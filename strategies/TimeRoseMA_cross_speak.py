import copy
import sys
import os
import pandas as pd
from myfunction import *

from tqsdk.tafunc import hhv, llv, crossup, crossdown, count, time_to_str, ema, trma, ma
from tradefuncs import *
from speaktext import speak_text
from loguru import logger as mylog
from signalSend_noblock import socket, sendsignal

from time import sleep
import time
try:
    from .paths import Paths
except:
    from paths import Paths

from MyTT import MA, CROSS
from utils.utils import tradingTime

# from tdx_function import CROSS


speak_text('程序开始运行')
speak_text('程序开始运行')


def disp_day_info(daymean, last3mean, hlmax, homean, olmean):
    print('最大价差:', hlmax, '平均价差:', daymean, '三日平均:', last3mean, '上价差:', int(homean), '下价差:', int(olmean))


def disp_0Day_info(quote):
    dayopen = quote.open
    dayhigh = quote.highest
    daylow = quote.lowest
    preclose = quote.pre_close
    dayvib = dayhigh - daylow
    gap = dayopen - preclose
    gapcover = False

    if gap > 0:
        if quote.lowest < quote.pre_close:
            gapcover = True
    else:
        if quote.highest > quote.pre_close:
            gapcover = True

    BB = (quote.last_price - quote.lowest) / (quote.highest - quote.lowest) if quote.highest - quote.lowest > 0 else 0.5
    BB = float('%.2f' % BB)

    upvib = quote.highest - quote.open
    dnvib = quote.open - quote.lowest

    print(quote.datetime, quote.instrument_id, '缺口：', gap, '回补:', gapcover, '现价:', quote.last_price, 'BB:', BB, '今日价差：',
          dayvib,
          '上价差:', upvib, '下价差:', dnvib)


def MaCrossCaculate(bars, period, quote):
    C = bars.close
    SYMBOL = bars.symbol.iloc[0]
    interval = bars.duration.iloc[0]

    trmac = ma(C, period)
    ups = crossup(C, trmac)
    dns = crossdown(C, trmac)
    upslist = ups.tolist()
    dnslist = dns.tolist()
    bkdist = be_apart_from(upslist)
    skdist = be_apart_from(dnslist)
    if bkdist > skdist:
        signalnow = '空'
        distnow = skdist
    else:
        signalnow = '多'
        distnow = bkdist
    updatetime = time_to_str(bars.datetime.iloc[-1]).split(' ')[1].split('.')[0]
    signalprice = C.iloc[-distnow]
    sigfloatprofit = quote.last_price - signalprice if signalnow == '多' else signalprice - quote.last_price
    print('时间:', updatetime, SYMBOL, interval, '当前信号:', signalnow, '持续周期:', distnow, '信号价格:', signalprice, '现价:',
          C.iloc[-1], '信号盈亏:', sigfloatprofit)
    uplist = ups.tolist()
    average_signal_distance = int(len(uplist) / (uplist.count(1) * 2))
    print('平均信号距离：', average_signal_distance)
    print('upsignal:  ', ups.iloc[-40:].tolist())
    print('downsignal:', dns.iloc[-40:].tolist())

    updatetime = time_to_str(bars.datetime.iloc[-1]).split(' ')[1].split('.')[0]
    signal = {'合约': SYMBOL, '周期': interval, '时间': updatetime, '当前信号': signalnow,
              '持续周期': distnow, '信号价格': signalprice, '现价': C.iloc[-1],
              '信号盈亏': sigfloatprofit}

    return signal


def get_Signals_Ma(bars, period=13):
    CLOSE = bars.close.values
    OPEN = bars.open.values
    HIGH = bars.high.values
    LOW = bars.low.values
    N = period

    ups = list(CROSS(CLOSE, MA(CLOSE, N)))
    dns = list(CROSS(MA(CLOSE, N), CLOSE))

    # dnsn = [-1 if x == 1 else x for x in dns]
    signals = []

    for i in range(len(ups)):
        if ups[i] == 0 and dns[i] == 0:
            signals.append(0)

        else:
            if ups[i] == 1:
                signals.append(1)
            if dns[i] == 1:
                signals.append(-1)

    # bsigs = ups.count(True)
    # ssigs = dns.count(True)
    # avgdistance = len(ups) / (bsigs + ssigs)
    return signals


def disp_account(acct):
    acct_info = dict(acct)
    print(acct_info)


def ma_cross(api, symbol, interval, single_volume, bklimit, sklimit, period=13):
    # strategyname = '凤舞杨柳'
    strategyname = 'ma_cross'
    acct = api.get_account()
    disp_account(acct)
    try:
        userid = acct.user_id.split('-')[0]
    except:
        userid = 'moni'

    logfilename = '_'.join([userid, symbol, strategyname])
    logfilename = Paths.log(logfilename)

    mylog.add(logfilename + '.log', encoding='utf-8')
    savebars = True
    quote = api.get_quote(symbol)
    chinese_name = quote.instrument_name
    if 'KQ.i' or 'KQ.m' in symbol:
        SYMBOL = symbol

    elif '@' in symbol:
        SYMBOL = quote.underlying_symbol

    else:
        SYMBOL = symbol

    # trading_symbol = SYMBOL.split('.')[1]

    # 不要加回 get_tick_serial: 快期模拟会重置tick流, tqsdk负shift崩溃, 且本策略未用tick
    klines = api.get_kline_serial(SYMBOL, duration_seconds=interval, data_length=8964)
    klines_tmp = api.get_kline_serial(SYMBOL, interval, 10)
    klines1 = copy.deepcopy(klines)
    del klines

    productid = SYMBOL.split('.')[1]
    minutes = str(int(klines_tmp.duration.iloc[0] / 60))
    # soundmsg = ''.join([productid, '     ', minutes])
    soundmsg = ''.join([chinese_name, '     ', minutes])
    # 设置语音提醒信息
    openlong_sound = soundmsg + '分钟' + '发出做多信号'
    openshort_sound = soundmsg + '分钟' + '发出做空信号'
    closelong_sound = soundmsg + '分钟' + '发出平多单信号'
    closeshort_sound = soundmsg + '分钟' + '发出平空单信号'

    # 获得日线数据的相关信息
    daybars = api.get_kline_serial(SYMBOL, duration_seconds=60 * 60 * 24, data_length=365)
    daybar = daybars.dropna()
    hl = daybar.high - daybar.low
    ho = daybar.high - daybar.open
    ol = daybar.open - daybar.low
    hlmax = max(hl)
    daymean = int(hl.mean())
    homean = ho.mean()
    olmean = ol.mean()
    last3mean = int(hl.iloc[-4:-1].mean())

    dayopen = quote.open
    dayhigh = quote.highest
    daylow = quote.lowest
    preclose = quote.pre_close
    dayvib = dayhigh - daylow
    gap = dayopen - preclose

    position = api.get_position(SYMBOL)
    disp_day_info(daymean, last3mean, hlmax, homean, olmean)
    disp_0Day_info(quote)

    signal = MaCrossCaculate(klines1, period, quote)
    print(signal)
    sendsignal(strategyname, signal)

    O = klines1.open
    H = klines1.high
    L = klines1.low
    C = klines1.close

    trmac = ma(C, period)
    ups = crossup(C, trmac)
    dns = crossdown(C, trmac)
    upslist = ups.tolist()
    dnslist = dns.tolist()
    bkdist = be_apart_from(upslist)
    skdist = be_apart_from(dnslist)
    if bkdist > skdist:
        signalnow = '空'
        distnow = skdist
    else:
        signalnow = '多'
        distnow = bkdist

    signalprice = C.iloc[-distnow]
    sigfloatprofit = quote.last_price - signalprice if signalnow == '多' else signalprice - quote.last_price
    updatetime = time_to_str(klines_tmp.datetime.iloc[-1]).split(' ')[1].split('.')[0]
    profitlosslist = [sigfloatprofit]
    while True:

        api.wait_update(deadline=time.time() + 60)
        if api.is_changing(daybars.iloc[-1], "datetime"):
            savebars = True
            dayopensp = True
            dayopenbp = True

            hl = daybar.high - daybar.low
            ho = daybar.high - daybar.open
            ol = daybar.open - daybar.low
            daymean = int(hl.mean())
            homean = ho.mean()
            olmean = ol.mean()
            hlmax = max(hl)
            last3mean = int(hl.iloc[-4:-1].mean())
            dayopen = quote.open
            dayhigh = quote.highest
            daylow = quote.lowest
            preclose = quote.pre_close
            dayvib = dayhigh - daylow
            gap = dayopen - preclose
            gapcover = False
            print('日线数据更新完成。。。')
            mylog.info('日线数据更新完成。。。')

        if api.is_changing(klines_tmp.iloc[-1], "datetime"):
            disp_day_info(daymean, last3mean, hlmax, homean, olmean)
            disp_0Day_info(quote)
            print('balance:', acct.balance, 'poslong:', position.pos_long, 'posshort:', position.pos_short,
                  'poslong float profit:', position.float_profit_long, 'posshort float profit:',
                  position.float_profit_short)

            speakyn = True

            newk = klines_tmp.iloc[-2]
            bdt = klines1.datetime.tolist()
            tt = newk.datetime

            if tt in bdt:
                mylog.info('发现重复数据, 跳过...', time_to_str(tt))
            else:
                newk = newk.to_frame()
                newk = newk.T
                klines1 = pd.concat([klines1, newk], ignore_index=True)

                # klines1 = klines1.append(newk)

            signal = MaCrossCaculate(klines1, period, quote)
            print(signal)
            sendsignal(strategyname, signal)

            signals = get_Signals_Ma(klines1, period=13)
            print('交易信号：', signals[-40:])

            O = klines1.open
            H = klines1.high
            L = klines1.low
            C = klines1.close

            hl = ema(H - L, 23).iloc[-1]
            cover_gap = max(int(hl), 3)

            bkvol = position.pos_long
            bkvol_yd = position.pos_long_his
            bkvol_td = position.pos_long_today
            bkfreeze = position.volume_long_frozen

            skvol = position.pos_short
            skvol_yd = position.pos_short_his
            skvol_td = position.pos_short_today
            skfreeze = position.volume_short_frozen

            trmac = ma(C, period)
            ups = crossup(C, trmac)
            dns = crossdown(C, trmac)
            upslist = ups.tolist()
            dnslist = dns.tolist()
            bkdist = be_apart_from(upslist)
            skdist = be_apart_from(dnslist)

            if bkdist > skdist:
                signalnow = '空'
                distnow = skdist
            else:
                signalnow = '多'
                distnow = bkdist

            signalprice = C.iloc[-distnow]
            sigfloatprofit = quote.last_price - signalprice if signalnow == '多' else signalprice - quote.last_price
            updatetime = time_to_str(klines_tmp.datetime.iloc[-1]).split(' ')[1].split('.')[0]

            # print('时间:', updatetime, SYMBOL, interval, '当前信号:', signalnow, '持续周期:', distnow, '信号价格:', signalprice,
            #       '现价:', quote.last_price,
            #       '信号盈亏:', sigfloatprofit)
            signal = {'合约': SYMBOL, '周期': interval, '时间': updatetime, '当前信号': signalnow,
                      '持续周期': distnow, '信号价格': signalprice, '现价': quote.last_price,
                      '信号盈亏': sigfloatprofit}
            print(signal)
            uplist = ups.tolist()
            average_signal_distance = int(len(uplist) / (uplist.count(1) * 2))
            print('平均信号距离：', average_signal_distance)
            print('upsignal:  ', ups.iloc[-40:].tolist())
            print('downsignal:', dns.iloc[-40:].tolist())

            profitlosslist.append(sigfloatprofit)

            # 交易部分
            basevalue = average_signal_distance * 2
            order_volume = (basevalue - distnow) * single_volume if distnow < average_signal_distance else single_volume
            order_volume = single_volume
            print('盈亏列表:', profitlosslist)
            if upslist[-1]:
                mylog.info([symbol, '发出做多信号....'])
                speak_text(openlong_sound)

                bkprice = quote.ask_price1
                mylog.info([SYMBOL, 'bkprice', bkprice, 'skprofit', position.float_profit_short, 'skvol', skvol])
                profitlosslist = []

                # 下多单
                if bkvol < bklimit:
                    # orderVol = min(bklimit - bkvol, skvol - bkvol + 1)
                    orderVol = single_volume
                    if orderVol <= 0:
                        mylog.info('持仓数量已经达到,不下单...')
                    else:
                        BK(api, symbol=SYMBOL, order_price=bkprice, volume=orderVol)
                        mylog.info([SYMBOL, '下多单:', '数量', orderVol, '价格', bkprice])
                # 平空单
                if skvol > 0:
                    if position.float_profit_short > 5 * skvol:  # 空单盈利
                        # BP(api, symbol=SYMBOL, order_price=bkprice, volume=skvol)
                        BP(api, symbol=SYMBOL, order_price=bkprice, volume=single_volume)
                        mylog.info([SYMBOL, '平空单', '数量', single_volume, '价格', bkprice])

                    elif sigfloatprofit>5:  # 信号盈利
                        BP(api, symbol=SYMBOL, order_price=bkprice, volume=single_volume)
                        mylog.info([SYMBOL, '平空单', '数量', single_volume, '价格', bkprice])

                    else:
                        mylog.info('short float profit doesnt match, dont cover.')

            if dnslist[-1]:
                mylog.info([SYMBOL, '发出做空信号....'])
                speak_text(openshort_sound)

                skprice = quote.bid_price1
                bkvol = position.pos_long
                bkvol_cost = position.open_price_long

                mylog.info(['skprice', skprice, 'bkprofit', position.float_profit_long, 'bkvol', bkvol])
                profitlosslist = []
                # 下空单
                print('skvol:', skvol, 'sklimit:', sklimit, 'ask1:', quote.ask_price1, 'bid1:', quote.bid_price1)
                if skvol < sklimit:
                    # orderVol = min(sklimit - skvol, bkvol + 1 - skvol)
                    orderVol = single_volume
                    if orderVol <= 0:
                        mylog.info('持仓数量已达要求,不下单.')

                    else:
                        SK(api, symbol=SYMBOL, order_price=skprice, volume=orderVol)
                        mylog.info([SYMBOL, '下空单', '数量', orderVol, '价格', skprice])

                # 平多单
                if bkvol >= skvol and bkvol > 0:
                    if position.float_profit_long > 5 * bkvol:  # 多单盈利
                        # SP(api, symbol=SYMBOL, order_price=skprice, volume=bkvol)
                        SP(api, symbol=SYMBOL, order_price=skprice, volume=single_volume, today_prefer=True)
                        mylog.info(['ping duo dan.', 'volume', single_volume, 'price', skprice])

                    else:
                        mylog.info('float profit of long pos does not match the condition. dont cover.')

        if api.is_changing(quote):
            if gap > 0:
                if quote.lowest < quote.pre_close:
                    gapcover = True
            else:
                if quote.highest > quote.pre_close:
                    gapcover = True

            if signalnow == '多':
                sigfloatprofit = quote.last_price - signalprice
            if signalnow == '空':
                sigfloatprofit = signalprice - quote.last_price

            # print('当前信号:', signalnow, '信号价格:', signalprice, '现价:', quote.last_price, '信号盈亏:', sigfloatprofit)

            updatetime = quote.datetime.split(' ')[1].split('.')[0]
            signal = {'合约': SYMBOL, '周期': interval, '时间': updatetime, '当前信号': signalnow,
                      '持续周期': distnow, '信号价格': signalprice, '现价': quote.last_price,
                      '信号盈亏': sigfloatprofit}
            sendsignal(strategyname, signal)
            print(signal)




def runstrategy():
    from tqsdk import TqApi, TqAccount, TqKq
    from datetime import date
    # from accounts import tgjyzjy as acct

    product = 'rb'
    symbol = product
    interval = 60
    bklimit = 200
    sklimit = 200
    single_volume = 1

    # 交易账号设置
    # api = TqApi(TqAccount(acct.name, acct.investorid, acct.password), auth=acct.tqacc)

    api = TqApi(TqKq(), auth="YOUR_TQ_USER,YOUR_TQ_PASSWORD", disable_print=True, debug=None)
    symbol = api.query_cont_quotes(product_id=product)[0]
    ma_cross(api, symbol, interval, single_volume, bklimit, sklimit)


#
if __name__ == "__main__":
    runstrategy()
