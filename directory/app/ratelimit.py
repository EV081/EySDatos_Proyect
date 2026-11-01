"""Límite de solicitudes en memoria, por IP y por grupo de rutas. La IP solo vive aquí, en memoria y durante
la ventana: no se guarda en la base ni se registra (C-05)."""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, window: float = 60.0, clock=time.monotonic):
        self._window, self._clock = window, clock
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, bucket: str, client: str, limit: int) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[(bucket, client)]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:  # evita que crezca sin límite con muchas IPs
                self._hits = defaultdict(deque, {k: v for k, v in self._hits.items() if v})
            return True
