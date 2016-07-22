from datetime import datetime


class Order(object):
    def __init__(self, symbol, amount, timestamp, price=None):
        self.symbol = symbol
        self.amount = amount
        self.price = price
        self.timestamp = timestamp

    @property
    def type(self):
        raise NotImplementedError()

    def __gt__(self, other):
        return self.price > other.price

    def __ge__(self, other):
        return self.price >= other.price

    def __lt__(self, other):
        print(self, other, "<", self.price < other.price)
        return self.price < other.price

    def __le__(self, other):
        print(self, other, "<=", self.price <= other.price)
        return self.price <= other.price

    def __cmp__(self, other):
        """Compare with another order, used when sorting.

        Comparing based on the following:
        * price
        * timestamp
        """
        if self.price < other.price:
            return -1
        elif self.price > other.price:
            return 1
        if self.timestamp <= other.timestamp:
            return 1
        else:
            return -1

    def reduce(self, amount):
        assert amount <= self.amount, 'expected amount <= %s, got: %s' % (self.amount, amount)
        if self.amount == amount:
            return None
        amount = self.amount - amount
        return self.__class__(self.symbol, amount, self.timestamp, self.price)

    def __str__(self):
        return "%s<%s, %s, %s>" % (self.__class__.__name__, self.price, self.amount, self.timestamp)
    __repr__ = __str__

    @property
    def is_sell(self):
        return isinstance(self, (SellOrder, MarketSellOrder))

    @property
    def is_buy(self):
        return isinstance(self, (BuyOrder, MarketBuyOrder))

    @staticmethod
    def factory(type_, symbol, amount, price=None):
        now = datetime.now()
        if type_ == 'sell':
            return SellOrder(symbol, amount, now, price=price)
        elif type_ == 'market_sell':
            return MarketSellOrder(symbol, amount, now)
        elif type_ == 'buy':
            return BuyOrder(symbol, amount, now, price=price)
        elif type_ == 'market_buy':
            return MarketBuyOrder(symbol, amount, now)
        else:
            raise Exception('invalid type: %s' % (type_,))


class SellOrder(Order):
    @property
    def type(self):
        return "sell"


class BuyOrder(Order):
    @property
    def type(self):
        return "buy"


class MarketSellOrder(Order):
    @property
    def type(self):
        return "market_sell"


class MarketBuyOrder(Order):
    @property
    def type(self):
        return "market_buy"
