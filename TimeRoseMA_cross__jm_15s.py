from strategies.TimeRoseMA_cross_speak import ma_cross

def runstrategy():

    from tqsdk import TqApi, TqAccount, TqKq
    from datetime import date

    product = 'jm'
    interval = 15
    bklimit = 2
    sklimit = 2
    single_volume = 1

    # 交易账号设置
    # api = TqApi(TqAccount(acct.name, acct.investorid, acct.password), auth=acct.tqacc)
    # symbol = api.query_cont_quotes(product_id=product)[0]
    api = TqApi(TqKq(), auth="YOUR_TQ_USER,YOUR_TQ_PASSWORD")
    symbol = api.query_cont_quotes(product_id=product)[0]
    ma_cross(api, symbol, interval, single_volume, bklimit, sklimit)


runstrategy()
