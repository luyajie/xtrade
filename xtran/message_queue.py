import queue


class MessageQueue(object):
    def get(self):
        raise NotImplementedError()

    def put(self, event):
        raise NotImplementedError()


class LocalQueue(MessageQueue):
    def __init__(self):
        self._queue = queue.Queue()

    def get(self):
        return self._queue.get()

    def put(self, event):
        self._queue.put(event)



