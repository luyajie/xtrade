from datetime import datetime
import heapq
from unittest import TestCase

from xtrade.order import Order


class TestOrder(TestCase):
    def test_can_buy(self):
        buy_order = Order.factory('buy', symbol='mu', amount=10, price=100)
        sell_order = Order.factory('sell', symbol='mu', amount=10, price=110)
        self.assertFalse(buy_order.can_buy(sell_order))
        sell_order = Order.factory('sell', symbol='mu', amount=10, price=90)
        self.assertTrue(buy_order.can_buy(sell_order))
        sell_order = Order.factory('sell', symbol='mu', amount=10, price=100)
        self.assertTrue(buy_order.can_buy(sell_order))
        sell_order = Order.factory('market_sell', symbol='mu', amount=10)
        self.assertTrue(buy_order.can_buy(sell_order))

    def test_sort(self):
        now = datetime.now()
        queue = []

        o1 = Order.factory('sell', 'mu', 10, price=100)
        o1.timestamp = now.replace(year=2000)
        o2 = Order.factory('sell', 'mu', 10, price=100)
        o3 = Order.factory('sell', 'mu', 10, price=101)
        o4 = Order.factory('market_sell', 'mu', 10)
        o5 = Order.factory('market_sell', 'mu', 10)
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
