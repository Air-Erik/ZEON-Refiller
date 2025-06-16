# vm_refiller/builder.py
from __future__ import annotations

import os
import time
import queue
import logging
import asyncio
import traceback
from multiprocessing import Process, Queue

from source.GameTutorial import GameTutorial
from source.BlissInitSetup import BlisInitSetup

from ..shared.settings import cfg
from ..infrastructure.logger.logger_setup import setup_vm_logger
from ..infrastructure.logger.log_ctx import set_context
from ..services.tasks import CLONE_QUEUE, CloneTask, WorkerResult
from ..infrastructure.vsphere.manager import VSpherePoolManager
from ..shared.pending_counter import pending

logger = logging.getLogger(__name__)


def retry_sync(fn, retries: int, backoff: float, label: str = ""):
    """Синхронный back-off-retry с экспонентой."""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            logger.warning("[retry] %s (попытка %s/%s): %s", label, attempt, retries, e)
            if attempt == retries:
                raise
            time.sleep(backoff * 2 ** (attempt - 1))


class CloneWorker:
    """Клонирует Golden-VM, выполняет post-install и отдаёт результат через Queue."""

    def __init__(self, task: CloneTask, result_q: Queue):
        self.task = task
        self.result_q = result_q
        self.id_hex = task.job_id.hex[:8]

        # Статические атрибуты из конфига
        self.prefix = cfg.vm_prefix.strip()
        self.source_vm = f"[{self.prefix}] {cfg.golden_name}"
        self.name_init = f"[{self.prefix}] VMInit_{self.id_hex}"
        self.name_ready = f"[{self.prefix}] VM2login_{self.id_hex}"
        self.name_error = f"[{self.prefix}] VMError_{self.id_hex}"
        self.folder_2_vm = f"DC1/ZeonVM/{self.prefix}/LoginVMs"

        self.retries = cfg.pool_op_retries
        self.backoff = cfg.pool_op_backoff
        self.ip_timeout = cfg.ip_timeout

        self.vm = None
        self.vm_log, self.stop_logger = setup_vm_logger()
        self.logger = self.vm_log
        set_context(vm_name=self.name_init, vm_ip="-", job_id=self.id_hex)

    # ---------------- private helpers ---------------- #

    def _bliss_init(self, ip: str, pool: VSpherePoolManager) -> str:
        """Первичная настройка Windows + драйверов."""
        for attempt in range(1, 4):
            try:
                with BlisInitSetup(ip=ip, logger=self.logger) as init:
                    init.run()
                self.logger.info("BlissInit — success (try %s)", attempt)
                return ip
            except TimeoutError:
                # APK не успел установиться — пробуем ещё без рестарта ВМ
                self.logger.warning(
                    "APK install timeout (try %s/3) – повторяем без рестарта", attempt
                )
                continue
            except Exception:
                self.logger.exception("BlissInit failed (try %s)", attempt)
                if attempt == 3:
                    raise
                pool.ensure_nsx_alive()
                pool.restart_vm(self.vm)
                ip = pool.wait_for_vm_ready(self.vm, timeout=300)

    def _game_init(self, ip: str, pool: VSpherePoolManager) -> None:
        """Прокликивание туториала внутри игры."""
        for attempt in range(1, 4):
            try:
                with GameTutorial(ip=ip, vm_name=self.vm.name, logger=self.logger) as init:
                    init.run()
                self.logger.info("GameTutorial — success (try %s)", attempt)
                return
            except Exception:
                self.logger.exception("GameTutorial failed (try %s)", attempt)
                if attempt == 3:
                    raise
                pool.restart_vm(self.vm)
                ip = pool.wait_for_vm_ready(self.vm, timeout=300)

    # ---------------- main workflow ---------------- #

    def prepare_vm(self) -> None:
        with VSpherePoolManager(
            cfg.vcenter_host, cfg.vcenter_user, cfg.vcenter_password, logger=self.logger
        ) as pool:
            # 1. clone
            self.vm = retry_sync(
                lambda: pool.clone_vm(self.source_vm, self.name_init, self.folder_2_vm),
                self.retries,
                self.backoff,
                "clone_vm",
            )
            time.sleep(10)

            # 2. power-on + wait IP
            retry_sync(lambda: pool.power_on_vm(self.vm), self.retries, self.backoff, "power_on_vm")
            ip = retry_sync(
                lambda: pool.wait_for_vm_ready(self.vm, timeout=self.ip_timeout),
                self.retries,
                self.backoff,
                "wait_for_ip",
            )
            set_context(vm_ip=ip)

            # 3. guest-side настройка
            ip = self._bliss_init(ip, pool)
            self._game_init(ip, pool)

            pool.mark_ready(self.vm)
            pool.power_off_vm(self.vm)
            self.logger.info("VM готова к работе")
            self.result_q.put(WorkerResult("ok", self.name_ready))
            # 4. freeze snapshot & mark ready
            retry_sync(lambda: pool.power_off_vm(self.vm), self.retries, self.backoff, "power_off_vm")
            retry_sync(lambda: pool.mark_ready(self.vm), self.retries, self.backoff, "mark_ready")

            self.logger.info("VM %s готова к работе", self.name_ready)
            self.result_q.put(WorkerResult("ok", self.name_ready))

    def _cleanup_on_error(self, exc: Exception) -> None:
        """Пытаемся аккуратно завершить ВМ и пометить её битой."""
        tb = traceback.format_exc()
        self.logger.exception("Критическая ошибка сборки ВМ:\n%s", tb)

        try:
            with VSpherePoolManager(cfg.vcenter_host, cfg.vcenter_user, cfg.vcenter_password) as pool:
                if self.vm:
                    try:
                        retry_sync(
                            lambda: pool.power_off_vm(self.vm), self.retries, self.backoff, "power_off_vm"
                        )
                    except Exception:
                        pass
                    pool.mark_fault(self.vm)
        except Exception:
            pass

        self.result_q.put(WorkerResult("err", self.name_error, tb))

    # ---------------- entrypoint for subprocess ---------------- #

    @staticmethod
    def run(task: CloneTask, result_q: Queue) -> None:
        worker = CloneWorker(task, result_q)
        try:
            worker.prepare_vm()
        except Exception as exc:
            worker._cleanup_on_error(exc)
        finally:
            worker.stop_logger()


# --------------------------------------------------------------------------- #
#                             BUILDER POOL (ASYNC)                            #
# --------------------------------------------------------------------------- #

WORKER_TIMEOUT = cfg.worker_timeout  # задаётся через .env


async def builder_pool() -> None:
    """Пул, который разворачивает subprocess-ы CloneWorker."""
    sem = asyncio.Semaphore(cfg.builder_proc)
    loop = asyncio.get_running_loop()

    while True:
        await sem.acquire()

        task: CloneTask = await CLONE_QUEUE.get()
        result_q: Queue[WorkerResult] = Queue()
        proc = Process(target=CloneWorker.run, args=(task, result_q), daemon=True)
        proc.start()

        async def _on_finish() -> None:
            """Запускается в фоне и ждёт завершения subprocess-а."""
            try:
                await loop.run_in_executor(None, proc.join, WORKER_TIMEOUT)
                if proc.is_alive():
                    proc.terminate()

                result: WorkerResult = result_q.get_nowait()

                if result.status == "ok":
                    logger.info("VM %s готова", result.vm_name)
                else:
                    logger.error("Ошибка подготовки %s:\n%s", result.vm_name, result.message)
                    _safe_mark_fault(result.vm_name)

            except queue.Empty:
                logger.error("Worker pid=%s завершился без ответа", proc.pid)
                _safe_mark_fault(f"[{cfg.vm_prefix}] VMInit_{task.job_id.hex[:8]}")
            finally:
                await pending.dec()
                sem.release()
                CLONE_QUEUE.task_done()

        async def _safe_mark_fault(vm_name: str) -> None:
            try:
                with VSpherePoolManager(cfg.vcenter_host, cfg.vcenter_user, cfg.vcenter_password) as pool:
                    pool.mark_fault(vm_name)
            except Exception:
                logger.exception("mark_fault %s failed", vm_name)

        asyncio.create_task(_on_finish())
