"""Diskcache wrapper for literature API responses."""
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import diskcache
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _get_cache(cache_dir: Path | None = None):
    if not _AVAILABLE:
        return None
    from bgclens.core.config import get_settings
    d = cache_dir or get_settings().cache_dir / "literature"
    d.mkdir(parents=True, exist_ok=True)
    return diskcache.Cache(str(d))


def cache_key(method_terms: list[str], topic_terms: list[str], window_years: int) -> str:
    payload = json.dumps(
        {"m": sorted(method_terms), "t": sorted(topic_terms), "w": window_years},
        sort_keys=True,
    )
    return "lit_" + hashlib.sha256(payload.encode()).hexdigest()[:20]


def get_cached(key: str, ttl_days: int = 30, cache_dir: Path | None = None) -> Any | None:
    cache = _get_cache(cache_dir)
    if cache is None:
        return None
    try:
        return cache.get(key)
    except Exception:
        return None


def set_cached(key: str, value: Any, ttl_days: int = 30, cache_dir: Path | None = None) -> None:
    cache = _get_cache(cache_dir)
    if cache is None:
        return
    try:
        cache.set(key, value, expire=ttl_days * 86400)
    except Exception:
        pass
