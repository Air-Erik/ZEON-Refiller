import logging


class VSphereError(Exception):
    """Базовый класс для ошибок команд vSphere."""
    def __init__(self, message: str, logger: logging.Logger = None):
        super().__init__(message)
        self.message = message
        self.logger = logger
        if self.logger:
            self.logger.error(message)

    def __str__(self):
        return self.message


class VMPowerOnError(VSphereError):
    """Ошибка при попытке включить виртуальную машину."""
    def __init__(self, vm_name: str, current_state: str, logger: logging.Logger = None):
        message = (
            f"Не удалось включить виртуальную машину '{vm_name}'. "
            f"Текущее состояние: {current_state}."
        )
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.current_state = current_state


class VMSuspendError(VSphereError):
    """Ошибка при попытке поставить виртуальную машину на паузу."""
    def __init__(self, vm_name: str, current_state: str, logger: logging.Logger = None):
        message = (
            f"Не удалось остановить виртуальную машину '{vm_name}'. "
            f"Текущее состояние: {current_state}."
        )
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.current_state = current_state


class VMPowerOffError(VSphereError):
    """Ошибка при попытке выключить виртуальную машину."""
    def __init__(self, vm_name: str, current_state: str, logger: logging.Logger = None):
        message = (
            f"Не удалось выключить виртуальную машину '{vm_name}'. "
            f"Текущее состояние: {current_state}."
        )
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.current_state = current_state


class VMCloneError(VSphereError):
    """Ошибка при клонировании виртуальной машины."""
    def __init__(self, vm_name: str, logger: logging.Logger = None, details: str = None):
        message = f"Не удалось клонировать виртуальную машину '{vm_name}'."
        if details:
            message += f" Детали: {details}"
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.details = details


class VMDeleteError(VSphereError):
    """Ошибка при удалении виртуальной машины."""
    def __init__(self, vm_name: str, logger: logging.Logger = None, details: str = None):
        message = f"Не удалось удалить виртуальную машину '{vm_name}'."
        if details:
            message += f" Детали: {details}"
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.details = details


class VMNotFoundError(VSphereError):
    """Ошибка получении ВМ"""
    def __init__(self, vm_name: str, logger: logging.Logger = None):
        message = f"Не удалось получить объект VM '{vm_name}'"
        super().__init__(message, logger)
        self.vm_name = vm_name


class VMIPNotFoundError(VSphereError):
    """Ошибка при получении IP-адреса ВМ по MAC адресу."""
    def __init__(self, vm_name: str, mac_address: str, logger: logging.Logger = None):
        message = f"Не удалось получить IP для VM '{vm_name}' с MAC адресом {mac_address}."
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.mac_address = mac_address


class VMWaitReadyError(VSphereError):
    """Ошибка ожидания готовности ВМ (например, для подключения ADB)."""
    def __init__(self, vm_name: str, timeout: int, logger: logging.Logger = None):
        message = f"Истекло время ожидания готовности VM '{vm_name}' для подключения (ADB) за {timeout} секунд."
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.timeout = timeout


class VMReconfigureError(VSphereError):
    """Ошибка при изменении конфигурации виртуальной машины."""
    def __init__(self, vm_name: str, logger: logging.Logger = None, details: str = None):
        message = f"Не удалось изменить конфигурацию VM '{vm_name}'."
        if details:
            message += f" Детали: {details}"
        super().__init__(message, logger)
        self.vm_name = vm_name
        self.details = details
