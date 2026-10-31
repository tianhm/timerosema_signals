from strategies.TimeRoseMA_cross_speak import ma_cross

def runstrategy():

    from tqsdk import TqApi, TqAccount, TqKq
    from datetime import date

    product = 'ag'
    interval = 60
    bklimit = 2
    sklimit = 2
    single_volume = 1

    # 交易账号设置
    # api = TqApi(TqAccount(acct.name, acct.investorid, acct.password), auth=acct.tqacc)
    # symbol = api.query_cont_quotes(product_id=product)[0]
    api = TqApi(TqKq(), auth="YOUR_TQ_USER,YOUR_TQ_PASSWORD")
    symbol = api.query_cont_quotes(product_id=product)[0]
    quote = api.get_quote(symbol)
    while True:
        api.wait_update()
        print(f"open:{quote.open}, 最新价:{quote.last_price}, 最高价:{quote.highest}, 最低价:{quote.lowest}, 昨收:{quote.pre_close}, 均价:{quote.average}, 成交量:{quote.volume}, 涨停:{quote.upper_limit}, 跌停:{quote.lower_limit}") 
 
    ma_cross(api, symbol, interval, single_volume, bklimit, sklimit)


runstrategy()
