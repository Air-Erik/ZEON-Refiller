# vm_refiller/logger/log_ctx.py
import logging
import contextvars
import ipaddress
from typing import Dict, Any

# контекст хранится в contextvars, чтобы работать и в потоках, и в async
_LOG_CTX: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "_LOG_CTX", default={}
)


def set_context(**kwargs) -> None:
    """Добавить или обновить поля (vm_name, vm_ip, job_id, …)."""
    ctx = _LOG_CTX.get().copy()
    ctx.update(kwargs)
    _LOG_CTX.set(ctx)


class ContextFilter(logging.Filter):
    """Приклеивает поля из _LOG_CTX к каждому LogRecord’у."""
    def filter(self, record: logging.LogRecord) -> bool:          # noqa: D401
        ctx = _LOG_CTX.get()
        for k, v in ctx.items():
            # vm_ip: приклеиваем только валидный IPv4/IPv6
            if k == "vm_ip":
                try:
                    ipaddress.ip_address(str(v))
                except ValueError:
                    continue
            setattr(record, k, v)
        return True
