import logging
import time

from flask import request, jsonify, Flask

from .event import NewOrderEvent, CancelOrderEvent
from .exc import InvalidRequest, InvalidRequestBody
from .manager import TradeManager, TradeStore
from .message_queue import LocalQueue
from .order import Order, OrderStore, OrderNotFound
from .symbol import get_symbol_price, SymbolNotFound


app = Flask(__name__)
queue = LocalQueue()
trade_store = TradeStore()
order_store = OrderStore()


@app.errorhandler(InvalidRequest)
def handle_invalid_type(e):
    resp = jsonify({'status': 400, 'error': e.__class__.__name__, 'message': str(e)})
    resp.status_code = 400
    return resp


@app.route('/trade.do', methods=['POST'])
def do_trade():
    try:
        data = request.get_json(force=True)
    except Exception:
        raise InvalidRequestBody('expected json-formated body')
    try:
        price = data.get('price', None)
        amount = data['amount']
        type_ = data['type']
        symbol_id = data['symbol']
    except KeyError as e:
        raise InvalidRequest('miss key: %s' % (e,))
    if not isinstance(amount, int) or amount <= 0 or amount >= 1000:
        raise InvalidRequest(
            'expected `amount` as an integer: 0 < amount < 1000. got: %s' % (amount,))
    try:
        min_price, max_price = get_symbol_price(symbol_id)
    except SymbolNotFound:
        raise InvalidRequest('unknown symbol: %s' % (symbol_id,))
    if price and (price < min_price or price > max_price):
        raise InvalidRequest('expected price between %s and %s, got: %s' % (min_price, max_price, price))
    order = Order.factory(type_, symbol_id, amount, price)
    order_store.save(order)
    queue.put(NewOrderEvent(order.id))
    return jsonify({'order_id': order.id, 'result': True})


@app.route('/cancel_order.do', methods=['POST'])
def cancel_order():
    try:
        data = request.get_json(force=True)
    except Exception:
        raise InvalidRequestBody('expected json-format body')
    order_id = data['order_id']
    try:
        order_store.get(order_id)
    except OrderNotFound:
        raise InvalidRequest('order not found: %s' % (order_id,))
    queue.put(CancelOrderEvent(order_id))
    result = False
    for i in range(10):
        # fixme: wait for the CancelEvent processed and will block the process
        time.sleep(0.1)
        trades = trade_store.get(order_id)
        if trades and trades[-1].is_canceled:
            result = True
            break
    return jsonify({'order_id': order_id, 'result': result})


def run_app():
    logging.basicConfig(level=logging.DEBUG)

    manager = TradeManager(queue, trade_store, order_store)
    manager.start()
    app.run()


if __name__ == '__main__':
    run_app()
