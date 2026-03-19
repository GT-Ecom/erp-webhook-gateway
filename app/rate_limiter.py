import time
import asyncio
from collections import defaultdict
from typing import Dict, Tuple
import logging

from .config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key: str) -> Tuple[bool, int]:
        """Check if request is allowed for the given key
        
        Args:
            key: Identifier (e.g., shop_domain)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            self._requests[key] = [
                ts for ts in self._requests[key] if ts > window_start
            ]
            
            if len(self._requests[key]) >= self.max_requests:
                oldest = self._requests[key][0] if self._requests[key] else now
                retry_after = int(oldest + self.window_seconds - now) + 1
                return False, retry_after
            
            self._requests[key].append(now)
            return True, 0
    
    async def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """Remove old entries to prevent memory growth"""
        async with self._lock:
            now = time.time()
            cutoff = now - max_age_seconds
            for key in list(self._requests.keys()):
                self._requests[key] = [
                    ts for ts in self._requests[key] if ts > cutoff
                ]
                if not self._requests[key]:
                    del self._requests[key]


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter (singleton)"""
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_per_shop,
            window_seconds=settings.rate_limit_window_seconds
        )
    
    return _rate_limiter
