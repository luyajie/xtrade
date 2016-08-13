from datetime import datetime
import sys

from .db import db, OrderModel
from .exc import InvalidRequest


_support_types = {}


class InvalidOrderType(InvalidRequest):
    pass


class OrderNotFound(Exception):
    pass


class OrderStore(object):

    @classmethod
    def instance(cls):
        try:
            return cls._instance
        except AttributeError:
            raise Exception('No global instance installed for %s' % (cls.__name__,))

    def install(self):
        self.__class__._instance = self
        return self

    def get(self, order_id):
        raise NotImplementedError()

    def create(self, type_, symbol, amount, price=None):
        order = self._factory(type_, symbol, amount, price)
        self._save(order)
        return order

    def _save(self, order):
        raise NotImplementedError()

    def _factory(self, type_, symbol, amount, price=None):
        if type_ not in _support_types:
            raise InvalidOrderType(type_)
        now = datetime.now()
        order_id = self.next_id
        klass = _support_types[type_]
        return klass(order_id, symbol, amount, now, price)

    @property
    def next_id(self):
        raise NotImplementedError()


class MemOrderStore(OrderStore):

    def __init__(self):
        self._data = {}
        self._id = 0

    def _save(self, order):
        self._data[order.id] = order

    def get(self, order_id):
        try:
            return self._data[order_id]
        except KeyError:
            raise OrderNotFound(order_id)

    @property
    def next_id(self):
        self._id += 1
        return self._id


class DBOrderStore(OrderStore):
    def __init__(self, db):
        self.db = db

    @property
    def next_id(self):
        order = self.db.session.query(OrderModel).order_by(OrderModel.id.desc()).first()
        current_id = order and order.id or 0
        return current_id + 1

    def get(self, order_id):
        order_model = self.db.session.query(OrderModel).filter(OrderModel.id == order_id).one()
        klass = _support_types[order_model.type]
        return klass(order_id, order_model.symbol, order_model.amount,
                     order_model.timestamp, order_model.price)

    def _save(self, order):
        self.db.session.add(
            OrderModel(id=order.id, symbol=order.symbol, amount=order.amount,
                       type=order.TYPE, price=order.price, timestamp=order.timestamp))
        self.db.session.commit()


class Order(object):
    TYPE = ''
    
    def __init__(self, id_, symbol, amount, timestamp, price=None):
        self.id = id_
        self.symbol = symbol
        self.amount = amount
        self.timestamp = timestamp
        self._price = price
        
    @property
    def price(self):
        return self._price

    def reduce(self, amount):
        assert amount <= self.amount, 'expected amount <= %s, got: %s' % (self.amount, amount)
        if self.amount == amount:
            return None
        amount = self.amount - amount
        return self.__class__(self.id, self.symbol, amount, self.timestamp, self.price)

    def __str__(self):
        return "%s<%s, %s, %s>" % (self.__class__.__name__, self.price, self.amount, self.timestamp)
    __repr__ = __str__

    @property
    def is_sell(self):
        return isinstance(self, SellOrder)

    @property
    def is_buy(self):
        return isinstance(self, BuyOrder)

    @classmethod
    def register(cls):
        assert issubclass(cls, Order)
        _support_types[cls.TYPE] = cls


class SellOrder(Order):
    TYPE = 'sell'

    def __lt__(self, other):
        """Compare with another order, used when sorting.

        Comparing based on the following:
        * price: lower price win
        * timestamp: if price is the same, the first one win
        """
        if self.price < other.price:
            return True
        elif self.price > other.price:
            return False
        return self.timestamp <= other.timestamp
SellOrder.register()


class BuyOrder(Order):
    TYPE = 'buy'

    def __lt__(self, other):
        """Compare with another order, used when sorting.

        Comparing based on the following:
        * price: higher price win
        * timestamp: if price is the same, the first one win
        """
        if self.price > other.price:
            return -1
        elif self.price < other.price:
            return 1
        if self.timestamp <= other.timestamp:
            return -1
        else:
            return 1

    def can_buy(self, sell_order):
        assert isinstance(sell_order, SellOrder),\
            '%s can only buy a sell order. got: %s' % (self, sell_order)
        return self.price >= sell_order.price
BuyOrder.register()


class MarketSellOrder(SellOrder):
    TYPE = 'market_sell'

    @property
    def price(self):
        return -1 - sys.maxsize
MarketSellOrder.register()


class MarketBuyOrder(BuyOrder):
    TYPE = 'market_buy'

    @property
    def price(self):
        return sys.maxsize
MarketBuyOrder.register()

