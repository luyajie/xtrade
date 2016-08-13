from datetime import datetime
import heapq
from unittest import TestCase

from xtrade.app import app
from xtrade.db import db
from xtrade.order import MemOrderStore, DBOrderStore


class TestOrder(TestCase):
    def setUp(self):
        self.store = MemOrderStore()

    def test_can_buy(self):
        buy_order = self.store.create('buy', symbol='mu', amount=10, price=100)
        sell_order = self.store.create('sell', symbol='mu', amount=10, price=110)
        self.assertFalse(buy_order.can_buy(sell_order))
        sell_order = self.store.create('sell', symbol='mu', amount=10, price=90)
        self.assertTrue(buy_order.can_buy(sell_order))
        sell_order = self.store.create('sell', symbol='mu', amount=10, price=100)
        self.assertTrue(buy_order.can_buy(sell_order))
        sell_order = self.store.create('market_sell', symbol='mu', amount=10)
        self.assertTrue(buy_order.can_buy(sell_order))

    def test_sort(self):
        now = datetime.now()
        queue = []

        o1 = self.store.create('sell', 'mu', 10, price=100)
        o1.timestamp = now.replace(year=2000)
        o2 = self.store.create('sell', 'mu', 10, price=100)
        o3 = self.store.create('sell', 'mu', 10, price=101)
        o4 = self.store.create('market_sell', 'mu', 10)
        o5 = self.store.create('market_sell', 'mu', 10)
        heapq.heappush(queue, o1)
        heapq.heappush(queue, o2)
        heapq.heappush(queue, o3)
        heapq.heappush(queue, o4)
        heapq.heappush(queue, o5)
        self.assertEqual(heapq.heappop(queue), o4)
        self.assertEqual(heapq.heappop(queue), o5)
        self.assertEqual(heapq.heappop(queue), o1)
        self.assertEqual(heapq.heappop(queue), o2)
        self.assertEqual(heapq.heappop(queue), o3)


class TestDBOrderStore(TestCase):
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

    def test_create_and_get(self):
        store = DBOrderStore(db)
        order = store.create('buy', symbol='mu', amount=10, price=100)
        self.assertEqual(order.id, 1)
        self.assertEqual(order.TYPE, 'buy')

        another_store = DBOrderStore(db)
        order = another_store.get(order.id)
        self.assertEqual(order.TYPE, 'buy')
        self.assertEqual(order.symbol, 'mu')
        self.assertEqual(order.amount, 10)
        self.assertEqual(order.price, 100)

        # order id should be increased
        another_order = store.create('sell', symbol='mu', amount=10, price=100)
        self.assertEqual(another_order.id, 2)
