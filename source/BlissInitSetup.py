import re
import time
import logging
from typing import List
from typing import Optional
from .core.VMware.BlissOSController import BlissAdbManager


class BlisInitSetup:
    def __init__(self, ip: str, logger: Optional[logging.Logger] = None):
        self.ip = ip
        self._initialized = False
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def initialize(self):
        self.adb = BlissAdbManager(adb_ip=self.ip)
        self.adb.logger = self.logger

        self._initialized = True
        self.logger.info('Тяжёлая инициализация завершена')

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Не подавляем исключения – возвращаем False
        return False

    def has_substring(
        self,
        target_list: List[str],
        check_list: List[str]
    ) -> bool:
        """
        Проверяет, есть ли хотя бы одно совпадение или подстрока из target_list в
        check_list. Сравнение происходит без учета регистра.

        :param target_list: Список целевых строк для поиска.
        :param check_list: Список строк для проверки.
        :return: True, если хотя бы одна строка из target_list является подстрокой
        любого элемента из check_list.
        """
        pattern = re.compile('|'.join(map(re.escape, target_list)), re.IGNORECASE)
        return any(pattern.search(item) for item in check_list)

    def run(self):
        # Защита от старта без тяжелой инициализации
        if not self._initialized:
            raise RuntimeError("BlisInitSetup не инициализирован. Вызывайте initialize() через контекстный менеджер.")

        self.text = self.adb.u2_get_all_texts()
        self.logger.debug(f'Тексты на экране: {self.text}')

        self.adb.u2_click_button('START', timeout=120)

        self.adb.u2_click_button("Don’t copy", timeout=360)
        self.adb.u2_click_button('SKIP', timeout=120)
        self.adb.u2_click_button('SKIP', timeout=40)

        self.adb.u2_wait_for_text('Tap to learn more', timeout=60)
        self.adb.u2_click_switch('', timeout=60)
        self.adb.swipe_percent([0.75, 0.8], [0.75, 0.2])
        self.adb.swipe_percent([0.75, 0.8], [0.75, 0.2])
        self.adb.u2_click_switch('', timeout=60)

        self.adb.u2_click_button("ACCEPT", timeout=60)
        self.adb.u2_click_text("Not now", timeout=60)
        self.adb.u2_click_text("SKIP ANYWAY", timeout=60)
        self.adb.u2_click_text("Launcher3", timeout=60)
        self.adb.u2_click_button("Always", timeout=60)

        self.adb.install_apk()
        self.adb.change_screen_size(432, 768)

        self.logger.info("Initial setup успешно завершён.")


if __name__ == "__main__":
    # Настраиваем логирование
    logging.basicConfig(level=logging.DEBUG)

    for noisy in ("uiautomator2.core", "urllib3.connectionpool", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Укажите IP вашей виртуальной машины adb OS
    IP = "192.168.19.172"

    # Запуск инициализации и выполнения последовательности
    with BlisInitSetup(ip=IP) as setup:
        setup.run()
