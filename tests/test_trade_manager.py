import time
from unittest import TestCase

from xtrade.manager import TradeManager, Trade, MemTradeStore, DBTradeStore
from xtrade.message_queue import LocalQueue
from xtrade.event import NewOrderEvent, CancelOrderEvent
from xtrade.order import MemOrderStore as OrderStore, BuyOrder, SellOrder
from xtrade.app import app
from xtrade.db import db

import logging
logging.basicConfig(level=logging.DEBUG)


class TestDBTradeStore(TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        app.config.from_mapping(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                                SQLALCHEMY_TRACK_MODIFICATIONS=True)
        db.init_app(app)
        db.create_all()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_save_and_get(self):
        store = DBTradeStore(db)
        trade = store.do_trade(BuyOrder(1, 'mu', 100, timestamp='', price=10), price=9, amount=10)
        self.assertEqual(trade.id, 1)
        self.assertEqual(trade.status, 'partial_done')

        trade = store.do_trade(BuyOrder(1, 'mu', 100, timestamp='', price=10), price=10, amount=100)
        self.assertEqual(trade.id, 2)
        self.assertEqual(trade.status, 'all_done')


class TestTradeManager(TestCase):
    def setUp(self):
        self.queue = LocalQueue()
        self.trade_store = MemTradeStore()
        self.order_store = OrderStore()
        self.manager = TradeManager(self.queue, self.trade_store, order_store=self.order_store)
        self.manager.start()

    def test_run(self):
        o1 = self.order_store.create('sell', 'WSCN', 10, price=100)
        o2 = self.order_store.create('buy', 'WSCN', 10, price=90)
        o3 = self.order_store.create('sell', 'WSCN', 20, price=95)
        o4 = self.order_store.create('buy', 'WSCN', 10, price=96)
        o5 = self.order_store.create('buy', 'WSCN', 10, price=100)
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

        o6 = self.order_store.create('sell', 'WSCN', 5, price=80)
        self.queue.put(NewOrderEvent(o6.id))
        self.queue.put(CancelOrderEvent(o2.id))
        time.sleep(0.1)
        trades = self.trade_store.get(o2.id)
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].status, 'partial_done')
        self.assertEqual(trades[1].status, 'left_cancel')
