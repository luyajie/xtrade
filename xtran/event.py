class Event(object):
    def __init__(self, type_, order):
        self.type_ = type_
        self.order = order

    @property
    def is_new(self):
        return self.type_ == 'new'

    @property
    def is_cancel(self):
        return self.type_ == 'cancel'

    def __repr__(self):
        return "%s<%s, %s>" % (self.__class__.__name__, self.type_, self.order)


