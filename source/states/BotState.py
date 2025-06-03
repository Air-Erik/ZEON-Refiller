import os
import time
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, List
from ..exceptions.GameBotError import StateTimeoutError
from ..utils.TemplateMatcher import TemplateMatcher


if TYPE_CHECKING:
    from ..GameTutorial import GameTutorial


class BotState(ABC):

    def __init__(
        self,
        game_bot: 'GameTutorial',
        max_duration_min=5,
        template_ref_dir: str = None
    ):
        self.bot = game_bot
        self.state_name = self.__class__.__name__
        self.api_send = False

        # Получаем логгер с именем класса
        self.logger = logging.getLogger(self.state_name)
        self.logger.info(f'Инциализация состояния: {self.state_name}')

        self.start_time = time.time()
        self.max_duration_min = max_duration_min

        # Выбираем путь к референсным картинкам:
        default_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '..', '..',
                'config',
                'reference_images'
            )
        )
        ref_dir = template_ref_dir or default_dir

        # Создаём matcher один раз
        self.template_matcher = TemplateMatcher(ref_dir=ref_dir)

        self.time_segments = [self.max_duration_min * i / 10 for i in range(1, 11)]
        self.time_segments_index = 0

        self.metrics = {}  # Словарь для хранения метрик

        # Параметры проверки текущей активности в ВМ
        self.whitelist_activity = []  # Разрешенные активности
        self.target_activity = ""  # Целевая активность

    @abstractmethod
    def handle(self):
        pass

    def _check_time_limit(self):
        current_time = time.time()
        duration = current_time - self.start_time
        minutes, _ = divmod(duration, 60)

        if minutes > self.max_duration_min:
            raise StateTimeoutError(
                self.state_name, self.max_duration_min, self.logger
            )

    def _process_screen(self, task_name, take_screenshot=True):
        self._check_time_limit()

        if take_screenshot:
            self.bot.memu.get_screenshot()

        self.bot._save_img(self.bot.memu.screenshot, 'img', task_name)

    def wait_for_template(
        self,
        ref_name: str,
        threshold: float = 0.90,
        retry_delay: float = 2,
        timeout: float = 60,
        stop_ref_name: Optional[str] = None,
        stop_threshold: Optional[float] = None
    ) -> str | None | bool:
        """
        Ждёт появления шаблона ref_name.
        Если найден stop_ref_name — возвращает None.
        Если таймаут — возвращает False.
        Если найден целевой шаблон — возвращает его имя (ref_name).

        :return:
            • ref_name (str)  — шаблон найден
            • None            — стоп-шаблон найден
            • False           — истёк timeout
        """
        start_time = time.time()
        stop_thresh = stop_threshold if stop_threshold is not None else threshold

        while True:
            self.bot.memu.get_screenshot()
            shot = self.bot.memu.screenshot

            # 1) стоп-шаблон
            if stop_ref_name:
                score = self.template_matcher.find(shot, stop_ref_name, stop_thresh)
                if score:
                    self.logger.info(f"Стоп-шаблон '{stop_ref_name}' найден → возвращаем None")
                    return None

            # 2) целевой шаблон
            found = self.template_matcher.find(shot, ref_name, threshold)
            if found:
                self.logger.info(f"Шаблон '{ref_name}' найден → возвращаем имя")
                return ref_name

            # 3) timeout?
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                self.logger.error(
                    f"Таймаут {elapsed:.1f}s ≥ {timeout}s при поиске '{ref_name}' → возвращаем False"
                )
                return False

            # 4) повтор
            self.logger.debug(f"Не найдено '{ref_name}', повтор через {retry_delay}s…")
            time.sleep(retry_delay)

    def wait_for_templates(
        self,
        target_refs: List[str],
        stop_refs: List[str],
        threshold: float = 0.90,
        stop_threshold: Optional[float] = None,
        retry_delay: float = 2,
        timeout: float = 60
    ) -> str | None | bool:
        """
        Ждёт появления любого шаблона из target_refs.
        Если найден любой из stop_refs — возвращает None.
        Если таймаут — возвращает False.
        Если найден целевой шаблон — возвращает его имя.

        :return:
            • имя шаблона из target_refs (str)
            • None    — если найден один из stop_refs
            • False   — при истечении timeout
        """
        start_time = time.time()
        stop_thresh = stop_threshold if stop_threshold is not None else threshold

        while True:
            self.bot.memu.get_screenshot()
            shot = self.bot.memu.screenshot

            # 1) стоп-шаблоны
            for stop in stop_refs:
                score = self.template_matcher.find(shot, stop, stop_thresh)
                if score:
                    self.logger.info(f"Стоп-шаблон '{stop}' найден → возвращаем None")
                    return None

            # 2) целевые шаблоны
            for ref in target_refs:
                found = self.template_matcher.find(shot, ref, threshold)
                if found:
                    self.logger.info(f"Шаблон '{ref}' найден → возвращаем имя")
                    return ref

            # 3) timeout?
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                self.logger.error(
                    f"Таймаут {elapsed:.1f}s ≥ {timeout}s при поиске {target_refs} → возвращаем False"
                )
                return False

            # 4) повтор
            self.logger.debug(
                f"Ни один из {target_refs} не найден, повтор через {retry_delay}s…"
            )
            time.sleep(retry_delay)
