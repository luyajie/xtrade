import logging
import uuid

from flask import request, jsonify, Flask

from .event import Event
from .manager import TransactionManager
from .message_queue import LocalQueue
from .order import Order, InvalidOrderType


app = Flask(__name__)
queue = LocalQueue()


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
    queue.put(Event('new', order))
    return jsonify({'order_id': order.id, 'result': True})


@app.route('/cancel', methods=['POST'])
def cancel_order():
    data = request.get_json()
    return jsonify({'order_id': data['order_id'], 'result': False})


def run_app():
    logging.basicConfig(level=logging.DEBUG)

    manager = TransactionManager(queue)
    manager.daemon = True
    manager.start()
    app.run()


if __name__ == '__main__':
    run_app()
