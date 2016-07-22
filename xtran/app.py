import logging
import uuid

from flask import request, jsonify, Flask

from .event import Event
from .manager import TransactionManager
from .message_queue import LocalQueue
from .order import Order


app = Flask(__name__)
queue = LocalQueue()


@app.route('/trade.do', methods=['POST'])
def do_trade():
    try:
        data = request.get_json()
        order = Order.factory(data['type'], data['symbol'], data['amount'], data.get('price', None))
        order_id = uuid.uuid4()
        queue.put(Event('new', order))
    except Exception as e:
        logging.exception(e)
        raise
    return jsonify({'order_id': order_id, 'result': True})


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
