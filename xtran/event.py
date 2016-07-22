class Event(object):
    pass


class OrderEvent(Event):
    def __init__(self, order_id):
        self.order_id = order_id


class NewOrderEvent(OrderEvent):
    pass


class CancelOrderEvent(OrderEvent):
    pass


