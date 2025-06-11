import os
import logging
from pydantic_settings import BaseSettings
from pydantic import Field


class Config(BaseSettings):
    # Обязательные поля
    min_ready_vm: int = Field(..., alias="REFILLER_MIN_READY_VM")
    max_ready_vm: int = Field(..., alias="REFILLER_MAX_READY_VM")
    batch_size: int = Field(..., alias="REFILLER_BATCH_SIZE")
    check_interval: int = Field(..., alias="REFILLER_CHECK_INTERVAL")

    # Необязательные с дефолтами
    pool_op_retries: int = Field(3, alias="POOL_OP_RETRIES")
    pool_op_backoff: float = Field(2.0, alias="POOL_OP_BACKOFF")
    ip_timeout: int = Field(10, alias="IP_TIMEOUT")
    builder_proc: int = Field(2, alias="REFILLER_BUILDER_PROC")
    worker_timeout: int = Field(1800, alias="WORKER_TIMEOUT")
    fault_vm_ttl_minutes: int = Field(60, alias="FAULT_VM_TTL_MINUTES")

    # Строковые переменные
    vcenter_host: str = Field("", alias="VCENTER_HOST")
    vcenter_user: str = Field("", alias="VCENTER_USER")
    vcenter_password: str = Field("", alias="VCENTER_PASSWORD")
    vm_prefix: str = Field("Dev", alias="VM_PREFIX")
    golden_name: str = Field(..., alias="REFILLER_GOLDEN_VM_NAME")

    # Порт с дефолтом
    vcenter_port: int = Field(443, alias="VCENTER_PORT")

    class Config:
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **values):
        super().__init__(**values)
        # сразу залогируем конфиг
        self.log_config()

    @property
    def logger(self) -> logging.Logger:
        """Логгер с именем класса Config."""
        return logging.getLogger(self.__class__.__name__)

    def log_config(self) -> None:
        """
        Логирует все параметры:
            - помечает (env), если взято из os.environ,
            - или (default), если используется значение по умолчанию.
        """
        for field_name, model_field in self.model_fields.items():
            env_key = model_field.alias or field_name
            value = getattr(self, field_name)
            source = "env" if env_key in os.environ else "default"
            self.logger.info("%s=%r (%s)", env_key, value, source)


cfg = Config()
