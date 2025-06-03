import asyncio
import uuid
import logging

from .pool_interface import IVSpherePoolManager
from .pending_counter import pending
from .tasks import CLONE_QUEUE, CloneTask
from .config import cfg


class Replenisher:
    def __init__(self, pool: IVSpherePoolManager):
        self.logger = logging.getLogger(__class__.__name__)
        self.pool = pool
        self._stop = asyncio.Event()

        self.min_ready_vm  = cfg.min_ready_vm
        self.max_ready_vm  = cfg.max_ready_vm
        self.batch_size    = cfg.batch_size
        self.check_interval = cfg.check_interval
        self.fault_ttl_min = cfg.fault_vm_ttl_minutes

    # — graceful-stop —
    def stop(self):
        self._stop.set()

    # — main loop —
    async def run(self):
        self.logger.info(
            "Replenisher online (low=%s high=%s)",
            self.min_ready_vm,
            self.max_ready_vm,
        )
        while not self._stop.is_set():
            await self._cleanup_fault_vms()

            ready = await self.pool.count_ready()
            pending_count = await pending.value()
            total = ready + pending_count

            self.logger.info(
                "Ready VMs: %s, Pending VMs: %s (total %s)",
                ready,
                pending_count,
                total,
            )

            # Не превышаем верхнюю границу
            if total < self.min_ready_vm:
                need = min(self.batch_size, self.max_ready_vm - total)
                self.logger.warning(
                    "Need %s new VM (ready %s, pending %s)",
                    need,
                    ready,
                    pending_count,
                )
                for _ in range(need):
                    await CLONE_QUEUE.put(CloneTask(uuid.uuid4()))
                    await pending.inc()

            await asyncio.sleep(self.check_interval)

    # — удаляем «битые / застрявшие» ВМ —
    async def _cleanup_fault_vms(self):
        if not hasattr(self.pool, "delete_vm_by_name"):
            self.logger.warning(
                "delete_vm_by_name не реализован — уборка битых ВМ невозможна"
            )
            return

        try:
            fault_vms = getattr(self.pool, "list_fault_vms", lambda: [])()
            init_vms  = getattr(
                self.pool, "list_init_vms", lambda _ttl: []
            )(self.fault_ttl_min)

            victims = set(fault_vms) | set(init_vms)
            if victims:
                self.logger.warning(
                    "Найдено %d битых/зависших ВМ, удаляем…", len(victims)
                )

            for vm_name in victims:
                try:
                    self.pool.delete_vm_by_name(vm_name)
                    self.logger.info("Удалена ВМ %s", vm_name)
                except Exception as e:
                    self.logger.exception("Ошибка при удалении %s: %s", vm_name, e)

        except Exception as e:
            self.logger.exception("Ошибка в _cleanup_fault_vms: %s", e)
