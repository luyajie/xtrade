from datetime import datetime
import heapq
import logging
import threading

from .event import NewOrderEvent, CancelOrderEvent
from .symbol import get_symbol_price_range, get_symbol_price


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
    def __init__(self, message_queue, trade_store, order_store, timeout=1,
                 trade_log_file='trade.log', order_log_file='order.log', depth_log_file='depth.log'):
        super().__init__()
        self.daemon = True
        self._buy_queue_map = {}  # symbol_id => []
        self._sell_queue_map = {}  # symbol_id => []
        self._symbol_price_map = {}  # symbol_id => price
        self._order_map = {}  # unfinished orders: order_id => order
        self.msg_queue = message_queue  # read_only
        self.trade_store = trade_store  # write_only
        self.order_store = order_store  # read_only
        self.timeout = timeout
        self.trade_log_file = trade_log_file
        self.order_log_file = order_log_file
        self.depth_log_file = depth_log_file

    def run(self):
        while True:
            try:
                event = self._get_event()
                if isinstance(event, NewOrderEvent):
                    order = self._get_order(event.order_id)
                    self._add_order(order)
                    self._running_trade(order.symbol)
                elif isinstance(event, CancelOrderEvent):
                    self._remove_order(event.order_id)
                elif event == 'timeout':
                    LOG.debug('timeout')
                else:
                    LOG.warning('unknonw event: %s', event)
            except Exception as e:
                LOG.exception(e)
            finally:
                try:
                    self._write_depth_log()
                except Exception as e:
                    LOG.error('error when write depth log: %s', e, exc_info=True)

    def _get_order(self, order_id):
        """Get the original order."""
        return self.order_store.get(order_id)

    def _get_event(self):
        try:
            return self.msg_queue.get(timeout=self.timeout)
        except Exception as e:
            # todo: more specific error handler
            return 'timeout'

    def _add_order(self, order):
        self._order_map[order.id] = order
        if order.is_sell:
            sell_queue = self._sell_queue_map.setdefault(order.symbol, [])
            heapq.heappush(sell_queue, order)
            self._sell_queue_map[order.symbol] = sell_queue
        else:
            buy_queue = self._buy_queue_map.setdefault(order.symbol, [])
            heapq.heappush(buy_queue, order)
            self._buy_queue_map[order.symbol] = buy_queue

    def _remove_order(self, order_id):
        order = self._order_map.pop(order_id, None)
        if order is None:
            LOG.warning('Order<%s> already finished', order_id)
            return
        LOG.info('%s canceled', order)
        orig_order = self._get_order(order_id)
        trade = Trade.cancel(order, orig_order.amount)
        self.trade_store.save(trade)
        self._write_order_log(trade)

    def _running_trade(self, symbol_id):
        """Check all the BuyOrders and the SellOrders until no trade is available."""
        buy_queue = self._buy_queue_map.setdefault(symbol_id, [])
        sell_queue = self._sell_queue_map.setdefault(symbol_id, [])
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
        # fixme: freeze the `symbol` when the highest or the lowest limit reached
        # price changed
        self._symbol_price_map[buy_order.symbol] = price
        self._write_trade_log(price, amount)
        LOG.debug('Trade available. amount: %s, price: %s', amount, price)
        buy_trade = Trade.do(buy_order, price, amount)
        self.trade_store.save(buy_trade)
        buy_order = buy_order.reduce(amount)
        self._write_order_log(buy_trade)
        if buy_trade.is_done:
            self._order_map.pop(buy_order_id)
        else:
            self._order_map[buy_order_id] = buy_order
        sell_trade = Trade.do(sell_order, price, amount)
        self.trade_store.save(sell_trade)
        sell_order = sell_order.reduce(amount)
        self._write_order_log(sell_trade)
        if sell_trade.is_done:
            self._order_map.pop(sell_order_id)
        else:
            self._order_map[sell_order.id] = sell_order
        return buy_order, sell_order

    def get_trade_price(self, buy_order, sell_order):
        """Return the price for this trade."""
        min_price, max_price = get_symbol_price_range(sell_order.symbol)
        if sell_order.price >= min_price:
            return sell_order.price
        if buy_order.price <= max_price:
            return buy_order.price
        return self._symbol_price_map.get(sell_order.symbol, get_symbol_price(sell_order.symbol))

    def _write_trade_log(self, price, amount):
        with open(self.trade_log_file, 'a') as f:
            f.write('%s %s %s\n' % (datetime.now(), price, amount))

    def _write_order_log(self, order_trade):
        with open(self.order_log_file, 'a') as f:
            f.write(
                '%(timestamp)s %(order_id)s %(order_type)s %(price)s '
                '%(amount)s %(status)s\n' % order_trade.__dict__)

    def _write_depth_log(self):
        def write_log(title_, queue_):
            with open(self.depth_log_file, 'a') as f_:
                f_.write('%s\n' % (title_,))
                for i in range(min(len(queue_), 20)):
                    order = heapq.heappop(queue_)
                    f_.write('%(id)s %(timestamp)s %(symbol)s %(type)s %(price)s %(amount)s\n' % dict(
                        id=order.id, timestamp=order.timestamp, symbol=order.symbol, type=order.TYPE,
                        price=order.price, amount=order.amount))
        symbols_list = list(self._buy_queue_map.keys()) + list(self._sell_queue_map.keys())
        symbols_list = sorted(set(symbols_list))
        for symbol_id in symbols_list:
            title = '*** symbol: %s,  buy order' % symbol_id
            queue = self._buy_queue_map.get(symbol_id, [])[:]
            write_log(title, queue)
            title = '*** symbol: %s,  sell order' % symbol_id
            queue = self._sell_queue_map.get(symbol_id, [])[:]
            write_log(title, queue)

        with open(self.depth_log_file, 'a') as f:
            f.write('\n\n')
