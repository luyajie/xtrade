import heapq
import logging
import threading

from .event import Event


LOG = logging.getLogger(__name__)


class TransactionManager(threading.Thread):
    def __init__(self, message_queue):
        super().__init__()
        self._buy_queue = []
        self._sell_queue = []
        self._canceled = set()
        self.msg_queue = message_queue

    def run(self):
        while True:
            try:
                event = self._get_event()
                assert isinstance(event, Event)
                if event.is_new:
                    self._add_order(event.order)
                    self._update()
                elif event.is_cancel:
                    self._remove_order(event.order)
                else:
                    LOG.warning('unknonw event: %s', event)
            except Exception as e:
                LOG.exception(e)

    def _get_event(self):
        return self.msg_queue.get()

    def _add_order(self, order):
        print(order, order.is_sell)
        if order.is_sell:
            heapq.heappush(self._sell_queue, order)
        else:
            heapq.heappush(self._buy_queue, order)

    def _remove_order(self, order):
        self._canceled.add(order)

    def _update(self):
        buy_queue, sell_queue = self._buy_queue, self._sell_queue
        while buy_queue and sell_queue:
            buy_order = self.pop_order(buy_queue)
            if buy_order is None:
                break
            sell_order = self.pop_order(sell_queue)
            if sell_order is None:
                self.push_order(buy_order)
                break
            buy_order, sell_order = self._make_transaction(buy_order, sell_order)
            LOG.debug('buy: %s, sell: %s', buy_order, sell_order)
            if buy_order and sell_order:
                LOG.debug('no transaction available')
                break
            elif buy_order:
                self.push_order(buy_queue, buy_order)
                continue
            elif sell_order:
                self.push_order(sell_queue, sell_order)
            else:
                # the amount just equal
                pass

    def pop_order(self, queue):
        while queue:
            order = heapq.heappop(queue)
            if order in self._canceled:
                self._canceled.remove(order)
                continue
            return order

    def push_order(self, queue, order):
        heapq.heappush(queue, order)

    def _make_transaction(self, buy_order, sell_order):
        if buy_order < sell_order:
            LOG.debug('%s less than %s', buy_order, sell_order)
            return buy_order, sell_order
        amount = min(sell_order.amount, buy_order.amount)
        price = sell_order.price
        # todo: record the transaction
        LOG.debug('transaction happen. amount: %s, price: %s', amount, price)
        buy_order = buy_order.reduce(amount)
        sell_order = sell_order.reduce(amount)
        return buy_order, sell_order
