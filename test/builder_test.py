import time
import queue
import logging
import asyncio
import traceback
from multiprocessing import Process, Queue

from vm_refiller.config import cfg
from vm_refiller.logger.logger_setup import setup_vm_logger
from vm_refiller.tasks import CLONE_QUEUE, CloneTask, WorkerResult
from vm_refiller.vsphere_pool_test import VSpherePoolManager


logger = logging.getLogger(__name__)


def retry_sync(fn, retries: int, backoff: float, label: str = ""):
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            logger.warning("[retry-test] %s (попытка %s/%s): %s", label, attempt, retries, e)
            if attempt == retries:
                raise
            time.sleep(backoff * (2 ** (attempt - 1)))


class TestCloneWorker:
    def __init__(self, task: CloneTask, result_q: Queue):
        self.task = task
        self.result_q = result_q
        self.id_hex = task.job_id.hex[:8]
        self.prefix = cfg.vm_prefix or "TEST"
        self.source_vm = f"[{self.prefix}] {cfg.golden_name}"
        self.name_init = f"[{self.prefix}] VMInit_{self.id_hex}"
        self.name_ready = f"[{self.prefix}] VM2login_{self.id_hex}"
        self.name_error = f"[{self.prefix}] VMError_{self.id_hex}"
        self.retries = cfg.pool_op_retries
        self.backoff = cfg.pool_op_backoff
        self.ip_timeout = cfg.ip_timeout
        self.vm = None
        self.vm_log, self.stop_logger = setup_vm_logger()
        self.logger = logging.LoggerAdapter(
            self.vm_log, {"vm_name": self.name_init, "vm_ip": "-", "job_id": self.id_hex}
        )

    def prepare_vm(self):
        with VSpherePoolManager() as pool:
            self.vm = retry_sync(lambda: pool.clone_vm(self.source_vm, self.name_init),
                                 self.retries, self.backoff, "clone_vm")
            time.sleep(0.5)
            retry_sync(lambda: pool.power_on_vm(self.vm), self.retries, self.backoff, "power_on_vm")

            ip = retry_sync(lambda: pool.wait_for_vm_ready(self.vm, timeout=self.ip_timeout),
                            self.retries, self.backoff, "wait_for_ip")
            self.logger.extra["vm_ip"] = ip

            self._blis_init(ip, pool)
            self._game_init(ip, pool)

            retry_sync(lambda: pool.power_off_vm(self.vm), self.retries, self.backoff, "power_off_vm")
            retry_sync(lambda: pool.mark_ready(self.vm), self.retries, self.backoff, "mark_ready")

            self.logger.info("VM готова (тест)")
            self.result_q.put(WorkerResult("ok", self.name_ready))

    def _blis_init(self, ip, pool):
        for attempt in range(1, 4):
            try:
                self.logger.info("[blis_init_setup] Успех на попытке %s", attempt)
                return ip
            except Exception:
                self.logger.exception("[blis_init_setup] Ошибка, попытка %s", attempt)
                if attempt == 3:
                    raise
                ip = pool.wait_for_vm_ready(self.vm, timeout=5)

    def _game_init(self, ip, pool):
        for attempt in range(1, 4):
            try:
                self.logger.info("[game_init_setup] Успех на попытке %s", attempt)
                return
            except Exception:
                self.logger.exception("[game_init_setup] Ошибка, попытка %s", attempt)
                if attempt == 3:
                    raise
                ip = pool.wait_for_vm_ready(self.vm, timeout=5)

    def cleanup_on_error(self, exc: Exception):
        tb = traceback.format_exc()
        self.logger.exception("Ошибка сборки ВМ (тест):\n%s", tb)
        try:
            with VSpherePoolManager() as pool:
                if self.vm:
                    try:
                        retry_sync(lambda: pool.power_off_vm(self.vm), self.retries, self.backoff, "power_off_vm")
                    except Exception:
                        pass
                    pool.mark_fault(self.vm)
        except Exception:
            pass
        self.result_q.put(WorkerResult("err", self.name_error, tb))

    @staticmethod
    def run(task: CloneTask, result_q: Queue):
        worker = TestCloneWorker(task, result_q)
        try:
            worker.prepare_vm()
        except Exception as e:
            worker.cleanup_on_error(e)
        finally:
            worker.stop_logger()


async def builder_pool() -> None:
    sem = asyncio.Semaphore(cfg.builder_proc)
    loop = asyncio.get_running_loop()

    while True:
        await sem.acquire()
        task: CloneTask = await CLONE_QUEUE.get()
        result_q: Queue[WorkerResult] = Queue()
        proc = Process(target=TestCloneWorker.run, args=(task, result_q), daemon=True)
        proc.start()

        def _on_finish(p: Process, q: Queue, sema: asyncio.Semaphore):
            try:
                p.join(timeout=30)
                if p.is_alive():
                    p.terminate()
                result: WorkerResult = q.get(timeout=0.2)
                if result.status == "ok":
                    logger.info("[builder‑test] VM %s готова", result.vm_name)
                else:
                    logger.error("[builder‑test] Ошибка подготовки %s:\n%s", result.vm_name, result.message)
            except queue.Empty:
                logger.error("[builder‑test] Worker завершился без ответа")
            finally:
                from vm_refiller.pending_counter import pending
                asyncio.run_coroutine_threadsafe(pending.dec(), loop)
                sema.release()
                CLONE_QUEUE.task_done()

        loop.run_in_executor(None, _on_finish, proc, result_q, sem)
