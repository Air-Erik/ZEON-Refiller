import logging
from typing import Optional


class ZeonError(Exception):
    def __init__(
        self,
        message: str,
        logger: Optional[logging.Logger] = None
    ) -> None:
        """Базовый класс исключений с автоматическим логированием

        Args:
            message (str): _description_
            logger (Optional[logging.Logger], optional): опциональный логгер для записи ошибки. Defaults to None.
        """
        super().__init__(message)
        # Используем переданный логгер или создаём свой
        self.logger = logger or logging.getLogger(__name__)
        # Логируем сообщение об ошибке сразу при создании
        self.logger.error(message)

    def __str__(self) -> str:
        # Возвращаем чистое сообщение без дополнительных деталей
        return str(self.args[0])
