import json
import logging
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger("brs.redis")
_client = None
_failed = False


def get_redis():
    """Return Redis client or None when unavailable (graceful degrade)."""
    global _client, _failed
    if not settings.REDIS_ENABLED or _failed:
        return None
    if _client is not None:
        return _client
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        _client = client
        return _client
    except Exception as exc:
        logger.warning("Redis unavailable, caching disabled: %s", exc)
        _failed = True
        return None


def cache_get_json(key: str) -> Optional[Any]:
    client = get_redis()
    if not client:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


def cache_set_json(key: str, value: Any, ttl: int) -> bool:
    client = get_redis()
    if not client:
        return False
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


def cache_header(hit: bool) -> str:
    return "HIT" if hit else "MISS"
