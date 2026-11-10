"""Performance benchmarks and optimization validation."""

import time
import hashlib
import hmac
from src.masking.strategies import hmac_token


def test_hmac_caching_optimization():
    """Verify that LRU caching of repeated customer IDs speeds up tokenization significantly."""
    repeated_keys = [f"CUST-{i:04d}" for i in range(500)] * 50  # 25,000 keys with repeats
    salt = "benchmark-salt"

    # Baseline uncached direct computation
    t0 = time.perf_counter()
    for k in repeated_keys:
        val_bytes = k.encode("utf-8")
        salt_bytes = salt.encode("utf-8")
        _ = hmac.new(salt_bytes, val_bytes, hashlib.sha256).hexdigest()[:16]
    uncached_duration = time.perf_counter() - t0

    # Optimized cached execution
    t1 = time.perf_counter()
    for k in repeated_keys:
        _ = hmac_token(k, salt=salt)
    cached_duration = time.perf_counter() - t1

    # Assert optimization is significantly faster
    speedup = uncached_duration / cached_duration if cached_duration > 0 else 1.0
    assert speedup > 1.5, f"Expected speedup > 1.5x, got {speedup:.2f}x"

