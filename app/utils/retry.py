import time
import logging

logger = logging.getLogger(__name__)


def retry_sync(fn, retries: int, backoff: float, label: str = ""):
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            logger.warning(
                "[retry] Ошибка в %s (попытка %s/%s): %s",
                label or fn.__name__, attempt, retries, e
            )
            if attempt == retries:
                raise
            time.sleep(backoff * (2 ** (attempt - 1)))  # экспоненциальный backoff
