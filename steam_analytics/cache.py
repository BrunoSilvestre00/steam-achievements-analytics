"""Caches para respostas JSON da API.

Redis continua sendo usado no Docker. A execução local pode funcionar sem
qualquer serviço externo usando o cache TTL em memória.
"""

import json
import os
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


class RedisCache:
    def __init__(self, url=None, ttl=300):
        self.url = url or os.environ.get("REDIS_URL", "")
        self.ttl = ttl
        self.memory = MemoryCache(ttl=ttl)
        self.client = None
        if self.url:
            try:
                import redis

                self.client = redis.Redis.from_url(
                    self.url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
                )
            except Exception:
                self.client = None

    def get(self, key):
        if not self.client:
            return self.memory.get(key)
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception:
            return self.memory.get(key)

    def set(self, key, value):
        if not self.client:
            self.memory.set(key, value)
            return
        try:
            self.client.setex(key, self.ttl, json.dumps(value, ensure_ascii=False))
        except Exception:
            self.memory.set(key, value)

    def invalidate(self, *keys):
        self.memory.invalidate(*keys)
        if not self.client or not keys:
            return
        try:
            self.client.delete(*keys)
        except Exception:
            pass
