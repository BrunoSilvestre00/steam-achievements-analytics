"""Cache TTL local usado pela aplicação desktop."""

import threading
import time


class MemoryCache:
    """Cache local, volátil e seguro para as requisições do processo."""

    def __init__(self, ttl=300):
        self.ttl = ttl
        self._values = {}
        self._lock = threading.Lock()

    def get(self, key):
        now = time.monotonic()
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            return value

    def set(self, key, value):
        with self._lock:
            self._values[key] = (time.monotonic() + self.ttl, value)

    def invalidate(self, *keys):
        if not keys:
            return
        with self._lock:
            for key in keys:
                self._values.pop(key, None)

