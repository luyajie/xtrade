import logging
import os
import time

from flask import request, jsonify, Flask, current_app

from .event import NewOrderEvent, CancelOrderEvent
from .exc import InvalidRequest, InvalidRequestBody
from .manager import TradeManager, DBTradeStore
from .message_queue import LocalQueue
from .order import OrderStore, OrderNotFound
from .symbol import get_symbol_price_range, SymbolNotFound


app = Flask(__name__)


def get_queue():
    return current_app.extensions['_message_queue']


def install_queue(queue=None):
    queue = queue or LocalQueue()
    app.extensions['_message_queue'] = queue
    return queue


def uninstall_queue():
    app.extensions.pop('_message_queue')


def get_trade_store():
    return current_app.extensions['_trade_store']


def install_trade_store(store=None):
    store = store or TradeStore()
    app.extensions['_trade_store'] = store
    return store


def uninstall_trade_store():
    app.extensions.pop('_trade_store')


def get_order_store():
    return current_app.extensions['_order_store']


def install_order_store(store=None):
    store = store or OrderStore()
    app.extensions['_order_store'] = store
    return store


def uninstall_order_store():
    app.extensions.pop('_order_store')


def uninstall_all():
    app.extensions = {}


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
        min_price, max_price = get_symbol_price_range(symbol_id)
    except SymbolNotFound:
        raise InvalidRequest('unknown symbol: %s' % (symbol_id,))
    if price and (price < min_price or price > max_price):
        raise InvalidRequest('expected price between %s and %s, got: %s' % (min_price, max_price, price))
    if int(price * 100) != price * 100:
        raise InvalidRequest('price should have no more than two floating points. got: %s' % (price,))
    order = get_order_store().create(type_, symbol_id, amount, price)
    get_queue().put(NewOrderEvent(order.id))
    return jsonify({'order_id': order.id, 'result': True})


@app.route('/cancel_order.do', methods=['POST'])
def cancel_order():
    try:
        data = request.get_json(force=True)
    except Exception:
        raise InvalidRequestBody('expected json-format body')
    order_id = data['order_id']
    try:
        get_order_store().get(order_id)
    except OrderNotFound:
        raise InvalidRequest('order not found: %s' % (order_id,))
    get_queue().put(CancelOrderEvent(order_id))
    result = False
    trade_store = get_trade_store()
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

    app.config.from_object(os.environ.get('XTRADE_CONFIG') or 'config')

    from .order import DBOrderStore
    from .db import db

    db.init_app(app)
    # todo: why this required?
    db.app = app

    db.create_all()
    install_order_store(DBOrderStore(db))
    order_store = DBOrderStore(db)
    install_trade_store(DBTradeStore(db))
    trade_store = DBTradeStore(db)

    queue = install_queue()
    manager = TradeManager(queue, trade_store, order_store)
    manager.start()
    app.run()


if __name__ == '__main__':
    run_app()
