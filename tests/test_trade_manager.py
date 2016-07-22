import logging
logging.basicConfig(level=logging.DEBUG)
import time
from unittest import TestCase

from xtran.manager import TradeManager, TradeStore
from xtran.message_queue import LocalQueue
from xtran.event import NewOrderEvent, CancelOrderEvent
from xtran.order import Order, OrderStore


class TestTradeManager(TestCase):
    def setUp(self):
        self.queue = LocalQueue()
        self.trade_store = TradeStore()
        self.order_store = OrderStore()
        self.manager = TradeManager(self.queue, self.trade_store, order_store=self.order_store)
        self.manager.start()

    def test_run(self):
        o1 = Order.factory('sell', 'mu', 10, price=100)
        self.order_store.save(o1)
        o2 = Order.factory('buy', 'mu', 10, price=90)
        self.order_store.save(o2)
        o3 = Order.factory('sell', 'mu', 20, price=95)
        self.order_store.save(o3)
        o4 = Order.factory('buy', 'mu', 10, price=96)
        self.order_store.save(o4)
        o5 = Order.factory('buy', 'mu', 10, price=100)
        self.order_store.save(o5)
        self.queue.put(NewOrderEvent(o1.id))
        self.queue.put(NewOrderEvent(o2.id))
        self.queue.put(NewOrderEvent(o3.id))
        self.queue.put(NewOrderEvent(o4.id))
        self.queue.put(NewOrderEvent(o5.id))
        time.sleep(0.2)

        self.assertEqual(self.trade_store.get(o1.id), [])
        self.assertEqual(self.trade_store.get(o2.id), [])
        trades = self.trade_store.get(o3.id)
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].price, 95)
        self.assertEqual(trades[0].amount, 10)
        self.assertEqual(trades[0].status, 'partial_done', trades)
        self.assertEqual(trades[1].price, 95)
        self.assertEqual(trades[1].amount, 10)
        self.assertEqual(trades[1].status, 'all_done')
        trades = self.trade_store.get(o4.id)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].price, 95)
        self.assertEqual(trades[0].amount, 10)
        self.assertEqual(trades[0].status, 'all_done')

        self.queue.put(CancelOrderEvent(o1.id))
        time.sleep(0.1)
        trades = self.trade_store.get(o1.id)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].status, 'all_cancel')

        o6 = Order.factory('sell', 'mu', 5, price=80)
        self.order_store.save(o6)
        self.queue.put(NewOrderEvent(o6.id))
        self.queue.put(CancelOrderEvent(o2.id))
        time.sleep(0.1)
        trades = self.trade_store.get(o2.id)
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].status, 'partial_done')
        self.assertEqual(trades[1].status, 'left_cancel')
