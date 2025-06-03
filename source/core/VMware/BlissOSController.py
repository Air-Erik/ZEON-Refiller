import os
import logging
import subprocess
import time
import random
import inspect
import re
import numpy as np
import uiautomator2 as u2
import tempfile
import zipfile
import shutil
from PIL import Image
import xml.etree.ElementTree as ET
from typing import Tuple, List, Optional, Union
from uiautomator2.exceptions import UiObjectNotFoundError


# 1) Регистрируем новый уровень CORE между DEBUG(10) и INFO(20)
CORE_LEVEL_NUM = 15
logging.addLevelName(CORE_LEVEL_NUM, "CORE")


# 2) Добавляем метод Logger.core(...)
def core(self, message, *args, **kwargs):
    if self.isEnabledFor(CORE_LEVEL_NUM):
        self._log(CORE_LEVEL_NUM, message, args, **kwargs)


logging.Logger.core = core


def waitable_click(func):
    """
    Декоратор для всех u2_click_*-методов:
    - Если timeout is None (т.е. не передан или явно None) или timeout <= 0,
        метод клика выполняется сразу без ожидания.
    - Если timeout > 0, ждём появления текста в течение timeout секунд
        (с интервалом interval), а затем кликаем.
    """
    def wrapper(
        self,
        *args,
        timeout: float = None,
        interval: float = 5.0,
        **kwargs
    ):
        # если таймаут не задан или неположительный — сразу кликаем
        if timeout is None or timeout <= 0:
            return func(self, *args, **kwargs)

        # извлекаем из args цель ожидания (строка или список строк)
        target = args[0] if args else kwargs.get('partial_text') or kwargs.get('text_list')
        texts = [target] if isinstance(target, str) else list(target)

        start = time.time()
        while time.time() - start < timeout:
            found = self.u2_get_all_texts() or []
            # если хотя бы одно из ожидаемых в списке встречается на экране — выходим из цикла
            if any(t.lower() in txt.lower() for t in texts for txt in found):
                break
            time.sleep(interval)
        else:
            self.logger.warning(f"Не дождались {texts} за {timeout}s, пропускаем {func.__name__}")
            return False

        return func(self, *args, **kwargs)

    return wrapper


class BlissAdbManager:
    """Управление Android (Bliss OS в ESXi) через ADB и uiautomator2."""

    def __init__(self, adb_ip, adb_port="5555", time_wait=180):
        """Инициализация менеджера ADB и uiautomator2."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ip_port = f"{adb_ip}:{adb_port}"
        self.time_wait = time_wait

        self.screenshot = None
        self.swipe_coords = None

        self.connect()

    def _execute_command(self, cmd: List[str]) -> Optional[subprocess.CompletedProcess]:
        """Выполняет команду через subprocess.run с проверкой на ошибки

        Args:
            cmd (List[str]): Список строк с инструкциями

        Returns:
            Optional[subprocess.CompletedProcess]: Результат выполнения
            команды или None в случае ошибки.
        """
        self.logger.core(f"Выполняем: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.time_wait)
        except subprocess.TimeoutExpired:
            self.logger.error(f"Команда {' '.join(cmd)} зависла по таймауту.")
            return None

        if result.returncode != 0:
            self.logger.error(f"Ошибка выполнения команды {' '.join(cmd)}: {result.stderr.strip()}")
            return None

        return result

    def _sleep(self, sleep_range: Tuple[float, float]) -> None:
        """
        Выполняет случайную задержку в указанном диапазоне,
        логируя время задержки и имя вызывающего метода.
        """
        sleep_duration = random.uniform(*sleep_range)
        # Получаем имя метода, который вызвал _sleep
        caller = inspect.stack()[1].function
        self.logger.core(f"Задержка {sleep_duration:.2f} сек. вызвана из метода: {caller}")

        time.sleep(sleep_duration)

    def connect(self) -> bool:
        """
        Подключается к BlissOS через ADB и инициализирует uiautomator2.
        Проводит 5 попыток подключения с таймаутом в 10 секунд. Если все попытки не увенчались успехом,
        выбрасывает исключение подключения из модуля u2.

        Returns:
            bool: True при успешном подключении.

        Raises:
            u2.exceptions.TimeoutError: Если не удалось подключиться после 5 попыток.
        """
        attempts = 5
        for attempt in range(1, attempts + 1):
            self.logger.info(f"Попытка подключения {attempt}/{attempts}")
            result = self._execute_command(["adb", "connect", self.ip_port])

            if result is None:
                self.logger.warning("Команда adb connect не вернула результат.")
            else:
                stdout = result.stdout.lower().strip()
                if "connected to" in stdout or "already connected" in stdout:
                    self.logger.info(f"ADB подключение успешно: {result.stdout.strip()}")
                else:
                    self.logger.warning(f"Неожиданный ответ ADB: {result.stdout.strip()}")

            try:
                # Пытаемся подключиться через uiautomator2 с таймаутом в 10 секунд
                self.device = u2.connect(self.ip_port)
                self.logger.info(f"Подключение к uiautomator2 успешно: {self.device.info}")
                return True
            except Exception as e:
                self.logger.error(f"Ошибка подключения (попытка {attempt}): {e}")

            # Ожидание перед следующей попыткой
            time.sleep(10)

        # Если ни одна из попыток не увенчалась успехом, выбрасываем исключение u2
        raise u2.ConnectError(f"Не удалось подключиться к uiautomator2 после {attempts} попыток.")

    def get_adb_devices(self) -> Optional[List[str]]:
        """Возвращает список ADB-устройств

        Returns:
            Optional[List[str]]: Список доступных устройств
        """
        result = self._execute_command(["adb", "devices"])
        if result is None:
            return None

        lines = result.stdout.splitlines()
        devices = [line.split()[0] for line in lines[1:] if "device" in line]
        self.logger.core(f"Список ADB-устройств: {devices}")
        return devices

    def install_apk(
        self,
        apk_path: str = None,
        time_wait: int = 300
    ) -> bool:
        """
        Устанавливает APK на устройство через ADB, используя _execute_command.
        Ждёт до 5 минут (300 сек.).
        При неуспехе или таймауте выбрасывает исключение.

        Args:
            apk_path (str): Путь к APK-файлу.
            time_wait (int): Время в секундах на ожидание установки

        Returns:
            bool: True, если установка прошла успешно.

        Raises:
            TimeoutError: Если установка не завершилась за 5 минут.
            RuntimeError: Если ADB вернул любой другой отказ.
        """
        # временно увеличиваем таймаут для установки
        old_timeout = self.time_wait
        self.time_wait = time_wait

        # Выбираем путь к референсным картинкам:
        default_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '..', '..', '..',
                'config',
                '15213.apk'
            )
        )
        apk_path_final = apk_path or default_dir

        try:
            cmd = ["adb", "-s", self.ip_port, "install", "-r", apk_path_final]
            self.logger.core(f"Начинаем установку APK: {' '.join(cmd)}")
            result = self._execute_command(cmd)
        finally:
            # восстанавливаем прежний таймаут
            self.time_wait = old_timeout

        # result == None означает либо таймаут, либо ошибку ADB
        if result is None:
            self.logger.error(f"Установка APK {apk_path} не завершилась за 5 минут.")
            raise TimeoutError("Не удалось установить APK за 5 минут.")

        out = result.stdout.lower()
        if "success" in out:
            self.logger.info(f"APK {apk_path} установлен успешно.")
            return True
        else:
            # если ADB вернул Failure или что-то иное
            msg = result.stdout.strip() or result.stderr.strip()
            self.logger.error(f"Ошибка установки APK: {msg}")
            raise RuntimeError(f"Не удалось установить APK: {msg}")

    def install_xapk(
        self,
        xapk_path: str = None
    ) -> bool:
        """
        Устанавливает XAPK на устройство через ADB:
        1) распаковывает XAPK (переименованный ZIP);
        2) устанавливает все найденные APK через install_apk;
        3) копирует OBB-файлы в /storage/emulated/0/Android/obb/ на устройстве.

        Args:
            xapk_path (str): Путь к файлу .xapk (или .zip).
            time_wait (int): Время ожидания установки APK (секунды).

        Returns:
            bool: True, если всё прошло успешно.
        """
        # Выбираем путь к референсным картинкам:
        default_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '..', '..', '..',
                'config',
                'pns_7.0.190.xapk'
            )
        )
        xapk_path_final = xapk_path or default_dir

        # 2) распаковываем его во временный каталог
        temp_dir = tempfile.mkdtemp(prefix="xapk_")
        try:
            with zipfile.ZipFile(xapk_path_final, 'r') as z:
                z.extractall(temp_dir)

            # 3) находим все APK в корне распаковки
            apk_list = [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if f.lower().endswith('.apk')
            ]
            if not apk_list:
                raise RuntimeError("В XAPK нет ни одного APK-файла")

            # 4) ставим их одной командой
            cmd = ["adb", "-s", self.ip_port, "install-multiple", "-r"] + apk_list
            self.logger.info("Running: " + " ".join(cmd))
            result = self._execute_command(cmd=cmd)
            if result is None or "failure" in (result.stdout or "").lower():
                raise RuntimeError(
                    "Ошибка установки APK-сплитов: " +
                    (result.stderr or result.stdout or "")
                )
            self.logger.info("Все APK из XAPK успешно установлены")
            return True

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def launch_app(self, package_name: str, activity_name: str) -> bool:
        """Запуск конкретного приложения на устройстве

        Args:
            package_name (str): Название пакета
            activity_name (str): Точка входа, активность запуска приложения

        Returns:
            bool: При успешном запуске True, иначе False
        """
        cmd = ["adb", "-s", self.ip_port, "shell", "am", "start", "-n", f"{package_name}/{activity_name}"]
        result = self._execute_command(cmd)

        if "cmp=" in result.stdout or "Starting:" in result.stdout:
            self.logger.info(f"Приложение {package_name} запущено.")
            return True
        else:
            self.logger.warning(f"Ошибка запуска: {result.stdout.strip()}")
            return False

    def start_game(self) -> bool:
        """Запуск игры Puzzle & Survival

        Returns:
            bool: При успешном запуске True, иначе False
        """
        return self.launch_app("com.global.ztmslg.website", "com.games37.sdk.AtlasPluginDemoActivity")

    def open_app(self, packge_name: str = 'com.global.ztmslg.website') -> bool:
        """_summary_

        Args:
            packge_name (str, optional): _description_.
                Defaults 'com.global.ztmslg.website' or 'com.global.ztmslgru'

        Returns:
            bool: _description_
        """
        try:
            self.logger.core(
                f'Статус приложения {packge_name}: '
                f'{self.device.app_info(packge_name)}'
            )
            self.device.app_start(packge_name)
            self.logger.info(f'Приложение {packge_name} открыто')
            return True
        except Exception as e:
            self.logger.error(f'Ошибка запуска приложения {packge_name}: {e}')
            return False

    def close_app(self, packge_name: str = 'com.global.ztmslg.website') -> bool:
        """_summary_

        Args:
            packge_name (str, optional): _description_. Defaults to 'com.global.ztmslg.website'.

        Returns:
            bool: _description_
        """
        try:
            self.logger.core(f'Статус приложения {packge_name}: {self.device.app_info(packge_name)}')
            self.device.app_stop(packge_name)
            self.logger.info(f'Приложение {packge_name} закрыто')
            time.sleep(7)
            return True
        except Exception as e:
            self.logger.error(f'Ошибка закрытия приложения {packge_name}: {e}')
            return False

    def shutdown_device(self) -> bool:
        """Мягкое выключение устройства через ADB."""

        try:
            # Логируем информацию о попытке выключения устройства
            self.logger.core("Попытка мягкого выключения устройства...")

            # Выполняем команду ADB для выключения устройства
            cmd = ["adb", "-s", self.ip_port, "shell", "reboot", "-p"]
            result = self._execute_command(cmd)

            if result is None:
                self.logger.error("Не удалось выполнить команду для выключения устройства.")
                return False

            self.logger.info("Устройство успешно выключено.")
            time.sleep(10)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при выключении устройства: {e}")
            return False

    def unlock_device(self) -> bool:
        """Проверяет, заблокирован ли экран, и выполняет разблокировку устройства.

        Если экран выключен, включает его, а затем, если обнаруживается элемент блокировки,
        выполняется свайп для разблокировки. Предполагается, что устройство не защищено паролем.

        Returns:
            bool: True, если устройство успешно разблокировано или уже было разблокировано, иначе False.
        """
        try:
            # Получаем информацию об устройстве
            info = self.device.info

            # Если экран выключен, включаем его
            if not info.get('screenOn', True):
                self.logger.info("Экран выключен. Включаем экран...")
                self.device.screen_on()

            time.sleep(2)  # Ожидание для включения экрана

            # Проверяем наличие элемента, указывающего на блокировку экрана.
            # Используем resourceId "com.android.systemui:id/lock_icon".
            # В зависимости от устройства может потребоваться корректировка.
            if self.device(resourceId="com.android.systemui:id/lock_icon").exists:
                self.logger.info("Экран заблокирован, выполняем разблокировку...")
                width = info['displayWidth']
                height = info['displayHeight']
                # Выполняем свайп от нижней части экрана к верхней для разблокировки
                start_x = width / 2.1
                start_y = height * 0.7
                end_x = width / 2.1
                end_y = height * 0.3
                self.device.swipe(start_x, start_y, end_x, end_y, 0.5)
                time.sleep(1)
                self.logger.info("Устройство разблокировано.")
            else:
                self.logger.core("Устройство уже разблокировано.")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при разблокировке устройства: {e}")
            return False

    def _crop_screenshot(
        self,
        screenshot: Image.Image,
        frame: Tuple[float, float, float, float]
    ) -> Image.Image:
        """Обрезает скриншот по указанным координатам

        Args:
            screenshot (Image.Image): Объект PIL.Image для обрезки
            frame (Tuple[float, float, float, float]): Координаты (x1, y1, x2, y2)
                для обрезки в процентах от размера объекта PIL.Image

        Returns:
            Image.Image: Обрезанный объект PIL.Image
        """
        x1, y1, x2, y2 = frame

        left = int(x1 * self.device.info['displayWidth'])
        top = int(y1 * self.device.info['displayHeight'])
        right = int(x2 * self.device.info['displayWidth'])
        bottom = int(y2 * self.device.info['displayHeight'])

        self.logger.core(f'Проценты от экрана для обрезки скриншота: {frame}')
        self.logger.core(f'Координаты обрезки скриншота: {(left, top, right, bottom)}')
        return screenshot.crop((left, top, right, bottom))

    def get_screenshot(
        self,
        frame: Optional[Tuple[float, float, float, float]] = None
    ) -> Optional[Image.Image]:
        """
        Делает скриншот активного окна.

        :param frame: Координаты (x1, y1, x2, y2) для обрезки скриншота.
                    Координаты в процентах от размера экрана.
        :return: Скриншот в виде объекта PIL.Image или None в случае ошибки.
        """
        try:
            screenshot = self.device.screenshot()
            if frame:
                screenshot = self._crop_screenshot(screenshot, frame)
                self.logger.core(
                    'Сделан скриншот области экрана '
                    f'для устройства {self.ip_port}'
                )
            else:
                self.logger.core(
                    f'Сделан скриншот экрана для устройства {self.ip_port}'
                )
            self.screenshot = screenshot
            return screenshot
        except Exception as e:
            self.logger.error(f"Ошибка u2_screenshot: {e}")
            return None

    def _click_abs(
        self,
        X: int,
        Y: int,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Клик по точным координатам

        Args:
            X (int): Положительная X кооридана для клика в пикселях
            Y (int): Положительная Y кооридана для клика в пикселях
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном клике True, иначе False
        """
        try:
            self.device.click(X, Y)
            self.logger.core(f"Клик по координатам: ({X}, {Y})")
            self._sleep(sleep_range)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка клика: {e}")
            return False

    def click_percent(
        self,
        rel_x: float,
        rel_y: float,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Кликает по указанным относительным координатам

        Args:
            rel_x (float): Относительная координата по оси X (0.0 - 1.0)
            rel_y (float): Относительная координата по оси Y (0.0 - 1.0)
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном клике True, иначе False
        """
        info = self.device.info
        abs_x = int(rel_x * info['displayWidth'])
        abs_y = int(rel_y * info['displayHeight'])

        return self._click_abs(abs_x, abs_y, sleep_range)

    def click_esc(
        self,
        count: int = 1,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> None:
        """
        УСТАРЕВШИЙ МЕТОД! Рекомендую использовать метод esc.
        Кликакает в угол экрана, где предположительно находится кнопка назд.
        Делает указаное число раз. Устарвший метод, необходим в ограниченом
        числе механик

        Args:
            count (int, optional): Число кликов. По умолчанию 1
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)
        """
        for _ in range(count):
            self.click_percent(0.06, 0.02, sleep_range)

    def click_in_box(
        self,
        box: List[int],
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Клик в центр бокса от YOLO

        Args:
            box (List[int, int, int, int]):
                Список с координатами [x1, y1, x2, y2], где координаты указаны
                в пикселях относительно верхнего левого угла окна.
                Адаптировано под YOLO box
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном клике True, иначе False
        """
        x1, y1, x2, y2 = box

        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        return self._click_abs(center_x, center_y, sleep_range)

    def click_in_box_side(
        self,
        box: List[int],
        side: str,
        offset: float,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Кликает в указанную сторону бокса с заданным отступом

        Args:
            box (List[int, int, int, int]):
                Список с координатами [x1, y1, x2, y2], где координаты указаны
                в пикселях относительно верхнего левого угла окна.
                Адаптировано под YOLO box
            side (str):
                Сторона, куда нужно кликнуть ('left', 'right', 'top', 'down')
            offset (float): Отступ в пикселях от указанной стороны
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном клике True, иначе False
        """
        x1, y1, x2, y2 = box

        if side == 'left':
            click_x = x1 + offset
            click_y = y1 + (y2 - y1) / 2
        elif side == 'right':
            click_x = x2 - offset
            click_y = y1 + (y2 - y1) / 2
        elif side == 'top':
            click_x = x1 + (x2 - x1) / 2
            click_y = y1 + offset
        elif side == 'down':
            click_x = x1 + (x2 - x1) / 2
            click_y = y2 - offset
        else:
            self.logger.error(f'Неверно указана сторона: {side}')
            return False

        return self._click_abs(click_x, click_y, sleep_range)

    def click_box_with_offset(
        self,
        box: List[int],
        offset_x_percent: float = 0,
        offset_y_percent: float = 0,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ):
        """Клик в центр бокса со смещением. Смещение задается приращеним
        координат в процентах от размера экрана

        Args:
            box (List[int, int, int, int]):
                Список с координатами [x1, y1, x2, y2], где координаты указаны
                в пикселях относительно верхнего левого угла окна.
                Адаптировано под YOLO box
            offset_x_percent (float, optional): Смещение по оси X в процентах. Defaults to 0
            offset_y_percent (float, optional): Смещение по оси Y в процентах. Defaults to 0
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            _type_: При успешном клике True, иначе False
        """
        # Получаем размеры экрана
        width = self.device.info['displayWidth']
        height = self.device.info['displayHeight']

        # Координаты бокса
        x1, y1, x2, y2 = box

        # Находим центр бокса
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        # Рассчитываем абсолютные координаты с учетом смещения
        corrected_x = center_x + offset_x_percent * width
        corrected_y = center_y + offset_y_percent * height

        return self._click_abs(corrected_x, corrected_y, sleep_range)

    def _long_click_abs(
        self,
        X: int,
        Y: int,
        press_time: float = 1.0,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Продолжительный клик по точным координатам

        Args:
            X (int): Положительная X кооридана для клика в пикселях
            Y (int): Положительная Y кооридана для клика в пикселях
            press_time (float): Время зажатия в секундах
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном клике True, иначе False
        """
        try:
            self.device.long_click(X, Y, press_time)
            self.logger.core(
                f"Долгий клик по координатам: ({X}, {Y}), "
                f"с зажатием {press_time} c"
            )
            self._sleep(sleep_range)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка долгого клика: {e}")
            return False

    def long_click_percent(
        self,
        rel_x: float,
        rel_y: float,
        press_time: float = 1.0,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Продолжительный клик по указанным относительным координатам

        Args:
            rel_x (float): Относительная координата по оси X (0.0 - 1.0)
            rel_y (float): Относительная координата по оси Y (0.0 - 1.0)
            press_time (float): Время зажатия в секундах
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном клике True, иначе False
        """
        info = self.device.info
        abs_x = int(rel_x * info['displayWidth'])
        abs_y = int(rel_y * info['displayHeight'])

        return self._long_click_abs(abs_x, abs_y, press_time, sleep_range)

    def long_click_in_box(
        self,
        box: List[int],
        press_time: float = 1.0,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Продолжительный клик в центр бокса от YOLO

        Args:
            box (List[int, int, int, int]):
                Список с координатами [x1, y1, x2, y2], где координаты указаны
                в пикселях относительно верхнего левого угла окна.
                Адаптировано под YOLO box
            press_time (float): Время зажатия в секундах
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном клике True, иначе False
        """
        x1, y1, x2, y2 = box

        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        return self._long_click_abs(center_x, center_y, press_time, sleep_range)

    def _press_botton(
        self,
        botton: str = 'back',
        sleep_range: Tuple[float, float] = (0.4, 0.6)
    ) -> bool:
        """Эмулирует нажатие физической кнопки

        Args:
            botton (str, optional):
                Название кнопки для нажатия. Defaults to 'back'.
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном нажатие True, иначе False
        """
        try:
            self.device.press(botton)
            self.logger.core(f"Нажата кнопка {botton}")
            self._sleep(sleep_range)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при нажатии кнопки {botton}: {e}")
            return False

    def esc(
        self,
        count: int = 1,
        sleep_range: Tuple[float, float] = (0.4, 0.6)
    ) -> bool:
        """Эмулирует нажатие 'back' несколько раз

        Args:
            count (int, optional):
                Число повторений нажатия кнопки. Defaults to 1.
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешных нажатиях True, иначе False
        """
        for i in range(count):
            if not self._press_botton('back', sleep_range):
                self.logger.core(f'Закончено но нажатии номер {i}')
                return False
        return True

    def _swipe(
        self,
        start_coords: List[int],
        end_coords: List[int],
        duration_range: Tuple[float, float] = (0.1, 0.3),
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Выполняет свайп по указанным координатам

        Args:
            start_coords (List[int, int]):
                Список координат [x, y] для начальной позиции
            end_coords (List[int, int]):
                Список координат [x, y] для конечной позиции
            duration_range (Tuple[float, float], optional):
                Диапазон времени выполнения свайпа. По умолчанию (0.1, 0.3)
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном свайпе True, иначе False
        """
        try:
            start_x, start_y = start_coords
            end_x, end_y = end_coords

            duration = random.uniform(*duration_range)
            self.device.swipe(
                start_x, start_y, end_x, end_y, duration
            )
            self.logger.core(
                f'Свайп с ({start_x}, {start_y}) до ({end_x}, {end_y}) '
                f'продолжительность: {duration}'
            )
            self._sleep(sleep_range)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка свайпа: {e}")
            return False

    def swipe_percent(
        self,
        start_coords: List[float],
        end_coords: List[float],
        duration_range: Tuple[float, float] = (0.1, 0.3),
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> bool:
        """Выполняет свайп по указанным относительным координатам

        Args:
            start_coords (List[float, float]):
                Список относительных координат [x, y] для начальной позиции
            end_coords (List[float, float]):
                Список относительных координат [x, y] для конечной позиции
            duration_range (Tuple[float, float], optional):
                Диапазон времени выполнения свайпа. По умолчанию (0.1, 0.3)
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.8, 1.0)

        Returns:
            bool: При успешном свайпе True, иначе False
        """
        # Получаем размеры экрана
        width = self.device.info['displayWidth']
        height = self.device.info['displayHeight']
        coef = np.array([width, height])

        start_coords_px = (np.array(start_coords) * coef).astype(int).tolist()
        end_coords_px = (np.array(end_coords) * coef).astype(int).tolist()

        return self._swipe(
            start_coords_px, end_coords_px, duration_range, sleep_range
        )

    def swipe_units(
        self,
        box: List[int],
        offset: float = 300,
        duration_range: Tuple[float, float] = (0.1, 0.3),
        sleep_range: Tuple[float, float] = (1.1, 1.3)
    ) -> bool:
        """
        Свайпает от смещённого центра указанного бокса с использованием абсолютных координат.

        Вычисляется центр бокса с учётом смещения по оси X (offset).
        Затем определяется конечная точка свайпа, которая получается путем
        смещения центра по оси Y на 315 пикселей вверх. Итоговые координаты
        приводятся к целочисленному типу с помощью NumPy и передаются в
        метод _swipe для выполнения свайпа.

        Args:
            box (List[int]):
                Список с координатами [x1, y1, x2, y2] в пикселях относительно
                верхнего левого угла
            offset (float, optional):
                Смещение по оси X (в пикселях) для изменения центра бокса.
                По умолчанию 300.
            duration_range (Tuple[float, float], optional):
                Диапазон времени выполнения свайпа. По умолчанию (0.1, 0.3)
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (1.1, 1.3)

        Returns:
            bool: При успешном свайпе True, иначе False
        """
        x1, y1, x2, y2 = box

        # Вычисляем центр бокса с учетом смещения по оси X
        center = np.array([(x1 + x2) / 2 - offset, (y1 + y2) / 2])

        # Определяем конечную точку свайпа, смещая центр по оси Y на 315 пикселей вверх
        end_point = center.copy()
        end_point[1] -= 315

        # Преобразуем координаты в целочисленные значения
        start_coords_px = center.astype(int).tolist()
        end_coords_px = end_point.astype(int).tolist()

        # Выполняем свайп с рассчитанными относительными координатами
        return self._swipe(
            start_coords_px,
            end_coords_px,
            duration_range,
            sleep_range
        )

    def center_screen_on_box(
        self,
        box: List[int],
        coef_x: float = 0.5,
        coef_y: float = 0.5,
        duration_range: Tuple[float, float] = (0.1, 0.3),
        sleep_range: Tuple[float, float] = (0.4, 0.6),
        click: bool = False,
        tolerance_x: float = 0.1,
        tolerance_y: float = 0.3
    ) -> bool:
        """Центрирует экран по обнаруженной метке (боксу).

        Вычисляет центр бокса и сравнивает его с центром экрана.
        Если разница по осям (относительно размеров экрана) превышает
        допустимые допуски, выполняется свайп от центра бокса к центру экрана
        с учетом коэффициентов смещения. После свайпа, если флаг click=True,
        выполняется клик

        Args:
            box (List[int]):
                Список с координатами [x1, y1, x2, y2] в пикселях относительно
                верхнего левого угла
            coef_x (float, optional):
                Коэффициент для смещения по оси X. По умолчанию 0.5
            coef_y (float, optional):
                Коэффициент для смещения по оси Y. По умолчанию 0.5
            duration_range (Tuple[float, float], optional):
                Диапазон времени выполнения свайпа. По умолчанию (0.1, 0.3)
            sleep_range (Tuple[float, float], optional):
                Интервал ожидания после клика. По умолчанию (0.4, 0.6)
            click (bool, optional):
                Флаг для выполнения клика после центрирования.
                По умолчанию False
            tolerance_x (float, optional):
                Допустимое отклонение по оси X для проверки центра.
                По умолчанию 0.1.
            tolerance_y (float, optional):
                Допустимое отклонение по оси Y для проверки центра.
                По умолчанию 0.3.

        Returns:
            bool: При успешном свайпе/клике True, иначе False
        """
        # Получаем размеры экрана
        width = self.device.info['displayWidth']
        height = self.device.info['displayHeight']

        # Вычисляем центр бокса и центра экрана
        x1, y1, x2, y2 = box
        box_center = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
        screen_center = np.array([width / 2, height / 2])

        # Вычисляем необходимое смещение (дельту) для центрирования
        delta = (screen_center - box_center) * np.array([coef_x, coef_y])

        # Проверяем, насколько центр бокса отклоняется от центра экрана
        relative_delta = np.abs(delta) / np.array([width, height])
        if np.all(relative_delta <= np.array([tolerance_x, tolerance_y])):
            self.logger.core("Центр бокса уже находится в заданных пределах")
            if click:
                self.click_in_box(box)
        else:
            self.logger.core("Центр бокса вне допустимых пределов, выполняем центрирование.")

            # Начальные координаты для свайпа — центр бокса
            start_coords = box_center
            # Конечные координаты — центр бокса плюс рассчитанное смещение
            end_coords = box_center + delta

            # Преобразуем координаты в целочисленные значения с помощью NumPy
            start_coords_px = start_coords.astype(int).tolist()
            end_coords_px = end_coords.astype(int).tolist()

            self.logger.core(f"Свайп с {start_coords_px} до {end_coords_px}")

            # Выполняем свайп с использованием метода _swipe
            swipe_success = self._swipe(
                start_coords_px, end_coords_px, duration_range, sleep_range
            )

            if swipe_success and click:
                return self.click_percent(0.51, 0.49)
            return swipe_success

    def write(
        self,
        text: Union[str, int, float],
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ) -> Optional[str]:
        """Вводит текст в первое найденное текстовое поле (EditText)."""

        text_to_write = str(text)

        field = self.device(className="android.widget.EditText")
        if field.exists:
            try:
                # Очистка поля ввода
                field.clear_text()
                self.logger.core('Поле ввода очищено')

                # Ввод текста
                field.set_text(text_to_write)
                self.logger.core(f'Введен текст: {text_to_write}')

                # Вывод текста
                time.sleep(0.1)
                current_text = field.get_text()
                self.logger.core(
                    f'Окончательный текст в поле ввода: {current_text}'
                )

                self._press_botton()
                self._sleep(sleep_range)
                return current_text
            except Exception as e:
                self.logger.error(f"Ошибка вставки текста: {e}")
                return None
        else:
            self.logger.error('Поле ввода не найдено')
            return None

    def _generate_swipe_coords(self, rows: int, columns: int):
        swipe_coords = []
        for row in range(rows):
            for col in range(columns):
                if col > 0:
                    if row % 2 == 0:
                        swipe_coords.append(([0.65, 0.5], [0.35, 0.5]))
                    else:
                        swipe_coords.append(([0.35, 0.5], [0.65, 0.5]))
            if row < rows - 1:
                swipe_coords.append(([0.5, 0.60], [0.5, 0.40]))
        self.logger.core(f'Сгенерированные координаты свайпов: {swipe_coords}')
        return swipe_coords

    def disconnect(self):
        """Отключает ADB-соединение."""
        self._execute_command(["adb", "disconnect", self.ip_port])

    def change_screen_size(self, width: int, height: int, sleep_range: Tuple[float, float] = (0.8, 1.0)) -> bool:
        """
        Изменяет размер экрана устройства через adb.

        Args:
            width (int): Новая ширина экрана.
            height (int): Новая высота экрана.
            sleep_range (Tuple[float, float], optional):
                Диапазон времени задержки после выполнения команды. По умолчанию (0.8, 1.0).

        Returns:
            bool: True если команда выполнена успешно, иначе False.
        """
        resolution = f"{width}x{height}"
        cmd = ["adb", "-s", self.ip_port, "shell", "wm", "size", resolution]
        result = self._execute_command(cmd)
        if result is None:
            self.logger.error("Не удалось изменить размер экрана.")
            return False

        self._sleep(sleep_range)

        if result.stdout.strip():
            self.logger.info(f"Размер экрана изменен на {resolution}: {result.stdout.strip()}")
        else:
            self.logger.info(f"Размер экрана изменен на {resolution}")
        return True

    # * u2
    def _find_elements(
        self,
        by: str,
        value: str,
        enabled: bool = True,
        retries: int = 1,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ):
        """
        Универсальный метод поиска элементов по заданному критерию с возможностью повторных попыток.

        Args:
            by (str): Критерий поиска ("class", "textContains", и т.п.).
            value (str): Значение для поиска.
            enabled (bool, optional): Фильтр по доступности элемента. По умолчанию True.
            retries (int, optional): Число попыток поиска. По умолчанию 1 (без повторов).
            sleep_range (float, optional): (Tuple[float, float], optional):
                Диапазон времени задержки после выполнения команды. По умолчанию (0.8, 1.0).

        Returns:
            Результат поиска (список элементов) или None, если элементы не найдены.
        """
        caller = inspect.stack()[1].function

        for attempt in range(retries):
            if by == "class":
                elements = self.device(className=value, enabled=enabled)
            elif by == "textContains":
                elements = self.device(textContains=value)
            else:
                self.logger.error(f'Неподдерживаемый критерий поиска: {by}')
                return None

            if elements:
                self.logger.core(f'Найдены элементы: {elements}. Вызвов из метода: {caller}')
                return elements
            else:
                self.logger.warning(
                    f"Попытка {attempt+1}/{retries}: Элементы по {by}="
                    f"'{value}' пока не найдены. Вызвов из метода: {caller}"
                )
                self._sleep(sleep_range)

        self.logger.error(
            f"Исчерапано {retries} попыток. Элементы по {by}='{value}' "
            f"не найдены. Вызвов из метода: {caller}"
        )
        return None

    def _get_element_text(self, element) -> str:
        """
        Безопасно получает текст элемента, перехватывая исключение UiObjectNotFoundError.
        Если возникает ошибка, возвращает пустую строку.
        """
        try:
            return element.info.get('text', '')
        except UiObjectNotFoundError as e:
            self.logger.warning(f"Элемент не найден при получении информации: {e}")
            return ""

    def _safe_click(self, element) -> bool:
        """
        Безопасно выполняет клик по элементу. Если элемент не найден при клике,
        перехватывает исключение и возвращает False.
        """
        try:
            element.click()
            self.logger.core(
                f"Нажатие на элемент {element.info.get('className')} "
                f"с текстом {element.info.get('text')}")
            return True
        except UiObjectNotFoundError as e:
            self.logger.warning(f"Элемент не найден при попытке нажать: {e}")
            return False

    def _select_edit_text_field(
        self,
        retries: int = 5,
        sleep_range: Tuple[float, float] = (0.8, 1.0)
    ):
        """
        Находит все поля ввода с классом 'android.widget.EditText', сортирует их по вертикальному положению
        и выбирает подходящее поле. Предпочтение отдается пустым полям ввода.

        Returns:
            Выбранное поле ввода или None, если поля не найдены.
        """
        fields = self._find_elements(
            "class",
            "android.widget.EditText",
            retries=retries,
            sleep_range=sleep_range
        )
        if not fields:
            self.logger.error('Поля ввода не найдены после нескольких попыток')
            return None

        # Приводим найденные элементы к списку, если возвращён не список
        try:
            fields_list = list(fields)
        except Exception:
            fields_list = [fields]

        # Сортировка по координате "top", полученной из info/bounds
        sorted_fields = sorted(
            fields_list,
            key=lambda field: field.info.get('bounds', {}).get('top', 0)
        )

        # Ищем среди отсортированных полей первое, у которого текст пустой
        chosen_field = None
        for field in sorted_fields:
            if not self._get_element_text(field).strip():
                self.logger.core('Найдено пустое поле')
                chosen_field = field
                break

        # Если ни одно поле не пусто, выбираем самое верхнее
        if chosen_field is None:
            self.logger.core('Пустого поля нет, выбираем верхнее')
            chosen_field = sorted_fields[0]

        return chosen_field

    def u2_wait_for_text(
        self,
        partial_text: str,
        timeout: int = None,
        interval: float = 5.0
    ) -> bool:
        """
        Ждет появления текста на экране в течение timeout секунд.
        Возвращает True, если текст появился, иначе False.
        """
        timeout = timeout or self.time_wait
        start = time.time()
        while time.time() - start < timeout:
            texts = self.u2_get_all_texts() or []
            if any(partial_text.lower() in t.lower() for t in texts):
                self.logger.info(f"Найден текст «{partial_text}»")
                return True
            time.sleep(interval)
        self.logger.warning(f"Таймаут ожидания текста «{partial_text}» ({timeout}s)")
        return False

    def u2_fill_input_field(
        self,
        text: str,
        sleep_range: Tuple[float, float] = (0.6, 0.7),
        is_password: bool = False
    ) -> Optional[str]:
        """
        Находит поле ввода (android.widget.EditText) и заполняет его текстом.
        При ошибке возвращает None.
        """
        input_field = self._select_edit_text_field(
            retries=5,
            sleep_range=sleep_range
        )
        if input_field and input_field.exists:
            input_field.click()
            input_field.set_text(text)

            if is_password:
                self.logger.core("Пароль успешно введен в поле ввода.")
            else:
                self.logger.core(f'Текст "{text}" успешно введен в поле ввода.')

            entered_text = input_field.get_text()
            self._sleep(sleep_range)
            return entered_text
        else:
            self.logger.error('Поле ввода не найдено после нескольких попыток.')
            self._sleep(sleep_range)
            return None

    @waitable_click
    def u2_click_button(
        self,
        partial_text: str = "Продолжить",
        sleep_range: Tuple[float, float] = (0.6, 0.7)
    ) -> bool:
        """
        Находит кнопку (android.widget.Button) с текстом, содержащим
        partial_text, и нажимает её. Возвращает True при успехе, иначе False.
        """
        buttons = self._find_elements(
            "class", "android.widget.Button", retries=5
        )
        if buttons:
            for button in buttons:
                button_text = self._get_element_text(button)

                if re.search(partial_text, button_text, re.IGNORECASE):
                    if self._safe_click(button):
                        self.logger.core(
                            f"Кнопка с текстом '{button_text}' успешно нажата."
                        )
                        self._sleep(sleep_range)
                        return True

        self.logger.error("Кнопка не найдена.")
        self._sleep(sleep_range)
        return False

    @waitable_click
    def u2_click_button_from_list(
        self,
        text_list: List[str] = ["Продолжить"],
        sleep_range: Tuple[float, float] = (0.6, 0.7)
    ) -> bool:
        """
        Находит кнопку с текстом, содержащим хотя бы один элемент из text_list, и нажимает её.
        Возвращает True при успехе, иначе False.
        """
        if text_list is None:
            text_list = []

        buttons = self._find_elements(
            "class", "android.widget.Button", retries=3
        )
        if buttons:
            for button in buttons:
                btn_text = self._get_element_text(button)
                for part in text_list:
                    if re.search(part, btn_text, re.IGNORECASE):
                        bounds = button.info.get("bounds", {})
                        left, top = bounds["left"], bounds["top"]
                        right, bottom = bounds["right"], bounds["bottom"]
                        cx = (left + right) // 2
                        cy = (top + bottom) // 2

                        # ! Клик через координаты обязателен для входа в
                        # ! гугл акк. _safe_click не видит кнопку в самом конце
                        if self._click_abs(cx, cy, sleep_range):
                            self.logger.core(f"Координатный клик по '{btn_text}' ({cx},{cy}).")
                            return True

        self.logger.error("Кнопка не найдена по заданному списку текстов.")
        self._sleep(sleep_range)
        return False

    @waitable_click
    def u2_click_text(
        self,
        partial_text: str = "Продолжить",
        sleep_range: Tuple[float, float] = (0.6, 0.7)
    ) -> bool:
        """
        Находит элемент по тексту и выполняет клик.
        Возвращает True при успехе, иначе False.
        """
        elements = self._find_elements("textContains", "", retries=5)
        if elements:
            for element in elements:
                element_text = self._get_element_text(element)
                if re.search(partial_text, element_text, re.IGNORECASE):
                    if self._safe_click(element):
                        self.logger.core(
                            f"Элемент с текстом '{element_text}' успешно нажат"
                        )
                        self._sleep(sleep_range)
                        return True

        self.logger.error(f"Элемент с текстом '{partial_text}' не найден.")
        self._sleep(sleep_range)
        return False

    @waitable_click
    def u2_click_text_from_list(
        self,
        text_list: List[str] = ["Продолжить"],
        sleep_range: Tuple[float, float] = (0.6, 0.7)
    ) -> bool:
        """
        Находит элемент по тексту, содержащему хотя бы один элемент из text_list, и выполняет клик.
        Возвращает True при успехе, иначе False.
        """
        if text_list is None:
            text_list = []

        elements = self._find_elements("textContains", "", retries=5)
        if elements:
            for element in elements:
                element_text = self._get_element_text(element)
                for partial_text in text_list:
                    if re.search(partial_text, element_text, re.IGNORECASE):
                        if self._safe_click(element):
                            self.logger.core(
                                f"Элемент с текстом '{element_text}' успешно нажат."
                            )
                            self._sleep(sleep_range)
                            return True

        self.logger.error(f"Элемент с текстом из списка {text_list} не найден.")
        self._sleep(sleep_range)
        return False

    @waitable_click
    def u2_click_switch(
        self,
        partial_text: str = None,
        sleep_range: Tuple[float, float] = (0.6, 0.7)
    ) -> bool:
        """
        Находит все переключатели android.widget.Switch и кликает по каждому.
        Если передан partial_text, применяет фильтр по тексту перед нажатием.
        Возвращает True, если хотя бы один клик выполнен успешно.
        """
        # Ищем все switch-элементы
        switches = self._find_elements(
            "class", "android.widget.Switch", retries=5
        )
        if not switches:
            self.logger.error("Переключатели не найдены.")
            return False

        clicked_any = False
        for switch in switches:
            # Фильтрация по тексту (если нужно)
            if partial_text:
                switch_text = self._get_element_text(switch)
                if not re.search(partial_text, switch_text, re.IGNORECASE):
                    continue
            # Пытаемся нажать безопасно
            if self._safe_click(switch):
                clicked_any = True
                self._sleep(sleep_range)
            else:
                self.logger.error("Не удалось нажать переключатель.")

        if not clicked_any:
            self.logger.error("Не был выполнен ни один клик по переключателю.")
        return clicked_any

    def u2_get_all_texts(self) -> List[str]:
        """
        Возвращает список всех текстов, найденных на экране.
        """
        time.sleep(1)
        elements = self._find_elements("textContains", "", retries=1)

        all_texts = []

        if elements:
            for element in elements:
                try:
                    if element.exists:
                        element_text = element.info.get('text', '')
                        if element_text:
                            all_texts.append(element_text)
                except Exception as e:
                    self.logger.warning(
                        f"Ошибка получения информации об элементе: {e}"
                    )
                    continue

        if all_texts:
            self.logger.core(f"Найдены тексты на экране: {all_texts}")
        else:
            self.logger.error("Тексты на экране не найдены")
        return all_texts

    def u2_get_all_elements(self) -> List[dict]:
        """
        Возвращает список словарей с информацией обо всех элементах, полученных из XML иерархии.
        """
        xml_content = self.device.dump_hierarchy()
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            self.logger.error(f"Ошибка парсинга XML: {e}")
            return []

        elements_info = []
        for elem in root.iter():
            info_dict = {
                "class": elem.attrib.get('class', ''),
                "text": elem.attrib.get('text', ''),
                "resource-id": elem.attrib.get('resource-id', ''),
                "content-desc": elem.attrib.get('content-desc', ''),
                "bounds": elem.attrib.get('bounds', '')
            }
            self.logger.debug(
                f"Класс: {info_dict['class']}, Текст: '{info_dict['text']}', "
                f"ID: {info_dict['resource-id']}, Описание: {info_dict['content-desc']}, "
                f"Границы: {info_dict['bounds']}"
            )
            elements_info.append(info_dict)
        return elements_info


if __name__ == "__main__":
    # Пример использования
    manager = BlissAdbManager(adb_ip="172.16.100.214")

    # Подключаемся
    manager.connect()
    manager.shutdown_device()
