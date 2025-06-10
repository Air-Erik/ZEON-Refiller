# vm_refiller/logger/logger_setup.py
from __future__ import annotations

import logging
import logging.handlers
import os
from queue import Queue
from typing import Callable, Tuple

from .opensearch_logger_handler import OpenSearchMicroserviceHandler
from .log_ctx import ContextFilter

# ────────────────────────────────────────────────────────────────────────
#  Настройки «тихого режима» для болтливых библиотек
# ────────────────────────────────────────────────────────────────────────
_NOISY_LIBS = (
    "urllib3",
    "opensearch",
    "asyncio",
    "filelock",
    "paramiko"
)


def _mute_third_party() -> None:
    """Переключаем болтливые библиотеки на WARNING и запрещаем propagate."""
    for name in _NOISY_LIBS:
        lib_log = logging.getLogger(name)
        lib_log.setLevel(logging.WARNING)
        lib_log.propagate = False


# ────────────────────────────────────────────────────────────────────────
#  Фильтр: пропускать только записи, у которых уже есть vm-контекст
# ────────────────────────────────────────────────────────────────────────
class VmOnlyFilter(logging.Filter):
    """Пропускает LogRecord, если в нём есть vm_name (значит, это наша ВМ)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        return hasattr(record, "vm_name")


# ────────────────────────────────────────────────────────────────────────
#  Фабрика логгеров
# ────────────────────────────────────────────────────────────────────────
def _create_logger(*, index: str, level: int = logging.INFO) -> Tuple[logging.Logger, Callable[[], None]]:
    """
    Возвращает (логгер, stop_fn).  stop_fn нужно вызвать при завершении работы
    процесса, чтобы корректно погасить QueueListener.
    """
    log = logging.getLogger(f"ms.{index}")

    # Если OpenSearch-хендлер уже висит — возвращаем существующий логгер
    if any(isinstance(h, OpenSearchMicroserviceHandler) for h in log.handlers):
        return log, lambda: None

    # ── базовые настройки ───────────────────────────────────────────
    log.setLevel(logging.DEBUG)          # всё принимаем, фильтруем на хендлерах
    log.propagate = False                # изолируемся от root
    q: Queue = Queue()
    log.addHandler(logging.handlers.QueueHandler(q))

    # ── консоль ─────────────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    console.setLevel(logging.INFO)
    console.addFilter(ContextFilter())   # ← добавляем vm_name / vm_ip / job_id
    console.addFilter(lambda r: r.name.split(".")[0] not in _NOISY_LIBS)

    # ── OpenSearch (хендлер, «сидящий» на ms.…-vms) ─────────────────
    os_handler = OpenSearchMicroserviceHandler(
        index_name=index,
        vm_index=index.endswith("-vms"),
    )
    os_handler.setLevel(level)
    os_handler.addFilter(ContextFilter())

    listener = logging.handlers.QueueListener(q, console, os_handler)
    listener.start()

    # ── OpenSearch-хендлер на root (чтобы ловить «голые» логгеры) ───
    root = logging.getLogger()
    if not any(isinstance(h, OpenSearchMicroserviceHandler) for h in root.handlers):
        os_handler_root = OpenSearchMicroserviceHandler(
            index_name=index,
            vm_index=index.endswith("-vms"),
        )
        os_handler_root.setLevel(level)
        os_handler_root.addFilter(ContextFilter())
        os_handler_root.addFilter(VmOnlyFilter())   # ← root пропускает только ВМ-логи
        root.addHandler(os_handler_root)

    # приглушаем сторонние библиотеки
    _mute_third_party()

    return log, listener.stop


# ───── публичные врапперы ──────────────────────────────────────────────
def setup_core_logger() -> Tuple[logging.Logger, Callable[[], None]]:
    """
    Логгер для «общего» индекса (без vm-контекста).
    """
    return _create_logger(index="zeon-refiller-test")


def setup_vm_logger() -> Tuple[logging.Logger, Callable[[], None]]:
    """
    Логгер для индекса-ВМ.  Все записи c vm_name → zeon-refiller-test-vms.
    """
    return _create_logger(index="zeon-refiller-test-vms")
