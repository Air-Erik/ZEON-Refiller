import logging
from .ZeonError import ZeonError
from typing import Optional


class GameBotError(ZeonError):
    """Базовый класс для ошибок игрового бота"""
    pass


class AnotherDeviceError(GameBotError):
    # TODO Тут должна быть логика отправки информации пользователю
    """Ошибка: вход с другого устройства."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = "Произведен вход с другого устройства"
        super().__init__(message, logger)


class MissingCharacterError(GameBotError):
    # TODO Тут должна быть логика отправки информации пользователю
    """Ошибка: нет доступных персонажей для игры."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = "Нет доступных персонажей для игры"
        super().__init__(message, logger)


class ConnectionLostError(GameBotError):
    # TODO Тут должна быть логика отправки информации разработчикам
    """Ошибка: разрыв интернет-соединения."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = "Разрыв интернет соединения"
        super().__init__(message, logger)


class RunTimeoutError(GameBotError):
    """Ошибка тайм-аута выполнения скрипта."""

    def __init__(
        self,
        timeout_value: int,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = f"Превышено максимальное время выполнения бота: {timeout_value} минут"
        super().__init__(message, logger)
        self.timeout_value = timeout_value


class ModelLoadError(GameBotError):
    """Ошибка загрузки модели по ключу."""

    def __init__(
        self,
        key: str,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = f"Модель для ключа {key} не найдена в настройках"
        super().__init__(message, logger)
        self.key = key


class RenderError(GameBotError):
    """Ошибка загрузки модели по ключу."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = "Ошибка рендринга изображения"
        super().__init__(message, logger)


class ExitCommandError(GameBotError):
    """Исключение, вызываемое при получении команды выхода."""
    pass


# Ошибки состояний
class StateError(GameBotError):
    """Класс исключения для ошибок состояний."""

    def __init__(
        self,
        state_name: str,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = f"Ошибка в состоянии {state_name}"
        super().__init__(message, logger)
        self.state_name = state_name


class StateTimeoutError(StateError):
    """Ошибка превышения времени выполнения состояния."""

    def __init__(
        self,
        state_name: str,
        max_time: int,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = f"Превышено максимальное время выполнения состояния {state_name}: {max_time} мин"
        super().__init__(message, logger)
        self.state_name = state_name
        self.max_time = max_time


class FreezeBotError(GameBotError):
    """Ошибка зависания бота."""

    def __init__(
        self,
        state_name: str,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = f"Бот завис в состоянии {state_name}, подтверждено сравнением картинок"
        super().__init__(message, logger)
        self.state_name = state_name


class WarStateError(StateError):
    # TODO Тут должна быть логика отправки лога и уведомления пользователю
    """Ошибка: распознано нападение на базу."""

    def __init__(
        self,
        state_name: str,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = f"Распознано нападение на базу в состоянии {state_name}"
        super().__init__(message, logger)
        self.state_name = state_name


class BackStateError(StateError):
    """Ошибка выхода через кнопку назад."""

    def __init__(
        self,
        state_name: str,
        core_name: str,
        logger: Optional[logging.Logger] = None
    ) -> None:
        message = f"{state_name}: не получилось выйти до {core_name}"
        super().__init__(message, logger)
        self.state_name = state_name
        self.core_name = core_name
