"""
Multi-period ma_cross on ONE TqApi connection.

Counterpart of TimeRoseMA_cross_multi_periods.py. That runner spawns one
process per period, and each process opens its own TqApi. This runner keeps
a single TqApi / TqKq and drives every period as an asyncio task, which is
the other pattern in the tqsdk docs:

    https://tqsdk-python.readthedocs.io/en/latest/advanced/multi_strategy.html
    "单线程创建多个异步任务"

The main thread only calls wait_update(). Each period subscribes to its own
kline series and wakes through api.register_update_notify(). Trading rules
match ma_cross() in strategies/TimeRoseMA_cross_speak.py.

Shared-connection consequences:
- One sim account. Periods of the same contract see the same position, so
  bklimit / sklimit are account-level, not per period.
- sendsignal() is synchronous. A slow signal server stalls every period,
  because they share this thread.
"""

import copy
import time
from typing import Any, Dict, List

import pandas as pd
from loguru import logger as mylog
from myfunction import be_apart_from
from signalSend_noblock import sendsignal
from speaktext import speak_text
from strategies.TimeRoseMA_cross_speak import (
    MaCrossCaculate,
    disp_0Day_info,
    disp_account,
    disp_day_info,
    get_Signals_Ma,
)
from strategies.paths import Paths
from tradefuncs import BK, BP, SK, SP
from tqsdk import TqApi, TqKq
from tqsdk.tafunc import crossdown, crossup, ema, ma, time_to_str

DEFAULT_AUTH = "YOUR_TQ_USER,YOUR_TQ_PASSWORD"


class MaCrossSession:
    """One period of ma_cross, updated by the shared TqApi task loop."""

    def __init__(
        self,
        api: TqApi,
        symbol: str,
        interval: int,
        single_volume: int = 1,
        bklimit: int = 2,
        sklimit: int = 2,
        period: int = 13,
    ) -> None:
        self.api = api
        self.symbol = symbol
        self.interval = interval
        self.single_volume = single_volume
        self.bklimit = bklimit
        self.sklimit = sklimit
        self.period = period
        self.strategyname = "ma_cross"
        self._sink_id = None
        self.log = mylog

    def setup(self) -> None:
        """Subscribe and compute the initial signal. Call from the main thread."""
        api = self.api
        symbol = self.symbol
        interval = self.interval
        period = self.period

        acct = api.get_account()
        self.acct = acct
        disp_account(acct)
        try:
            userid = acct.user_id.split("-")[0]
        except Exception:
            userid = "moni"

        # Interval is part of the filename: several periods share this process.
        logfilename = "_".join([userid, symbol, self.strategyname, str(interval)])
        logfilename = Paths.log(logfilename)
        period_key = f"{symbol}|{interval}"

        def _only_this(record: Any, key: str = period_key) -> bool:
            return record["extra"].get("period_key") == key

        self.log = mylog.bind(period_key=period_key)
        self._sink_id = mylog.add(logfilename + ".log", encoding="utf-8", filter=_only_this)

        self.savebars = True
        quote = api.get_quote(symbol)
        self.quote = quote
        chinese_name = quote.instrument_name
        if "KQ.i" or "KQ.m" in symbol:
            SYMBOL = symbol
        elif "@" in symbol:
            SYMBOL = quote.underlying_symbol
        else:
            SYMBOL = symbol
        self.SYMBOL = SYMBOL

        # 不要加回 get_tick_serial: 快期模拟会重置tick流, tqsdk负shift崩溃, 且本策略未用tick
        klines = api.get_kline_serial(SYMBOL, duration_seconds=interval, data_length=8964)
        self.klines_tmp = api.get_kline_serial(SYMBOL, interval, 10)
        self.klines1 = copy.deepcopy(klines)
        del klines

        minutes = str(int(self.klines_tmp.duration.iloc[0] / 60))
        soundmsg = "".join([chinese_name, "     ", minutes])
        self.openlong_sound = soundmsg + "分钟" + "发出做多信号"
        self.openshort_sound = soundmsg + "分钟" + "发出做空信号"
        self.closelong_sound = soundmsg + "分钟" + "发出平多单信号"
        self.closeshort_sound = soundmsg + "分钟" + "发出平空单信号"

        daybars = api.get_kline_serial(SYMBOL, duration_seconds=60 * 60 * 24, data_length=365)
        self.daybars = daybars
        daybar = daybars.dropna()
        self.daybar = daybar
        hl = daybar.high - daybar.low
        ho = daybar.high - daybar.open
        ol = daybar.open - daybar.low
        self.hlmax = max(hl)
        self.daymean = int(hl.mean())
        self.homean = ho.mean()
        self.olmean = ol.mean()
        self.last3mean = int(hl.iloc[-4:-1].mean())

        self.dayopen = quote.open
        self.dayhigh = quote.highest
        self.daylow = quote.lowest
        self.preclose = quote.pre_close
        self.dayvib = self.dayhigh - self.daylow
        self.gap = self.dayopen - self.preclose

        self.position = api.get_position(SYMBOL)
        disp_day_info(self.daymean, self.last3mean, self.hlmax, self.homean, self.olmean)
        disp_0Day_info(quote)

        signal = MaCrossCaculate(self.klines1, period, quote)
        print(signal)
        sendsignal(self.strategyname, signal)

        C = self.klines1.close
        trmac = ma(C, period)
        ups = crossup(C, trmac)
        dns = crossdown(C, trmac)
        bkdist = be_apart_from(ups.tolist())
        skdist = be_apart_from(dns.tolist())
        if bkdist > skdist:
            self.signalnow = "空"
            self.distnow = skdist
        else:
            self.signalnow = "多"
            self.distnow = bkdist

        self.signalprice = C.iloc[-self.distnow]
        sigfloatprofit = quote.last_price - self.signalprice if self.signalnow == "多" else self.signalprice - quote.last_price
        self.profitlosslist = [sigfloatprofit]
        print(f"[{symbol}/{interval}s] 已订阅, 当前信号={self.signalnow}")

    def close(self) -> None:
        if self._sink_id is not None:
            try:
                mylog.remove(self._sink_id)
            except ValueError:
                pass
            self._sink_id = None

    async def run_task(self) -> None:
        """Wake on this period's day bars, short kline window, or quote."""
        watch = [self.daybars, self.klines_tmp, self.quote]
        async with self.api.register_update_notify(watch) as update_chan:
            async for _ in update_chan:
                self.on_update()

    def on_update(self) -> None:
        api = self.api
        quote = self.quote
        mylog_ = self.log
        daybars = self.daybars
        daybar = self.daybar
        klines_tmp = self.klines_tmp
        position = self.position
        acct = self.acct
        SYMBOL = self.SYMBOL
        symbol = self.symbol
        interval = self.interval
        period = self.period
        strategyname = self.strategyname
        single_volume = self.single_volume
        bklimit = self.bklimit
        sklimit = self.sklimit

        if api.is_changing(daybars.iloc[-1], "datetime"):
            self.savebars = True

            hl = daybar.high - daybar.low
            ho = daybar.high - daybar.open
            ol = daybar.open - daybar.low
            self.daymean = int(hl.mean())
            self.homean = ho.mean()
            self.olmean = ol.mean()
            self.hlmax = max(hl)
            self.last3mean = int(hl.iloc[-4:-1].mean())
            self.dayopen = quote.open
            self.dayhigh = quote.highest
            self.daylow = quote.lowest
            self.preclose = quote.pre_close
            self.dayvib = self.dayhigh - self.daylow
            self.gap = self.dayopen - self.preclose
            print("日线数据更新完成。。。")
            mylog_.info("日线数据更新完成。。。")

        if api.is_changing(klines_tmp.iloc[-1], "datetime"):
            disp_day_info(self.daymean, self.last3mean, self.hlmax, self.homean, self.olmean)
            disp_0Day_info(quote)
            print(
                "balance:",
                acct.balance,
                "poslong:",
                position.pos_long,
                "posshort:",
                position.pos_short,
                "poslong float profit:",
                position.float_profit_long,
                "posshort float profit:",
                position.float_profit_short,
            )

            newk = klines_tmp.iloc[-2]
            bdt = self.klines1.datetime.tolist()
            tt = newk.datetime

            if tt in bdt:
                mylog_.info("发现重复数据, 跳过...", time_to_str(tt))
            else:
                newk = newk.to_frame()
                newk = newk.T
                self.klines1 = pd.concat([self.klines1, newk], ignore_index=True)

            signal = MaCrossCaculate(self.klines1, period, quote)
            print(signal)
            sendsignal(strategyname, signal)

            signals = get_Signals_Ma(self.klines1, period=13)
            print("交易信号：", signals[-40:])

            C = self.klines1.close
            H = self.klines1.high
            L = self.klines1.low

            hl = ema(H - L, 23).iloc[-1]
            cover_gap = max(int(hl), 3)

            bkvol = position.pos_long
            skvol = position.pos_short

            trmac = ma(C, period)
            ups = crossup(C, trmac)
            dns = crossdown(C, trmac)
            upslist = ups.tolist()
            dnslist = dns.tolist()
            bkdist = be_apart_from(upslist)
            skdist = be_apart_from(dnslist)

            if bkdist > skdist:
                self.signalnow = "空"
                self.distnow = skdist
            else:
                self.signalnow = "多"
                self.distnow = bkdist

            self.signalprice = C.iloc[-self.distnow]
            sigfloatprofit = quote.last_price - self.signalprice if self.signalnow == "多" else self.signalprice - quote.last_price
            updatetime = time_to_str(klines_tmp.datetime.iloc[-1]).split(" ")[1].split(".")[0]

            signal = {
                "合约": SYMBOL,
                "周期": interval,
                "时间": updatetime,
                "当前信号": self.signalnow,
                "持续周期": self.distnow,
                "信号价格": self.signalprice,
                "现价": quote.last_price,
                "信号盈亏": sigfloatprofit,
            }
            print(signal)
            uplist = ups.tolist()
            average_signal_distance = int(len(uplist) / (uplist.count(1) * 2))
            print("平均信号距离：", average_signal_distance)
            print("upsignal:  ", ups.iloc[-40:].tolist())
            print("downsignal:", dns.iloc[-40:].tolist())

            self.profitlosslist.append(sigfloatprofit)

            # 交易部分
            basevalue = average_signal_distance * 2
            order_volume = (basevalue - self.distnow) * single_volume if self.distnow < average_signal_distance else single_volume
            order_volume = single_volume
            print("盈亏列表:", self.profitlosslist)
            if upslist[-1]:
                mylog_.info([symbol, "发出做多信号...."])
                speak_text(self.openlong_sound)

                bkprice = quote.ask_price1
                mylog_.info([SYMBOL, "bkprice", bkprice, "skprofit", position.float_profit_short, "skvol", skvol])
                self.profitlosslist = []

                if bkvol < bklimit:
                    orderVol = single_volume
                    if orderVol <= 0:
                        mylog_.info("持仓数量已经达到,不下单...")
                    else:
                        BK(api, symbol=SYMBOL, order_price=bkprice, volume=orderVol)
                        mylog_.info([SYMBOL, "下多单:", "数量", orderVol, "价格", bkprice])
                if skvol > 0:
                    if position.float_profit_short > 5 * skvol:
                        BP(api, symbol=SYMBOL, order_price=bkprice, volume=single_volume)
                        mylog_.info([SYMBOL, "平空单", "数量", single_volume, "价格", bkprice])
                    elif sigfloatprofit > 5:
                        BP(api, symbol=SYMBOL, order_price=bkprice, volume=single_volume)
                        mylog_.info([SYMBOL, "平空单", "数量", single_volume, "价格", bkprice])
                    else:
                        mylog_.info("short float profit doesnt match, dont cover.")

            if dnslist[-1]:
                mylog_.info([SYMBOL, "发出做空信号...."])
                speak_text(self.openshort_sound)

                skprice = quote.bid_price1
                bkvol = position.pos_long

                mylog_.info(["skprice", skprice, "bkprofit", position.float_profit_long, "bkvol", bkvol])
                self.profitlosslist = []
                print("skvol:", skvol, "sklimit:", sklimit, "ask1:", quote.ask_price1, "bid1:", quote.bid_price1)
                if skvol < sklimit:
                    orderVol = single_volume
                    if orderVol <= 0:
                        mylog_.info("持仓数量已达要求,不下单.")
                    else:
                        SK(api, symbol=SYMBOL, order_price=skprice, volume=orderVol)
                        mylog_.info([SYMBOL, "下空单", "数量", orderVol, "价格", skprice])

                if bkvol >= skvol and bkvol > 0:
                    if position.float_profit_long > 5 * bkvol:
                        SP(api, symbol=SYMBOL, order_price=skprice, volume=single_volume, today_prefer=True)
                        mylog_.info(["ping duo dan.", "volume", single_volume, "price", skprice])
                    else:
                        mylog_.info("float profit of long pos does not match the condition. dont cover.")

        if api.is_changing(quote):
            if self.signalnow == "多":
                sigfloatprofit = quote.last_price - self.signalprice
            if self.signalnow == "空":
                sigfloatprofit = self.signalprice - quote.last_price

            updatetime = quote.datetime.split(" ")[1].split(".")[0]
            signal = {
                "合约": SYMBOL,
                "周期": interval,
                "时间": updatetime,
                "当前信号": self.signalnow,
                "持续周期": self.distnow,
                "信号价格": self.signalprice,
                "现价": quote.last_price,
                "信号盈亏": sigfloatprofit,
            }
            sendsignal(strategyname, signal)
            print(signal)


def _resolve_auth(configs: List[Dict[str, Any]]) -> str:
    auths = [cfg.get("auth", DEFAULT_AUTH) for cfg in configs]
    if len(set(auths)) > 1:
        print("多个配置的 auth 不一致，单连接只使用第一条配置的 auth。")
    return auths[0] if auths else DEFAULT_AUTH


def run_multi_strategy(configs: List[Dict[str, Any]]) -> None:
    """
    Run every config on one TqApi.

    Each dict requires product and interval. Optional: single_volume, bklimit,
    sklimit, auth. auth is taken from the first config; one connection cannot
    log in as two users.
    """
    if not configs:
        print("run_multi_strategy: 空的配置列表，无操作。")
        return

    auth = _resolve_auth(configs)
    api = TqApi(TqKq(), auth=auth)
    sessions: List[MaCrossSession] = []
    try:
        symbol_cache: Dict[str, str] = {}
        seen = set()
        for cfg in configs:
            product = cfg["product"]
            interval = int(cfg["interval"])
            key = (product, interval)
            if key in seen:
                print(f"跳过重复配置: {product}/{interval}s")
                continue
            seen.add(key)

            if product not in symbol_cache:
                quotes = api.query_cont_quotes(product_id=product)
                if not quotes:
                    raise RuntimeError(f"query_cont_quotes 未返回合约: {product}")
                symbol_cache[product] = quotes[0]
            symbol = symbol_cache[product]
            print(f"[{product}/{interval}s] 准备订阅: 合约={symbol}")

            session = MaCrossSession(
                api,
                symbol,
                interval,
                single_volume=cfg.get("single_volume", 1),
                bklimit=cfg.get("bklimit", 2),
                sklimit=cfg.get("sklimit", 2),
            )
            session.setup()
            sessions.append(session)

        for session in sessions:
            api.create_task(session.run_task())

        print(f"单连接已启动 {len(sessions)} 个周期")
        while True:
            api.wait_update(deadline=time.time() + 60)
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭连接...")
    finally:
        for session in sessions:
            session.close()
        api.close()


def runstrategy() -> None:
    """Same OI periods as TimeRoseMA_cross_multi_periods.runstrategy()."""
    run_multi_strategy([
        {"product": "OI", "interval": 60, "single_volume": 1, "bklimit": 2, "sklimit": 2},
        {"product": "OI", "interval": 180, "single_volume": 1, "bklimit": 2, "sklimit": 2},
        {"product": "OI", "interval": 300, "single_volume": 1, "bklimit": 2, "sklimit": 2},
        {"product": "OI", "interval": 900, "single_volume": 1, "bklimit": 2, "sklimit": 2},
    ])


if __name__ == "__main__":
    runstrategy()
