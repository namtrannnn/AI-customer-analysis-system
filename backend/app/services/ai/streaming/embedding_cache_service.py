from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Dict, Iterable, Optional
import time


@dataclass(slots=True)
class CacheEntry:
    value: Any
    expires_at: float


class EmbeddingMemoryCacheService:
    """AI-05: cache embedding/profile gallery trong RAM, hỗ trợ TTL + LRU."""

    def __init__(self, max_entries: int = 4096, ttl_seconds: float = 900.0) -> None:
        self.max_entries = max(1, int(max_entries))
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self._items: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else max(1.0, float(ttl_seconds))
        with self._lock:
            self._items[key] = CacheEntry(value=value, expires_at=time.monotonic() + ttl)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def get_or_load(self, key: str, loader: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = loader()
        self.set(key, value)
        return value

    def preload(self, values: Dict[str, Any]) -> None:
        for key, value in values.items():
            self.set(str(key), value)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in [k for k in self._items if k.startswith(prefix)]:
                self._items.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {"entries": len(self._items), "max_entries": self.max_entries}
