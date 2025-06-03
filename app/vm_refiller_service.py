import asyncio
import signal
import logging

from .replenisher import Replenisher
from .builder import builder_pool
from .tasks import CLONE_QUEUE
from .logger.logger_setup import setup_core_logger
from .vsphere_pool_manager import VSpherePoolManager
from .config import cfg

# Уровень логирования CORE
CORE_LEVEL = 9
logging.addLevelName(CORE_LEVEL, "CORE")


def core(self, msg, *args, **kwargs):
    if self.isEnabledFor(CORE_LEVEL):
        self._log(CORE_LEVEL, msg, args, **kwargs)


logging.Logger.core = core


async def main():
    # Настройка логирования
    core_logger, stop_core_logger = setup_core_logger()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for h in core_logger.handlers:
        root.addHandler(h)

    # Создаём пул через конфиг
    pool = VSpherePoolManager(
        cfg.vcenter_host,
        cfg.vcenter_user,
        cfg.vcenter_password
    )

    rep = Replenisher(pool)

    tasks = [
        asyncio.create_task(rep.run(), name="replenisher"),
        asyncio.create_task(builder_pool(), name="builder-pool")
    ]

    loop = asyncio.get_running_loop()
    stop_ev = asyncio.Event()
    try:
        loop.add_signal_handler(signal.SIGINT, stop_ev.set)
        loop.add_signal_handler(signal.SIGTERM, stop_ev.set)
    except NotImplementedError:
        pass

    try:
        await stop_ev.wait()
    except KeyboardInterrupt:
        pass

    rep.stop()
    await CLONE_QUEUE.join()
    await asyncio.gather(*tasks, return_exceptions=True)

    stop_core_logger()


if __name__ == "__main__":
    asyncio.run(main())
