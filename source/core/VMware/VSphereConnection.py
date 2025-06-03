import ssl
import logging
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect


class VSphereConnection:
    def __init__(self, host: str, user: str, pwd: str, port: int = 443) -> None:

        self.logger = logging.getLogger(self.__class__.__name__)
        self.host = host
        self.user = user
        self.pwd = pwd
        self.port = port
        self.si = None
        self.content = None

        self._connect()

    def _connect(self) -> None:
        try:
            context = ssl._create_unverified_context()
            self.si = SmartConnect(host=self.host, user=self.user, pwd=self.pwd, port=self.port, sslContext=context)
            self.content = self.si.RetrieveContent()
            self.logger.info(f"Подключение к vCenter {self.host} прошло успешно.")
        except Exception as e:
            self.logger.error(f"Ошибка при подключении к vCenter {self.host}: {e}")
            raise

    def disconnect(self) -> None:
        try:
            Disconnect(self.si)
            self.logger.info("Отключение от vCenter прошло успешно.")
        except Exception as e:
            self.logger.error(f"Ошибка при отключении от vCenter: {e}")
            raise

    def reconnect_if_needed(self):
        try:
            # Реальный запрос к серверу
            self.si.CurrentTime()
        except vim.fault.NotAuthenticated:
            self.logger.warning("Сессия устарела. Переподключаемся...")
            self._connect()
            return True

        return False
