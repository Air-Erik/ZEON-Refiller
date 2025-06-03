from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


env_path = Path(__file__).parent.parent / "config" / ".env"


class Config(BaseSettings):
    min_ready_vm: int = Field(..., alias="REFILLER_MIN_READY_VM")
    max_ready_vm: int = Field(..., alias="REFILLER_MAX_READY_VM")
    batch_size: int = Field(..., alias="REFILLER_BATCH_SIZE")
    check_interval: int = Field(..., alias="REFILLER_CHECK_INTERVAL")

    pool_op_retries: int = Field(3, alias="POOL_OP_RETRIES")
    pool_op_backoff: float = Field(2.0, alias="POOL_OP_BACKOFF")
    ip_timeout: int = Field(10, alias="IP_TIMEOUT")

    builder_proc: int = Field(2, alias="REFILLER_BUILDER_PROC")

    worker_timeout: int = Field(1800, alias="WORKER_TIMEOUT")
    fault_vm_ttl_minutes: int = Field(60, alias="FAULT_VM_TTL_MINUTES")

    vcenter_host: str = Field("", alias="VCENTER_HOST")
    vcenter_user: str = Field("", alias="VCENTER_USER")
    vcenter_password: str = Field("", alias="VCENTER_PASSWORD")

    vm_prefix: str = Field("Dev", alias="VM_PREFIX")
    golden_name: str = Field(..., alias="REFILLER_GOLDEN_VM_NAME")

    vcenter_port: int = Field(443, alias="VCENTER_PORT")

    class Config:
        env_file = str(env_path)
        case_sensitive = False
        extra = "ignore"


cfg = Config()
