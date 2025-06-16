import os
import time
import logging
import datetime
from PIL import Image
from collections import deque
from typing import Optional

from .core.VMware.BlissOSController import BlissAdbManager
from .states.Tutorial.InitGame import InitGame
from .states.FinishState import FinishState


class GameTutorial:
    def __init__(self, ip: str, vm_name: str, logger: Optional[logging.Logger] = None):
        self.ip = ip
        self.vm_name = vm_name
        self.iteration = 0
        self._initialized = False
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def initialize(self):
        self.memu = BlissAdbManager(adb_ip=self.ip)
        self.memu.logger = self.logger

        self.memu.open_app()

        self._initialized = True
        self.logger.info('Тяжёлая инициализация завершена')

        # Очередь состояний
        self.state_queue = deque([InitGame(self)], maxlen=5)
        self.substate = None

        self.session_start = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        # Не подавляем исключения – возвращаем False
        return False

    def cleanup(self):
        """
        Освобождение всех ресурсов.
        Вызывается в блоке __exit__.
        """
        self.memu.close_app()
        self.memu.shutdown_device()
        self.logger.info("Cleanup выполнен")

    def run(self):
        # Защита от старта без тяжелой инициализации
        if not self._initialized:
            raise RuntimeError("BlisInitSetup не инициализирован. Вызывайте initialize() через контекстный менеджер.")

        start_time = time.time()
        time_limit = 30 * 60  # 20 минут в секундах

        while not isinstance(self.state_queue[-1], FinishState):
            elapsed = time.time() - start_time
            if elapsed > time_limit:
                self.logger.error(
                    f'Превышено максимальное время выполнения: {elapsed:.1f}s > {time_limit}s'
                )
                break

            current_state = self.state_queue[-1]
            current_state.handle()

    def _save_img(
        self,
        img: Image.Image,
        mode: str,
        task_name: str
    ):
        if img is None:
            self.logger.error(
                f'Не удалось сохранить скриншот {mode}: {task_name}, '
                'так как изображение равно None')
            return

        save_pth = os.path.join(
            os.getenv('LOGS_SAVE_FOLDER'),
            self.vm_name,
            self.session_start,
            mode,
            task_name
        )
        os.makedirs(save_pth, exist_ok=True)

        image_name = f'{self.iteration}.jpg'

        screnshot_pth = os.path.join(save_pth, image_name)

        img.save(screnshot_pth)
        self.logger.core(f'Сохранен скриншот {mode}: {task_name} {image_name}')

    def change_state(self, new_state, substate=None):
        """
        Переключает на новое состояние, добавляя его в очередь.
        """
        last_state_name = self.state_queue[-1].__class__.__name__
        new_state_name = new_state.__class__.__name__

        self.logger.info(
            f'Изменение состояния с {last_state_name} '
            f'на {new_state_name}'
        )
        self.state_queue.append(new_state)
        self.substate = substate

    def change_substate(self, new_substate):
        # Логирование
        self.logger.info(
            f'Изменено подсостояние с {self.substate} на {new_substate}'
        )

        self.substate = new_substate

    def complete_task(self, swipe_state=False, substate=None):
        # Получение имен состояний
        last_state = self.state_queue.pop()
        last_state_name = last_state.__class__.__name__
        new_state = self.state_queue[-1]
        new_state_name = new_state.__class__.__name__

        # Логирование смены состояния
        self.logger.info(
            f'Закончено состояние {last_state_name} '
            f'переключение на {new_state_name}'
        )

        self.substate = substate


if __name__ == "__main__":
    # Настраиваем логирование
    logging.basicConfig(level=logging.DEBUG)

    for noisy in ("uiautomator2.core", "urllib3.connectionpool", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Укажите IP вашей виртуальной машины adb OS
    IP = "192.168.19.172"

    # Запуск инициализации и выполнения последовательности
    with GameTutorial(ip=IP, vm_name='BlissOS16_GO_2') as game:
        game.run()
