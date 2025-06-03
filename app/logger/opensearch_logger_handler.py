# vm_refiller/logger/opensearch_logger_handler.py
import ipaddress
import logging
from opensearchpy import OpenSearch, exceptions as opensearch_exceptions

IGNORED_MODULES = {"opensearch", "urllib3", "filelock"}


class OpenSearchMicroserviceHandler(logging.Handler):
    """
    • Если vm_index=False — пишем «общие» логи (без vm_*-полей);
    • Если vm_index=True  — расширяем mapping и логируем vm_name / vm_ip / job_id.
    """
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        username: str = "admin",
        password: str = "S3cur3P@ssword!",
        index_name: str = "zeon-refiller-test",
        vm_index: bool = False,
    ):
        super().__init__()
        self.index_name = index_name
        self.vm_index = vm_index

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=(username, password),
            use_ssl=False,
            verify_certs=False,
            timeout=30,
            max_retries=5,
            retry_on_timeout=True,
        )
        self._ensure_index_exists()

    # ------------------------------------------------------------------ #
    # 1. Создаём индекс с нужным набором полей
    # ------------------------------------------------------------------ #
    def _ensure_index_exists(self) -> None:
        props = {
            "timestamp": {
                "type":   "date",
                "format": "epoch_millis",
            },
            "level":    {"type": "keyword"},
            "logger":   {"type": "keyword"},      #  <<< новое поле
            "module":   {"type": "keyword"},      #  теперь «py-модуль», а не имя логгера
            "function": {"type": "keyword"},
            "line":     {"type": "integer"},
            "message":  {"type": "text"},
        }
        if self.vm_index:                       # дополняем только для VM-индекса
            props.update({
                "vm_name": {"type": "keyword"},
                "vm_ip":   {"type": "ip"},
                "job_id":  {"type": "keyword"},
            })

        mapping = {"mappings": {"properties": props}}

        try:
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(index=self.index_name, body=mapping)
        except opensearch_exceptions.ConnectionError as e:
            print(f"[Logger] OpenSearch connection error: {e}")
        except Exception as e:
            print(f"[Logger] Error while creating index: {e}")

    # ------------------------------------------------------------------ #
    # 2. Отправляем документ
    # ------------------------------------------------------------------ #
    def emit(self, record: logging.LogRecord) -> None:
        # отбрасываем «шумные» либы
        if record.name.split(".")[0] in IGNORED_MODULES:
            return

        try:
            doc = {
                "timestamp": int(record.created * 1000),
                "level":     record.levelname,
                "logger":    record.name,       #  <<< имя логгера (ms.…)
                "module":    record.module,     #  <<< настоящий py-модуль
                "function":  record.funcName,
                "line":      record.lineno,
                "message":   record.getMessage(),
            }
            if self.vm_index:
                for fld in ("vm_name", "vm_ip", "job_id"):
                    if not hasattr(record, fld):
                        continue
                    val = getattr(record, fld)
                    # vm_ip → только корректные адреса
                    if fld == "vm_ip":
                        try:
                            ipaddress.ip_address(str(val))
                        except ValueError:
                            continue
                    doc[fld] = val

            self.client.index(index=self.index_name, body=doc)
        except Exception as e:
            print(f"[Logger] Error while sending log: {e}")
