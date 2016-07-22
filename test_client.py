import json
import random
import requests
import time

URL = 'http://127.0.0.1:5000'
SYMBOL = 'WSCN'
PRICE_RANGE = (90, 110)
TYPES = ('sell', 'buy', 'market_sell', 'market_buy')
INTERVAL = 250  # UNIT: millisecond


def do_trade(type_, amount, price):
    url = URL + '/trade.do'
    data = {
        'type': type_,
        'amount': amount,
        'price': price,
        'symbol': SYMBOL,
    }
    resp = requests.post(url, json=data)
    if resp.status_code != 200:
        raise Exception('%s: %s' % (resp.status_code, resp.text))

    resp_data = json.loads(resp.text)
    if not resp_data['result']:
        raise Exception('fail: `%s`' % (resp.text,))
    return resp_data['order_id']


def run_test(num=1000):
    for i in range(num):
        type_ = random.choice(TYPES)
        amount = random.randint(1, 999)
        price = random.randint(PRICE_RANGE[0] * 100, PRICE_RANGE[1] * 100) * 1.0 / 100
        order_id = do_trade(type_, amount, price)
        if not type_.startswith('market'):
            with open('client.log', 'a') as f:
                f.write('%s\n' % (order_id,))
        print("%s: %s" % (i, order_id))
        time.sleep(INTERVAL * 1.0 / 1000)


if __name__ == '__main__':
    import sys
    num = 1000
    if len(sys.argv) > 1:
        num = int(sys.argv[1])
    run_test(num)
