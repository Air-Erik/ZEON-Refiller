import os
import logging
from typing import Optional
from PIL import Image
import numpy as np
import cv2


class TemplateMatcher:
    """
    Ищет шаблон на скриншоте с помощью OpenCV matchTemplate.
    Создаётся как объект, хранит папку с эталонами и логгер.
    """

    def __init__(self, ref_dir: Optional[str] = None):
        # Настраиваем логгер
        self.logger = logging.getLogger(self.__class__.__name__)

        # Папка с шаблонами: если не передана, по умолчанию config/reference_images
        if ref_dir:
            self.ref_dir = ref_dir
        else:
            # Путь относительно этого файла
            self.ref_dir = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    '..', '..', 'config', 'reference_images'
                )
            )
        self.logger.debug(f"Используем папку шаблонов: {self.ref_dir}")

    def _load_template(self, ref_name: str) -> np.ndarray:
        """
        Загружает шаблон из файловой системы и возвращает его в градациях серого.
        """
        path = os.path.join(self.ref_dir, f"{ref_name}.png")
        if not os.path.exists(path):
            msg = f"Template not found: {path}"
            self.logger.error(msg)
            raise FileNotFoundError(msg)

        tmpl = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if tmpl is None:
            msg = f"Не удалось загрузить шаблон: {path}"
            self.logger.error(msg)
            raise IOError(msg)

        # Отбрасываем альфа-канал, если есть
        if tmpl.ndim == 3 and tmpl.shape[-1] == 4:
            tmpl = cv2.cvtColor(tmpl, cv2.COLOR_BGRA2BGR)
        # Конвертируем в градации серого
        gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)
        self.logger.debug(f"Шаблон '{ref_name}' загружен (shape={gray.shape})")
        return gray

    def find(self, screenshot: Image.Image, ref_name: str, threshold: float = 0.8) -> bool:
        """
        Ищет шаблон по всему скриншоту.

        :param screenshot: PIL.Image скриншот
        :param ref_name: имя файла шаблона без расширения .png
        :param threshold: порог нормированной корреляции [0.0–1.0]
        :return: True, если найден участок с корреляцией ≥ threshold
        """
        # Конвертация скриншота в grayscale numpy array
        img_arr = np.array(screenshot.convert('RGB'))  # RGB
        img_gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)

        # Загружаем шаблон
        tmpl_gray = self._load_template(ref_name)

        # Шаблонное соответствие
        res = cv2.matchTemplate(img_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # Логируем результат
        self.logger.info(
            f"Поиск шаблона '{ref_name}': val={max_val:.2f}, threshold={threshold:.2f}"
        )

        return max_val >= threshold
