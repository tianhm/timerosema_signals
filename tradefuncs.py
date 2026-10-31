# coding: utf-8
# 交易相关的函数
import os
from loguru import logger as mylog

directory = os.path.dirname(__file__) + r"/"
mylog.add(directory + 'tradefunc' + '.log', encoding='utf-8')


def BK(api, symbol, order_price, volume):
    print(symbol, volume)
    acct = api.get_account()
    order_price * volume
    if acct.available > 100:
        orderid = api.insert_order(symbol, direction='BUY', offset='OPEN', limit_price=order_price, volume=volume)
        print('tradefunc:', 'BK', symbol, order_price, volume)
        return orderid
    else:
        print('not enough fund.')
        return None


def SP(api, symbol, order_price, volume, today_prefer=False):
    """
    平多单 (Sell to close long position)
    today_prefer=True: 今仓优先
    today_prefer=False: 历史仓优先，历史仓不够时检查今仓
    """
    position = api.get_position(symbol)
    bkvol = position.pos_long
    bkvol_yd = position.pos_long_his
    bkvol_td = position.pos_long_today
    bkfreeze = position.volume_long_frozen
    orderid = 0
    bkvol_available = bkvol - bkfreeze

    if volume > bkvol_available:
        print('可平数量：', bkvol_available, '平仓数量:', volume, '平仓数量大于持仓数量，无法平仓。')
        mylog.warning(f'SP: 可平数量 {bkvol_available} < 平仓数量 {volume}，无法平仓')
        return None

    if today_prefer:  # 今仓优先
        bkvol_td_available = bkvol_td - bkfreeze if bkvol_td > bkfreeze else 0
        if bkvol_td_available >= volume:
            # 今仓足够
            orderid = api.insert_order(symbol, direction='SELL', offset='CLOSETODAY', limit_price=order_price, volume=volume)
        elif bkvol_td_available > 0:
            # 今仓不够，先平今仓
            orderid = api.insert_order(symbol, direction='SELL', offset='CLOSETODAY', limit_price=order_price, volume=bkvol_td_available)
            remaining = volume - bkvol_td_available
            if bkvol_yd >= remaining:
                # 再平历史仓
                orderid = api.insert_order(symbol, direction='SELL', offset='CLOSE', limit_price=order_price, volume=remaining)
            elif bkvol_yd > 0:
                orderid = api.insert_order(symbol, direction='SELL', offset='CLOSE', limit_price=order_price, volume=bkvol_yd)
        else:
            # 无今仓，平历史仓
            if bkvol_yd >= volume:
                orderid = api.insert_order(symbol, direction='SELL', offset='CLOSE', limit_price=order_price, volume=volume)
    else:  # 历史仓优先
        if bkvol_yd >= volume:
            # 历史仓足够
            orderid = api.insert_order(symbol, direction='SELL', offset='CLOSE', limit_price=order_price, volume=volume)
        elif bkvol_yd > 0:
            # 历史仓不够，先平历史仓
            orderid = api.insert_order(symbol, direction='SELL', offset='CLOSE', limit_price=order_price, volume=bkvol_yd)
            remaining = volume - bkvol_yd
            bkvol_td_available = bkvol_td - bkfreeze if bkvol_td > bkfreeze else 0
            if bkvol_td_available >= remaining:
                # 再平今仓补足差额
                orderid = api.insert_order(symbol, direction='SELL', offset='CLOSETODAY', limit_price=order_price, volume=remaining)
                mylog.info(f'SP: 历史仓 {bkvol_yd} 不够，已平今仓 {remaining} 手')
            elif bkvol_td_available > 0:
                orderid = api.insert_order(symbol, direction='SELL', offset='CLOSETODAY', limit_price=order_price, volume=bkvol_td_available)
                mylog.info(f'SP: 历史仓 {bkvol_yd} + 今仓 {bkvol_td_available} 仍不够，已全部平仓')
        else:
            # 无历史仓，平今仓
            bkvol_td_available = bkvol_td - bkfreeze if bkvol_td > bkfreeze else 0
            if bkvol_td_available >= volume:
                orderid = api.insert_order(symbol, direction='SELL', offset='CLOSETODAY', limit_price=order_price, volume=volume)
                mylog.info(f'SP: 无历史仓，平今仓 {volume} 手')
            elif bkvol_td_available > 0:
                orderid = api.insert_order(symbol, direction='SELL', offset='CLOSETODAY', limit_price=order_price, volume=bkvol_td_available)
                mylog.info(f'SP: 无历史仓，今仓不足，仅平 {bkvol_td_available} 手')

    print('tradefunc:', 'SP', symbol, order_price, volume, '历史仓:', bkvol_yd, '今仓:', bkvol_td)
    mylog.info(['tradefunc:', 'SP', symbol, order_price, volume, '历史仓:', bkvol_yd, '今仓:', bkvol_td])

    if orderid:
        return orderid
    else:
        return 0


def SK(api, symbol, order_price, volume):
    print(symbol, volume)
    acct = api.get_account()
    if acct.available > 100:
        orderid = api.insert_order(symbol, direction='SELL', offset='OPEN', limit_price=order_price, volume=volume)
        print('tradefunc:', 'SK', symbol, order_price, volume)
        return orderid
    else:
        print('not enough fund.')
        return None


def BP(api, symbol, order_price, volume, today_prefer=False):
    """
    平空单 (Buy to close short position)
    today_prefer=True: 今仓优先
    today_prefer=False: 历史仓优先，历史仓不够时检查今仓
    """
    position = api.get_position(symbol)
    skvol = position.pos_short  # 空单仓位
    skvol_yd = position.pos_short_his  # 空单历史仓位
    skvol_td = position.pos_short_today  # 空单当日仓位
    skfreeze = position.volume_short_frozen  # 冻结仓位
    orderid = 0
    skvol_available = skvol - skfreeze  # 可用持仓

    if volume > skvol_available:
        print('可平数量：', skvol_available, '平仓数量:', volume, '平仓数量大于持仓数量，无法平仓。')
        mylog.warning(f'BP: 可平数量 {skvol_available} < 平仓数量 {volume}，无法平仓')
        return None

    if today_prefer:  # 今仓优先
        if skvol_td >= volume:
            # 今仓足够
            orderid = api.insert_order(symbol, direction='BUY', offset='CLOSETODAY', limit_price=order_price, volume=volume)
        elif skvol_td > 0:
            # 今仓不够，先平今仓
            orderid = api.insert_order(symbol, direction='BUY', offset='CLOSETODAY', limit_price=order_price, volume=skvol_td)
            remaining = volume - skvol_td
            if skvol_yd >= remaining:
                # 再平历史仓
                orderid = api.insert_order(symbol, direction='BUY', offset='CLOSE', limit_price=order_price, volume=remaining)
            elif skvol_yd > 0:
                orderid = api.insert_order(symbol, direction='BUY', offset='CLOSE', limit_price=order_price, volume=skvol_yd)
        else:
            # 无今仓，平历史仓
            if skvol_yd >= volume:
                orderid = api.insert_order(symbol, direction='BUY', offset='CLOSE', limit_price=order_price, volume=volume)
    else:  # 历史仓优先
        if skvol_yd >= volume:
            # 历史仓足够
            orderid = api.insert_order(symbol, direction='BUY', offset='CLOSE', limit_price=order_price, volume=volume)
        elif skvol_yd > 0:
            # 历史仓不够，先平历史仓
            orderid = api.insert_order(symbol, direction='BUY', offset='CLOSE', limit_price=order_price, volume=skvol_yd)
            remaining = volume - skvol_yd
            if skvol_td >= remaining:
                # 再平今仓补足差额
                orderid = api.insert_order(symbol, direction='BUY', offset='CLOSETODAY', limit_price=order_price, volume=remaining)
                mylog.info(f'BP: 历史仓 {skvol_yd} 不够，已平今仓 {remaining} 手')
            elif skvol_td > 0:
                orderid = api.insert_order(symbol, direction='BUY', offset='CLOSETODAY', limit_price=order_price, volume=skvol_td)
                mylog.info(f'BP: 历史仓 {skvol_yd} + 今仓 {skvol_td} 仍不够，已全部平仓')
        else:
            # 无历史仓，平今仓
            if skvol_td >= volume:
                orderid = api.insert_order(symbol, direction='BUY', offset='CLOSETODAY', limit_price=order_price, volume=volume)
                mylog.info(f'BP: 无历史仓，平今仓 {volume} 手')
            elif skvol_td > 0:
                orderid = api.insert_order(symbol, direction='BUY', offset='CLOSETODAY', limit_price=order_price, volume=skvol_td)
                mylog.info(f'BP: 无历史仓，今仓不足，仅平 {skvol_td} 手')

    print('tradefunc:', 'BP', symbol, order_price, volume, '历史仓:', skvol_yd, '今仓:', skvol_td)
    mylog.info(['tradefunc:', 'BP', symbol, order_price, volume, '历史仓:', skvol_yd, '今仓:', skvol_td])
    if orderid:
        return orderid
    else:
        return 0


def SPK(api, symbol, order_price, volume, today=False):
    acct = api.get_account()
    pos = api.get_position(symbol)
    bkvoltd = api.get_position(symbol).pos_long_today
    bkvolyd = api.get_position(symbol).pos_long_his
    orderid = None

    if today and bkvoltd >= volume:
        api.insert_order(symbol, direction='SELL', offset='CLOSETODAY', limit_price=order_price, volume=volume)
    elif bkvolyd > volume:
        api.insert_order(symbol, direction='SELL', offset='CLOSE', limit_price=order_price, volume=volume)
    if acct.available > 30000:
        print(acct.available)
        orderid = api.insert_order(symbol, direction='SELL', offset='OPEN', limit_price=order_price, volume=volume)

    return orderid


def BPK(api, symbol, order_price, volume, today=True):
    # order_price = quote.last_price
    acct = api.get_account()
    skvoltd = api.get_position(symbol).pos_short_today
    skvolyd = api.get_position(symbol).pos_short_his
    orderid = None
    if today and skvoltd >= volume:
        api.insert_order(symbol, direction='BUY', offset='CLOSETODAY', limit_price=order_price, volume=volume)
    elif skvolyd > volume:
        api.insert_order(symbol, direction='BUY', offset='CLOSE', limit_price=order_price, volume=volume)
    if acct.available > 30000:
        orderid = api.insert_order(symbol, direction='BUY', offset='OPEN', limit_price=order_price, volume=volume)

    if orderid:
        return orderid
    else:
        return None


def BARSSK():
    pass


def BARSBK():
    pass


def BARSBP():
    pass


def BARSSP():
    pass


def getLastSig():
    pass


def display_acct_pos_info(api, symbol):
    position = api.get_position(symbol)
    account = api.get_account()
    print(account.user_id, symbol, "净值: %.2f,可用: %.2f, 今多头: %d 手, 今空头: %d 手" % (account.balance, account.available, position.volume_long, position.volume_short))


def display_all_positon(api):
    position = api.get_position()
    account = api.get_account()
    userid = account.user_id
    for pos in position:
        # print(pos)
        if pos.split('.')[0] in ('CZCE', 'SHFE', 'DCE'):
            # print(position[pos])
            print(userid, pos, '昨多:', position[pos]['pos_long_his'], '今多:', position[pos]['pos_long_today'])
            print(userid, pos, '昨空:', position[pos]['pos_short_his'], '今空:', position[pos]['pos_short_today'])


# 判断是否为工作日,工作日返回1，非工作日返回0
def workDay():
    import datetime
    import time
    workTime = ['08:30:00', '15:15:00']
    dayOfWeek = datetime.datetime.now().weekday()
    # dayOfWeek = datetime.today().weekday()
    beginWork = datetime.datetime.now().strftime("%Y-%m-%d") + ' ' + workTime[0]
    endWork = datetime.datetime.now().strftime("%Y-%m-%d") + ' ' + workTime[1]
    beginWorkSeconds = time.time() - time.mktime(time.strptime(beginWork, '%Y-%m-%d %H:%M:%S'))
    endWorkSeconds = time.time() - time.mktime(time.strptime(endWork, '%Y-%m-%d %H:%M:%S'))
    if (int(dayOfWeek) in range(5)) and int(beginWorkSeconds) > 0 and int(endWorkSeconds) < 0:
        return True
    else:
        return False
