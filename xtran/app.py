import logging

from flask import request, jsonify, Flask

from .event import NewOrderEvent, CancelOrderEvent
from .manager import TradeManager, TradeStore
from .message_queue import LocalQueue
from .order import Order, OrderStore, InvalidOrderType


app = Flask(__name__)
queue = LocalQueue()
trade_store = TradeStore()
order_store = OrderStore()


@app.errorhandler(InvalidOrderType)
def handle_invalid_type(e):
    resp = jsonify({'status': 400, 'error': 'invalid type', 'message': str(e)})
    resp.status_code = 400
    return resp


@app.route('/trade.do', methods=['POST'])
def do_trade():
    try:
        data = request.get_json()
    except Exception as e:
        logging.exception(e)
        raise
    order = Order.factory(data['type'], data['symbol'], data['amount'], data.get('price', None))
    order_store.save(order)
    queue.put(NewOrderEvent(order.id))
    return jsonify({'order_id': order.id, 'result': True})


@app.route('/cancel', methods=['POST'])
def cancel_order():
    data = request.get_json()
    return jsonify({'order_id': data['order_id'], 'result': False})


def run_app():
    logging.basicConfig(level=logging.DEBUG)

    manager = TradeManager(queue, trade_store, order_store)
    manager.start()
    app.run()


if __name__ == '__main__':
    run_app()
