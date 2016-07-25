import json
from unittest import TestCase

from xtran.app import app, Order, NewOrderEvent, CancelOrderEvent
from xtran.app import install_queue, install_trade_store, install_order_store, uninstall_all
from xtran.app import get_queue, get_order_store, get_trade_store


class TestHandlers(TestCase):
    def setUp(self):
        self.queue = install_queue()
        self.trade_store = install_trade_store()
        self.order_store = install_order_store()

    def tearDown(self):
        uninstall_all()

    def test_component_installation(self):
        with app.app_context():
            self.assertTrue(get_queue() is self.queue)
            self.assertTrue(get_trade_store() is self.trade_store)
            self.assertTrue(get_order_store() is self.order_store)

    def test_do_trade(self):
        with app.test_client() as c:
            data = json.dumps({
                'symbol': 'WSCN',
                'type': 'sell',
                'amount': 10,
                'price': 100,
            })
            resp = c.post('/trade.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 200, resp.data)

            resp_data = json.loads(resp.data.decode())
            self.assertTrue(resp_data['result'])
            order_id = resp_data['order_id']

        order = self.order_store.get(order_id)
        self.assertEqual(order.id, order_id)
        self.assertEqual(order.TYPE, 'sell')
        self.assertEqual(order.amount, 10)
        self.assertEqual(order.price, 100)
        self.assertEqual(order.symbol, 'WSCN')

        event = self.queue.get()
        self.assertTrue(isinstance(event, NewOrderEvent), event)
        self.assertEqual(event.order_id, order_id)

    def test_do_trade_with_non_json_formatted_content(self):
        with app.test_client() as c:
            data = {
                'symbol': 'WSCNn',
                'type': 'sell',
                'amount': 10,
                'price': 100,
            }
            resp = c.post('/trade.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 400, resp.data)
            resp_data = json.loads(resp.data.decode())
            self.assertTrue('json-formated' in resp_data['message'])

    def test_do_trade_with_unknown_symbol(self):
        with app.test_client() as c:
            data = json.dumps({
                'symbol': 'WSCNn',
                'type': 'sell',
                'amount': 10,
                'price': 100,
            })
            resp = c.post('/trade.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 400, resp.data)
            resp_data = json.loads(resp.data.decode())
            self.assertTrue('unknown symbol' in resp_data['message'])

    def test_do_trade_with_price_out_of_range(self):
        with app.test_client() as c:
            data = json.dumps({
                'symbol': 'WSCN',
                'type': 'sell',
                'amount': 10,
                'price': 110.01,
            })
            resp = c.post('/trade.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 400, resp.data)
            resp_data = json.loads(resp.data.decode())
            self.assertTrue('110.01' in resp_data['message'], resp_data['message'])

    def test_do_trade_with_price_of_more_than_two_floating_points(self):
        with app.test_client() as c:
            data = json.dumps({
                'symbol': 'WSCN',
                'type': 'sell',
                'amount': 10,
                'price': 100.001,
            })
            resp = c.post('/trade.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 400, resp.data)
            resp_data = json.loads(resp.data.decode())
            self.assertTrue('100.001' in resp_data['message'], resp_data['message'])

    def test_do_trade_with_invalid_amount(self):
        with app.test_client() as c:
            data = json.dumps({
                'symbol': 'WSCN',
                'type': 'sell',
                'amount': 1001,
                'price': 101,
            })
            resp = c.post('/trade.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 400, resp.data)
            resp_data = json.loads(resp.data.decode())
            self.assertTrue('1001' in resp_data['message'])

    def test_cancel_order(self):
        self.order_store.save(Order.factory('sell', 'WSCN', 10, price=100))
        with app.test_client() as c:
            data = json.dumps({
                'symbol': 'WSCN',
                'order_id': 1,
            })
            resp = c.post('/cancel_order.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 200, resp.data)

            resp_data = json.loads(resp.data.decode())
            self.assertFalse(resp_data['result'])
            order_id = resp_data['order_id']
            self.assertEqual(order_id, 1)

        event = self.queue.get()
        self.assertTrue(isinstance(event, CancelOrderEvent), event)
        self.assertEqual(event.order_id, 1)

    def test_cancel_order_with_order_not_found(self):
        with app.test_client() as c:
            data = json.dumps({
                'symbol': 'WSCN',
                'order_id': 1,
            })
            resp = c.post('/cancel_order.do', headers={'content-type': 'application/json'}, data=data)
            self.assertEqual(resp.status_code, 400, resp.data)
            resp_data = json.loads(resp.data.decode())
            self.assertTrue('not found' in resp_data['message'])
