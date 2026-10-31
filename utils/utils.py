from datetime import datetime, date, timedelta
import time


# 判断是否为交易时间, 交易时间True，非交易时间返回False
def tradingTime(symbol=None):
    """
    判断是否为交易时间
    symbol: 合约代码，如果提供则使用该合约的具体交易时间，否则使用通用时间
    """
    # 如果提供了合约代码，使用合约特定的交易时间
    if symbol:
        try:
            return is_contract_trading_time(symbol)
        except Exception as e:
            print(f"获取合约{symbol}交易时间失败，使用默认时间: {e}")

    # 默认交易时间（适用于大部分期货合约）
    now = datetime.now()
    dayOfWeek = now.weekday()

    # 只在工作日交易（周一到周五，0-4）
    if dayOfWeek >= 5:  # 周六、周日
        return False

    workTime1 = ['08:56:00', '11:30:00']
    workTime2 = ['12:59:00', '15:00:00']
    workTime3 = ['20:55:00', '23:30:00']

    beginWork1 = datetime.now().strftime("%Y-%m-%d") + ' ' + workTime1[0]
    endWork1 = datetime.now().strftime("%Y-%m-%d") + ' ' + workTime1[1]

    beginWork2 = datetime.now().strftime("%Y-%m-%d") + ' ' + workTime2[0]
    endWork2 = datetime.now().strftime("%Y-%m-%d") + ' ' + workTime2[1]

    beginWork3 = datetime.now().strftime("%Y-%m-%d") + ' ' + workTime3[0]
    endWork3 = datetime.now().strftime("%Y-%m-%d") + ' ' + workTime3[1]

    beginWorkSeconds1 = time.time() - time.mktime(time.strptime(beginWork1, '%Y-%m-%d %H:%M:%S'))
    endWorkSeconds1 = time.time() - time.mktime(time.strptime(endWork1, '%Y-%m-%d %H:%M:%S'))

    beginWorkSeconds2 = time.time() - time.mktime(time.strptime(beginWork2, '%Y-%m-%d %H:%M:%S'))
    endWorkSeconds2 = time.time() - time.mktime(time.strptime(endWork2, '%Y-%m-%d %H:%M:%S'))

    beginWorkSeconds3 = time.time() - time.mktime(time.strptime(beginWork3, '%Y-%m-%d %H:%M:%S'))
    endWorkSeconds3 = time.time() - time.mktime(time.strptime(endWork3, '%Y-%m-%d %H:%M:%S'))

    if (int(beginWorkSeconds1) > 0 and int(endWorkSeconds1) < 0) or \
       (int(beginWorkSeconds2) > 0 and int(endWorkSeconds2) < 0) or \
       (int(beginWorkSeconds3) > 0 and int(endWorkSeconds3) < 0):
        return True
    else:
        return False


def parse_time(time_str):
    hours, minutes, seconds = map(int, time_str.split(':'))
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

def get_time_period(api, symbol: str):
    """
    获取合约的交易时间段
    """
    try:
        # 查询合约信息
        symbol_info = api.query_symbol_info(symbol)

        # 获取交易时间
        trading_time_day = symbol_info['trading_time_day'].to_list()[0]
        trading_time_night = symbol_info['trading_time_night'].to_list()[0]

        print(f"合约 {symbol} 日间交易时间: {trading_time_day}")
        print(f"合约 {symbol} 夜间交易时间: {trading_time_night}")

        # Handle the case where trading_time_night is None
        if trading_time_night is None:
            trading_periods = trading_time_day
        else:
            # 合并日间和夜间交易时间
            trading_periods = trading_time_day + trading_time_night

        return trading_periods
    except Exception as e:
        print(f"获取合约 {symbol} 交易时间失败: {e}")
        # 返回默认的ag合约交易时间
        if 'ag' in symbol.lower():
            return [
                ['09:00:00', '11:30:00'],
                ['13:30:00', '15:00:00'],
                ['21:00:00', '02:30:00']  # 夜盘跨日
            ]
        else:
            return [
                ['09:00:00', '11:30:00'],
                ['13:30:00', '15:00:00']
            ]

def is_trading_time(trading_periods):
    """
    根据交易时间段判断当前是否为交易时间
    支持跨日夜盘的处理
    """
    # 获取当前时间
    now = datetime.now()
    current_time = timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
    dayOfWeek = now.weekday()

    # 周末不交易
    # 周日不交易
    if dayOfWeek == 6:
        return False

    # 检查当前时间是否在任何一个交易时间段内
    for period in trading_periods:
        start_time = parse_time(period[0])
        end_time = parse_time(period[1])

        # 处理跨日的情况（如夜盘21:00-02:30）
        if end_time <= start_time:
            # 跨日情况：
            if current_time >= start_time:
                # 晚间部分 (e.g. > 21:00). Valid for Mon-Fri (0-4).
                if dayOfWeek < 5: 
                    return True
            elif current_time <= end_time:
                 # 凌晨部分 (e.g. < 02:30). Valid for Tue-Sat (1-5).
                 if 0 < dayOfWeek <= 5: 
                     return True
        else:
            # 正常情况：同一天内的交易时间 (e.g. 09:00-11:30)
            # Valid for Mon-Fri (0-4).
            if start_time <= current_time <= end_time:
                if dayOfWeek < 5:
                    return True

    return False


def extract_contract_code(symbol):
    """
    从完整合约代码中提取品种代码
    例如：SHFE.ag2512 -> ag, CZCE.CF512 -> cf
    """
    if '.' in symbol:
        # 分离交易所和合约代码
        exchange, contract = symbol.split('.', 1)
        # 提取字母部分作为品种代码
        import re
        match = re.match(r'([a-zA-Z]+)', contract)
        if match:
            return match.group(1).lower()
    return symbol.lower()


def get_contract_trading_times(symbol):
    """
    根据合约代码获取交易时间配置
    返回交易时间段列表，格式：[['开始时间', '结束时间'], ...]
    """
    # 提取品种代码
    contract_code = extract_contract_code(symbol)

    # 贵金属合约（有夜盘）
    if contract_code in ['ag', 'au']:  # 白银、黄金
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00'],  # 日盘下午
            ['21:00:00', '02:30:00']   # 夜盘（跨日）
        ]

    # 有色金属（有夜盘）
    elif contract_code in ['cu', 'al', 'zn', 'pb', 'ni', 'sn']:  # 铜、铝、锌、铅、镍、锡
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00'],  # 日盘下午
            ['21:00:00', '01:00:00']   # 夜盘（跨日）
        ]

    # 黑色金属（有夜盘）
    elif contract_code in ['rb', 'hc', 'i', 'j', 'jm']:  # 螺纹钢、热卷、铁矿石、焦炭、焦煤
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00'],  # 日盘下午
            ['21:00:00', '23:00:00']   # 夜盘
        ]

    # 能源化工（有夜盘）
    elif contract_code in ['sc', 'fu', 'lu', 'bu', 'ru', 'nr', 'sp', 'eg', 'eb', 'pp', 'l', 'v', 'pg', 'ta', 'ma']:
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00'],  # 日盘下午
            ['21:00:00', '23:00:00']   # 夜盘
        ]

    # 农产品（有夜盘）
    elif contract_code in ['y', 'm', 'a', 'b', 'p', 'c', 'cs', 'jd']:  # 豆油、豆粕、豆一、豆二、棕榈油、玉米、玉米淀粉、鸡蛋
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00'],  # 日盘下午
            ['21:00:00', '23:00:00']   # 夜盘
        ]

    # 农产品（无夜盘）
    elif contract_code in ['cf', 'sr', 'oi', 'rm', 'zc', 'fg', 'sf', 'sm', 'pk', 'ur', 'sa', 'ri', 'lr', 'wh', 'pm', 'ap', 'cj']:
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00']   # 日盘下午
        ]

    # 股指期货
    elif contract_code in ['if', 'ic', 'ih', 'im']:
        return [
            ['09:30:00', '11:30:00'],  # 日盘上午
            ['13:00:00', '15:00:00']   # 日盘下午
        ]

    # 国债期货
    elif contract_code in ['t', 'tf', 'ts']:
        return [
            ['09:15:00', '11:30:00'],  # 日盘上午
            ['13:00:00', '15:15:00']   # 日盘下午
        ]

    # 广州期货交易所（GFEX）品种
    elif contract_code in ['si', 'lc']:  # 工业硅、碳酸锂
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00'],  # 日盘下午
            ['21:00:00', '23:00:00']   # 夜盘
        ]

    # 默认交易时间（无夜盘）
    else:
        return [
            ['09:00:00', '11:30:00'],  # 日盘上午
            ['13:30:00', '15:00:00']   # 日盘下午
        ]


def is_contract_trading_time(symbol):
    """
    根据具体合约判断当前是否为交易时间
    """
    if not symbol:
        return tradingTime()  # 回退到默认方法

    # 获取合约的交易时间配置
    trading_periods = get_contract_trading_times(symbol)

    # 使用通用的交易时间判断函数
    return is_trading_time(trading_periods)


if __name__ == '__main__':
    from tqsdk import TqApi, TqKq
    acct= 'YOUR_TQ_USER,YOUR_TQ_PASSWORD'
    api = TqApi(TqKq(), auth=acct, disable_print=True)
    product_id = 'ag'
    symbol = api.query_cont_quotes(product_id=product_id)
    periods = get_time_period(api, symbol)
    api.close()
    print(periods)
    is_trading_time(periods)
    print(is_trading_time(periods))

