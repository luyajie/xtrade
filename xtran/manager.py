from datetime import datetime
import heapq
import logging
import threading

from .event import NewOrderEvent, CancelOrderEvent


LOG = logging.getLogger(__name__)

_id = 0


def get_trade_id():
    global _id
    _id += 1
    return _id


class Trade(object):
    def __init__(self, id_, order_id, order_type, price, amount, status):
        self.id = id_
        self.order_id = order_id
        self.order_type = order_type
        self.price = price
        self.amount = amount
        self.status = status
        self.timestamp = datetime.now()

    @staticmethod
    def do(order, price, amount):
        id_ = get_trade_id()
        status = 'all_done'
        if order.amount > amount:
            status = 'partial_done'
        return Trade(id_, order.id, order.TYPE, price, amount, status)

    @staticmethod
    def cancel(order, orig_amount):
        id_ = get_trade_id()
        status = 'left_cancel'
        if order.amount >= orig_amount:
            status = 'all_cancel'
        return Trade(id_, order.id, order.TYPE, order.price, order.amount, status)

    @property
    def is_done(self):
        return self.status.startswith('all')

    @property
    def is_canceled(self):
        return self.status.endswith('cancel')

    def __repr__(self):
        return "%s<%s, %s, %s, %s, %s>" % (
            self.__class__.__name__, self.order_id, self.order_type, self.price, self.amount, self.status)


class TradeStore(object):
    def __init__(self):
        self._data = {}  # order_id => [Trade]

    def save(self, trade):
        self._data.setdefault(trade.order_id, []).append(trade)

    def get(self, order_id):
        return self._data.get(order_id, [])


class TradeManager(threading.Thread):
    def __init__(self, message_queue, trade_store, order_store):
        super().__init__()
        self.daemon = True
        self._buy_queue = []
        self._sell_queue = []
        self._order_map = {}  # unfinished orders: order_id => order
        self.msg_queue = message_queue  # read_only
        self.trade_store = trade_store  # write_only
        self.order_store = order_store  # read_only

    def run(self):
        while True:
            try:
                event = self._get_event()
                if isinstance(event, NewOrderEvent):
                    order = self._get_order(event.order_id)
                    self._add_order(order)
                    self._running_trade()
                elif isinstance(event, CancelOrderEvent):
                    self._remove_order(event.order_id)
                else:
                    LOG.warning('unknonw event: %s', event)
            except Exception as e:
                LOG.exception(e)

    def _get_order(self, order_id):
        """Get the original order."""
        return self.order_store.get(order_id)

    def _get_event(self):
        return self.msg_queue.get()

    def _add_order(self, order):
        self._order_map[order.id] = order
        if order.is_sell:
            heapq.heappush(self._sell_queue, order)
        else:
            heapq.heappush(self._buy_queue, order)

    def _remove_order(self, order_id):
        order = self._order_map.pop(order_id, None)
        if order is None:
            LOG.warning('Order<%s> already finished', order_id)
            return
        LOG.info('%s canceled', order)
        orig_order = self._get_order(order_id)
        self.trade_store.save(Trade.cancel(order, orig_order.amount))

    def _running_trade(self):
        """Check all the BuyOrders and the SellOrders until no trade is available."""
        buy_queue, sell_queue = self._buy_queue, self._sell_queue
        while buy_queue and sell_queue:
            buy_order = self._pop_order(buy_queue)
            if buy_order is None:
                break
            sell_order = self._pop_order(sell_queue)
            if sell_order is None:
                self._push_order(buy_queue, buy_order)
                break
            buy_order, sell_order = self._do_trade(buy_order, sell_order)
            LOG.debug('buy: %s, sell: %s', buy_order, sell_order)
            if buy_order and sell_order:
                LOG.debug('no transaction available')
                self._push_order(buy_queue, buy_order)
                self._push_order(sell_queue, sell_order)
                break
            elif buy_order:
                self._push_order(buy_queue, buy_order)
                continue
            elif sell_order:
                self._push_order(sell_queue, sell_order)
                continue
            else:
                # the amount just equal
                pass

    def _pop_order(self, queue):
        """Pop an order from the queue, which is meant to be of highest priority.
        """
        while queue:
            order = heapq.heappop(queue)
            if order.id not in self._order_map:
                LOG.debug('%s: ignored, already canceled.', order)
                continue
            return order

    def _push_order(self, queue, order):
        """Push an order back into the queue."""
        heapq.heappush(queue, order)

    def _do_trade(self, buy_order, sell_order):
        """Trade happen when the price of BuyOrder is higher than that of the SellOrder.
        """
        if not buy_order.can_buy(sell_order):
            LOG.debug('%s less than %s', buy_order, sell_order)
            return buy_order, sell_order
        buy_order_id, sell_order_id = buy_order.id, sell_order.id
        amount = min(sell_order.amount, buy_order.amount)
        price = self.get_trade_price(buy_order, sell_order)
        LOG.debug('Trade available. amount: %s, price: %s', amount, price)
        buy_trade = Trade.do(buy_order, price, amount)
        self.trade_store.save(buy_trade)
        buy_order = buy_order.reduce(amount)
        if buy_trade.is_done:
            self._order_map.pop(buy_order_id)
        else:
            self._order_map[buy_order_id] = buy_order
        sell_trade = Trade.do(sell_order, price, amount)
        self.trade_store.save(sell_trade)
        sell_order = sell_order.reduce(amount)
        if sell_trade.is_done:
            self._order_map.pop(sell_order_id)
        else:
            self._order_map[sell_order.id] = sell_order
        return buy_order, sell_order

    @staticmethod
    def get_trade_price(buy_order, sell_order):
        """Return the price for this trade."""
        # todo: current price should return when both sell_order and buy_order are `market'
        return sell_order.price
