import asyncio
from vm_refiller.builder_test import builder_pool
from vm_refiller.vsphere_pool_test import VSpherePoolManager
from vm_refiller.tasks import CLONE_QUEUE, CloneTask
import uuid
import pytest

@pytest.mark.asyncio
async def test_builder_pool_smoke(tmp_path):
    """Проверяем, что процесс‑воркер завершается и pending падает до нуля."""
    pool = VSpherePoolManager()       # mock‑реализация: чтение/запись в vms.txt
    await CLONE_QUEUE.put(CloneTask(uuid.uuid4()))

    # запускаем pool и стопаем после первой готовой VM
    task = asyncio.create_task(builder_pool(pool))
    await asyncio.wait_for(CLONE_QUEUE.join(), timeout=10)
    task.cancel()     # корутина‑демон, останавливаем вручную
