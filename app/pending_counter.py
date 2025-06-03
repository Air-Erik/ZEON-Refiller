# vm_refiller/pending_counter.py
import asyncio


class PendingCounter:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._count = 0

    async def inc(self):
        async with self._lock:
            self._count += 1

    async def dec(self):
        async with self._lock:
            self._count = max(0, self._count - 1)

    async def value(self):
        async with self._lock:
            return self._count

    async def reset_to(self, value: int):
        """Аварийный пересчёт счётчика из health-check-скрипта."""
        async with self._lock:
            self.   _count = max(0, int(value))


pending = PendingCounter()
