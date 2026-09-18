"""Cache Redis opcional para respostas JSON da API."""

import json
import os


class RedisCache:
    def __init__(self, url=None, ttl=300):
        self.url = url or os.environ.get("REDIS_URL", "")
        self.ttl = ttl
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
            return None
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    def set(self, key, value):
        if not self.client:
            return
        try:
            self.client.setex(key, self.ttl, json.dumps(value, ensure_ascii=False))
        except Exception:
            pass

    def invalidate(self, *keys):
        if not self.client or not keys:
            return
        try:
            self.client.delete(*keys)
        except Exception:
            pass
