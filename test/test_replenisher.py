import asyncio
import uuid
import pytest
from vm_refiller.replenisher import Replenisher
from vm_refiller.tasks import CLONE_QUEUE
from vm_refiller.pending_counter import pending

@pytest.mark.asyncio
async def test_replenisher_triggers_clone(dummy_pool, mocker):
    dummy_pool.count_ready = lambda: 0
    rep = Replenisher(dummy_pool)

    # запустим репленишер, но остановим через 0.2 сек
    async def stopper():
        await asyncio.sleep(0.2)
        rep.stop()
    asyncio.create_task(stopper())
    await rep.run()

    assert await pending.value() == 0      # после stop() очередь дождалась
    assert not CLONE_QUEUE.empty()
    task = await CLONE_QUEUE.get()
    assert isinstance(task.job_id, uuid.UUID)
