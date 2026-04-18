"""TTL 적용 LRU 캐시 — 동일 incident 반복 분석 호출 방지."""
import hashlib
import json
import time
from collections import OrderedDict
from typing import Optional


class LRUCache:
    """Simple ordered-dict LRU cache with TTL."""

    def __init__(self, maxsize: int = 64, ttl_seconds: float = 300.0):
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[dict]:
        if key not in self._store:
            return None
        ts, val = self._store[key]
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return val

    def put(self, key: str, value: dict) -> None:
        self._store[key] = (time.time(), value)
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def __len__(self) -> int:
        return len(self._store)


def make_cache_key(incident_data: dict) -> str:
    """Incident 상태를 결정짓는 핵심 필드만으로 sha256 hash 생성."""
    key_parts = {
        "step_id": incident_data.get("step_id"),
        "anomaly_value": incident_data.get("anomaly", {}).get("value"),
        "anomaly_type": incident_data.get("anomaly", {}).get("anomaly_type"),
        "top_cause": incident_data.get("diagnosis", {}).get("top_cause"),
        "confidence": incident_data.get("diagnosis", {}).get("confidence"),
        "recovery_success": incident_data.get("recovery", {}).get("success"),
        "post_yield": incident_data.get("recovery", {}).get("post_yield"),
    }
    raw = json.dumps(key_parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
