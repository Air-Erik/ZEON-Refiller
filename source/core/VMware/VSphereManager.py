import os
import time
import socket
import logging
from functools import wraps
from typing import Optional, List, Any

from pyVmomi import vim
from .VSphereConnection import VSphereConnection
from .NSXManager import NSXManager
from ...exceptions.vsphere import (
    VMPowerOnError,
    VMSuspendError,
    VMPowerOffError,
    VMCloneError,
    VMDeleteError,
    VMNotFoundError,
    VMIPNotFoundError,
    VMWaitReadyError,
    VMReconfigureError
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ensure_vm_connection(fn):
    @wraps(fn)
    def wrapper(self, vm: vim.VirtualMachine, *args, **kwargs):
        # попытка переподключиться (метод у вас уже возвращает True, если была ре-коннект)
        reconnected = self.reconnect_if_needed()

        # если сессия пересоздалась — надо взять свежий объект ВМ
        if reconnected:
            new_vm = self.get_vm_by_name(vm.name)

            if not new_vm:
                raise VMNotFoundError(vm.name, logger=self.logger)
            vm = new_vm

        return fn(self, vm, *args, **kwargs)
    return wrapper


class VSphereManager(VSphereConnection):
    """
    Класс для управления vSphere через pyVmomi.
    Позволяет клонировать ВМ из шаблона, запускать, получать IP, изменять конфигурацию,
    выключать и удалять ВМ, а также получать объект ВМ по имени или IP.
    """

    def __init__(self, host: str, user: str, pwd: str, port: int = 443) -> None:
        """
        Инициализация подключения к vCenter.
        :param host: Хост vCenter (например, "vcenter.example.com").
        :param user: Имя пользователя для аутентификации.
        :param pwd: Пароль.
        :param port: Порт подключения (по умолчанию 443).
        """
        super().__init__(host, user, pwd, port)

        self.logger = logging.getLogger(self.__class__.__name__)

        self.nsx = NSXManager(
            host=os.getenv("NSX_HOST"),
            username=os.getenv("NSX_USER"),
            password=os.getenv("NSX_PASSWORD"),
            switch_name=os.getenv("NSX_SWITCH_NAME"),
            port=os.getenv("NSX_PORT")
        )

    def get_obj(self, vimtype: list, name: str) -> Optional[Any]:
        """
        Поиск объекта vSphere по имени.
        :param vimtype: Список классов (например, [vim.VirtualMachine]).
        :param name: Имя объекта.
        :return: Найденный объект или None.
        """
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
        for obj in container.view:
            if obj.name == name:
                return obj
        return None

    def get_vm_by_name(self, name: str) -> Optional[vim.VirtualMachine]:
        """
        Получить объект виртуальной машины по имени.
        :param name: Имя ВМ.
        :return: Объект виртуальной машины или None.
        """
        return self.get_obj([vim.VirtualMachine], name)

    @ensure_vm_connection
    def get_vm_ip(
        self,
        vm: vim.VirtualMachine,
        timeout: int = 300
    ) -> Optional[str]:
        """Получение IP-адреса ВМ по MAC адресу

        Args:
            vm (vim.VirtualMachine): Объект виртуальной машины
            param timeout (int, optional): Максимальное время ожидания

        Returns:
            Optional[str]: IP-адрес или выбрасывается исключение
        """
        mac_address: Optional[str] = None

        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualEthernetCard):
                mac_address = device.macAddress
        if not mac_address:
            self.logger.error(f"VM '{vm.name}': MAC address not found.")
            raise VMIPNotFoundError(vm.name, "Unknown", logger=self.logger)

        start_time = time.time()
        while time.time() - start_time < timeout:
            res_ip = self.nsx.get_ip_by_mac(mac_address)

            if res_ip:
                return res_ip
            else:
                time.sleep(5)
        raise VMIPNotFoundError(vm.name, mac_address, logger=self.logger)

    def _get_vm_list(self) -> List[vim.VirtualMachine]:
        """
        Получаем список всех виртуальных машин с хоста.
        :return: Список объектов виртуальных машин.
        """
        self.reconnect_if_needed()
        vm_list = []
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.VirtualMachine], True
        )
        for vm in container.view:
            vm_list.append(vm)

        self.logger.debug(f'Список всех ВМ: {vm_list}')
        return vm_list

    def create_folder(self, folder_name: str, parent_folder: vim.Folder) -> Optional[vim.Folder]:
        """
        Создание папки с заданным именем в указанном родительском каталоге.
        :param folder_name: Имя создаваемой папки.
        :param parent_folder: Родительская папка для создания нового каталога.
        :return: Новый объект папки или None, если создание не удалось.
        """
        self.reconnect_if_needed()
        self.logger.info(f"Попытка создать папку '{folder_name}' в родительской папке '{parent_folder.name}'...")
        try:
            new_folder = parent_folder.CreateFolder(folder_name)
            self.logger.info(f"Папка '{folder_name}' успешно создана.")
            return new_folder
        except Exception as e:
            self.logger.exception(f"Не удалось создать папку '{folder_name}': {e}")
            return None

    def wait_for_task(self, task: vim.Task) -> Any:
        """
        Ожидание завершения задачи.
        :param task: Задача vSphere.
        :return: Результат задачи.
        :raises Exception: При ошибке выполнения задачи.
        """
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            time.sleep(1)
        if task.info.state == vim.TaskInfo.State.error:
            raise Exception(f"Task failed: {task.info.error.msg}")
        return task.info.result

    def clone_vm(self, source_vm_name: str, new_vm_name: str, folder_name: Optional[str] = None) -> vim.VirtualMachine:
        """
        Клонирование виртуальной машины на основе существующей ВМ.
        Новая ВМ будет создана либо в указанной папке, либо в той же, что и исходная ВМ,
        если папка не указана или создание указанной папки не удалось.

        :param source_vm_name: Имя исходной виртуальной машины.
        :param new_vm_name: Имя новой виртуальной машины.
        :param folder_name: Необязательное имя папки для размещения клона.
        :return: Объект созданной виртуальной машины.
        :raises VMCloneError: Если исходная ВМ не найдена или операция клонирования завершилась ошибкой.
        """
        source_vm = self.get_vm_by_name(source_vm_name)
        if source_vm is None:
            raise VMCloneError(
                new_vm_name, logger=self.logger,
                details=f"Исходная ВМ '{source_vm_name}' не найдена."
            )

        # Используем те же параметры, что у исходной ВМ:
        # Папка, ресурсный пул и datastore
        original_folder = source_vm.parent
        resource_pool = source_vm.resourcePool

        if not source_vm.datastore:
            raise VMCloneError(
                new_vm_name, logger=self.logger,
                details="Нет привязанных datastore у исходной ВМ."
            )
        datastore = source_vm.datastore[0]  # Если их несколько, выбираем первый

        # Определяем папку для клонирования:
        destination_folder = original_folder
        if folder_name:
            if '/' in folder_name:
                # если передан путь, то гарантированно его "пробиваем"
                destination_folder = self.ensure_folder_path(folder_name)
            else:
                # старая логика — просто имя
                folder_candidate = self.get_obj([vim.Folder], folder_name)
                if folder_candidate is None:
                    base = original_folder.parent or original_folder
                    folder_candidate = self.create_folder(folder_name, base)
                if folder_candidate:
                    destination_folder = folder_candidate
                else:
                    self.logger.warning(
                        f"Не удалось создать папку '{folder_name}', "
                        f"клонируем в '{original_folder.name}'"
                    )

        # Создание спецификации для relocate
        relospec = vim.vm.RelocateSpec()
        relospec.pool = resource_pool
        relospec.datastore = datastore

        # Спецификация клонирования
        clonespec = vim.vm.CloneSpec()
        clonespec.location = relospec
        clonespec.powerOn = False

        self.logger.info(f"Клонирование ВМ '{new_vm_name}' из исходной ВМ '{source_vm_name}'...")
        try:
            task = source_vm.Clone(folder=destination_folder, name=new_vm_name, spec=clonespec)
            self.wait_for_task(task)
        except Exception as e:
            raise VMCloneError(new_vm_name, logger=self.logger, details=str(e)) from e

        vm = self.get_vm_by_name(new_vm_name)
        if vm is None:
            raise VMCloneError(new_vm_name, logger=self.logger,
                               details="Клонированная ВМ не обнаружена после создания.")
        self.logger.info(f"ВМ '{new_vm_name}' успешно клонирована.")
        return vm

    @ensure_vm_connection
    def power_on_vm(self, vm: vim.VirtualMachine) -> None:
        """
        Включение виртуальной машины.
        :param vm: Объект виртуальной машины.
        """
        current_state = vm.runtime.powerState
        if current_state == vim.VirtualMachinePowerState.poweredOn:
            self.logger.info(f"VM '{vm.name}' уже включена.")
            return

        self.logger.info(f"Запуск VM '{vm.name}'...")
        task = vm.PowerOn()
        try:
            self.wait_for_task(task)
            self.logger.info(f"VM '{vm.name}' успешно запущена.", )
        except Exception as e:
            # Если ошибка не связана с уже запущенной машиной,
            # выбрасываем специальное исключение
            raise VMPowerOnError(
                vm_name=vm.name,
                current_state=current_state,
                logger=self.logger
            ) from e

    @ensure_vm_connection
    def suspend_vm(self, vm: vim.VirtualMachine) -> None:
        """
        Приостановка виртуальной машины (Suspend).

        :param vm: Объект виртуальной машины.
        :raises VMSuspendError: Если операция приостановки завершилась ошибкой.
        """
        current_state = vm.runtime.powerState
        if current_state == vim.VirtualMachinePowerState.suspended:
            self.logger.info(f"VM '{vm.name}' уже находится в состоянии приостановки.")
            return

        self.logger.info(f"Приостановка VM '{vm.name}'...")
        try:
            task = vm.Suspend()  # Инициируем задачу suspend
            self.wait_for_task(task)
            self.logger.info(f"VM '{vm.name}' успешно приостановлена.")
        except Exception as e:
            raise VMSuspendError(vm.name, logger=self.logger, details=str(e)) from e

    @ensure_vm_connection
    def power_off_vm(self, vm: vim.VirtualMachine) -> None:
        """Выключение виртуальной машины

        Args:
            vm (vim.VirtualMachine): Объект виртуальной машины

        Raises:
            VMPowerOffError: Если выключение завершилось ошибкой
        """
        current_state = vm.runtime.powerState
        if current_state == vim.VirtualMachinePowerState.poweredOff:
            self.logger.info(f"VM '{vm.name}' уже выключена.")
            return

        self.logger.info(f"Остановка VM '{vm.name}'...")
        task = vm.PowerOff()
        try:
            self.wait_for_task(task)
            self.logger.info(f"VM '{vm.name}' успешно остановлена.")
        except Exception as e:
            raise VMPowerOffError(
                vm_name=vm.name,
                current_state=current_state,
                logger=self.logger
            ) from e

    @ensure_vm_connection
    def restart_vm(self, vm: vim.VirtualMachine, timeout: int = 300) -> str:
        """
        Безопасно перезапустить ВМ:
        1) Попробовать выключить (игнорируя ошибки),
        2) Включить,
        3) Дождаться готовности (ADB check) и вернуть IP.

        :param vm: Объект виртуальной машины.
        :param timeout: Таймаут ожидания готовности в секундах.
        :return: IP-адрес перезапущенной VM.
        :raises VMPowerOnError: если не удалось включить ВМ.
        :raises VMWaitReadyError: если ВМ не стала готовой в указанный timeout.
        """
        self.logger.info(f"Перезапуск VM '{vm.name}'…")

        # 1. Пытаемся выключить (если уже выключена — метод сам ничего не сделает)
        try:
            self.power_off_vm(vm)
        except Exception as e:
            self.logger.warning(f"Не удалось выключить VM '{vm.name}': {e}")

        # 2. Включаем
        try:
            self.power_on_vm(vm)
        except VMPowerOnError as e:
            self.logger.error(f"Ошибка при включении VM '{vm.name}': {e}")
            raise

        # 3. Ждём готовности и возвращаем IP
        try:
            ip = self.wait_for_vm_ready(vm, timeout)
            self.logger.info(f"VM '{vm.name}' перезапущена и готова (IP: {ip})")
            return ip
        except VMWaitReadyError as e:
            self.logger.error(f"VM '{vm.name}' не стала готовой после перезапуска: {e}")
            raise

    @ensure_vm_connection
    def delete_vm(self, vm: vim.VirtualMachine) -> None:
        """Удаление виртуальной машины.

        Args:
            vm (vim.VirtualMachine): Объект виртуальной машины

        Raises:
            VMDeleteError: Если удаление завершилось ошибкой
        """
        name = vm.name
        self.logger.info(f"Удаление VM '{name}'...")
        task = vm.Destroy_Task()
        try:
            self.wait_for_task(task)
            self.logger.info(f"VM '{name}' была удалена.")
        except Exception as e:
            raise VMDeleteError(
                name, logger=self.logger, details=str(e)
            ) from e

    def delete_vm_by_name(self, vm_name: str) -> None:
        """Удаление виртуальной машины по имени

        Args:
            vm (str): Имя виртуальной машины

        Raises:
            VMDeleteError: Если удаление завершилось ошибкой
        """
        self.reconnect_if_needed()
        vm = self.get_vm_by_name(vm_name)
        self.logger.info(f"Удаление VM '{vm_name}'...")
        task = vm.Destroy_Task()
        try:
            self.wait_for_task(task)
            self.logger.info(f"VM '{vm_name}' была удалена.")
        except Exception as e:
            raise VMDeleteError(
                vm_name, logger=self.logger, details=str(e)
            ) from e

    @ensure_vm_connection
    def wait_for_vm_ready(self, vm: vim.VirtualMachine, timeout: int = 300) -> str:
        """
        Ожидание, пока VM будет доступна для подключения (через ADB).
        Поскольку VMware Tools отсутствуют, полагаемся на возможность установления TCP-соединения на порту ADB.
        :param vm: Объект виртуальной машины.
        :param timeout: Максимальное время ожидания в секундах.
        :return: str c ip готовой машины, иначе выбрасывает Exception.
        :raises Exception: При истечении timeout.
        """
        self.logger.info(f"Waiting for VM '{vm.name}' to become ready (ADB check)...")
        ip = self.get_vm_ip(vm)
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.create_connection((ip, 5555), timeout=5):
                    self.logger.info(f"VM '{vm.name}' is ready for ADB connection.")
                    time.sleep(1)
                    return ip
            except Exception:
                time.sleep(2)
        raise VMWaitReadyError(vm.name, timeout, logger=self.logger)

    @ensure_vm_connection
    def reconfigure_vm(self, vm: vim.VirtualMachine, num_cpus: int, memory_mb: int) -> None:
        """
        Изменение конфигурации виртуальной машины.
        :param vm: Объект виртуальной машины.
        :param num_cpus: Новое количество виртуальных CPU.
        :param memory_mb: Новый объем памяти в мегабайтах.
        :raises VMReconfigureError: Если задача изменения конфигурации завершилась ошибкой.
        """
        self.logger.info(f"Reconfiguring VM '{vm.name}': CPUs={num_cpus}, Memory={memory_mb}MB")
        spec = vim.vm.ConfigSpec()
        spec.numCPUs = num_cpus
        spec.memoryMB = memory_mb
        task = vm.ReconfigVM_Task(spec=spec)
        try:
            self.wait_for_task(task)
            self.logger.info(f"VM '{vm.name}' reconfigured successfully.")
        except Exception as e:
            raise VMReconfigureError(vm.name, logger=self.logger, details=str(e)) from e

    @ensure_vm_connection
    def rename_vm(self, vm: vim.VirtualMachine, new_name: str) -> None:
        """
        Переименование виртуальной машины.
        :param vm: Объект виртуальной машины.
        :param new_name: Новое имя для виртуальной машины.
        :raises Exception: Если операция переименования завершилась ошибкой.
        """
        self.logger.info(f"Переименование VM '{vm.name}' в '{new_name}'...")
        try:
            # Запуск задачи переименования
            task = vm.Rename_Task(newName=new_name)
            self.wait_for_task(task)
            self.logger.info(f"VM успешно переименована в '{new_name}'.")
        except Exception as e:
            raise Exception(f"Ошибка при переименовании VM '{vm.name}': {e}") from e

    def get_vm_details(self, vm: vim.VirtualMachine) -> dict:
        """
        Получение детальной информации о виртуальной машине.
        :param vm: Объект виртуальной машины.
        :return: Словарь с ключевыми характеристиками VM.
        """
        details = {
            "name": vm.name,
            "power_state": vm.runtime.powerState,
            "ip_address": None,
            "cpu": None,
            "memory": None,
            "datastores": None
        }
        details["ip_address"] = vm.guest.ipAddress if vm.guest and vm.guest.ipAddress else "Unknown"
        details["cpu"] = vm.config.hardware.numCPU if vm.config and vm.config.hardware else "Unknown"
        details["memory"] = vm.config.hardware.memoryMB if vm.config and vm.config.hardware else "Unknown"
        if vm.datastore:
            details["datastores"] = [ds.name for ds in vm.datastore]
        else:
            details["datastores"] = "None"
        return details

    def ensure_folder_path(self, folder_path: str) -> vim.Folder:
        """
        Гарантированно вернёт vim.Folder по пути "DC1/ZeonVM/Prod/LoginVMs",
        создавая промежуточные папки, если их нет.
        """
        parts = folder_path.split('/')
        # 1) Найти датасентер
        dc_name = parts[0]
        datacenter = self.get_obj([vim.Datacenter], dc_name)
        if datacenter is None:
            raise Exception(f"Datacenter '{dc_name}' не найден")
        cur_folder = datacenter.vmFolder

        # 2) Идём по остальным частям пути
        for sub in parts[1:]:
            # ищем дочернюю папку с таким именем
            next_folder = next(
                (
                    e for e in cur_folder.childEntity
                    if isinstance(e, vim.Folder) and e.name == sub
                ),
                None
            )
            if next_folder is None:
                self.logger.info(f"Создаём папку '{sub}' в '{cur_folder.name}'")
                next_folder = cur_folder.CreateFolder(sub)
            cur_folder = next_folder

        return cur_folder

    @ensure_vm_connection
    def move_vm_to_folder(self, vm: vim.VirtualMachine, target_folder_path: str) -> None:
        """
        Перемещение ВМ в папку по полному пути "DC1/ZeonVM/Prod/LoginVMs".
        """
        # Находим или создаём конечную папку
        if '/' in target_folder_path:
            target_folder = self.ensure_folder_path(target_folder_path)
        else:
            target_folder = self.get_obj([vim.Folder], target_folder_path)
            if target_folder is None:
                self.logger.error(f"Целевая папка '{target_folder}' не найдена.")
                raise Exception(f"Папка '{target_folder_path}' не найдена")

        try:
            # Инициируем задачу перемещения ВМ в целевую папку
            self.logger.info(f"Перемещаем VM '{vm.name}' в '{target_folder.name}'...")
            task = target_folder.MoveIntoFolder_Task([vm])
            self.wait_for_task(task)
            self.logger.info(f"VM '{vm.name}' успешно перемещена в папку '{target_folder}'.")
        except Exception as e:
            self.logger.exception(f"Ошибка при перемещении VM '{vm.name}' в папку '{target_folder}': {e}")
            raise

    def disconnect(self):
        """
        Переопределяем отключение:
        — сначала закрываем SSH-соединение NSXManager,
        — затем дисконнект от vCenter.
        """

        if hasattr(self.nsx, 'close'):
            try:
                self.nsx.close()
                self.logger.info("SSH-соединение к NSX Manager закрыто")
            except Exception as e:
                self.logger.warning(f"Не удалось закрыть SSH NSXManager: {e}")

        # вызываем оригинальный метод из VSphereConnection
        super().disconnect()


# Пример использования класса
if __name__ == "__main__":
    # Параметры подключения к vCenter
    VCENTER_HOST = "192.168.3.215"
    VCENTER_USER = "administrator@vsphere80.local"
    VCENTER_PASSWORD = "Tf34gfasz!"

    # Параметры клонирования
    TEMPLATE_NAME = "Bliss 16 landscape"
    NEW_VM_NAME = "User_VM_001"
    FOLDER_NAME = "Production VMs"
    RESOURCE_POOL_NAME = "DefaultPool"
    DATASTORE_NAME = "NFS_Raid"

    manager = VSphereManager(VCENTER_HOST, VCENTER_USER, VCENTER_PASSWORD)
    try:
        # name_vm = 'FreeVM char_0 num_0'
        # vm = manager.get_vm_by_name(name_vm)
        # manager.move_vm_to_folder(vm, 'ZEON VMs dev')
        # manager.suspend_vm(vm)
        # 1. Клонирование из золотого образа
        for i in range(3, 5):
            vm = manager.clone_vm(
                '[Prod] FreeVM char_3',
                f'[Prod] FreeVM char_3 num_{i}',
                '[Prod] Free VMs to login'
            )
            manager.power_on_vm(vm)

        # 2. Изменение конфигурации ВМ (пример: 4 CPU и 4096 MB памяти)
        # name_vm = 'Bliss 15 iso Clone 1'
        # vm = manager.get_vm_by_name(name_vm)
        # manager.reconfigure_vm(vm, num_cpus=4, memory_mb=4096)

        # 3.1 Получение объекта vm
        # for i in range(0, 10):
            # name_vm = f'Bliss 16.9.6 Clone {i}'
            # vm = manager.get_vm_by_name(name_vm)
            # manager.power_off_vm(vm)

            # manager.reconfigure_vm(vm, num_cpus=4, memory_mb=2048)
            # manager.delete_vm(vm)

            # 3. Запуск ВМ
            # manager.power_on_vm(vm)
            # ip = manager.wait_for_vm_ready(vm)

            # bliss = BlissAdbManager(ip)
            # bliss.unlock_device()
            # if bliss.start_game():
                # logger.info(f'Успех для {name_vm}')

    except Exception as e:
        logger.exception("Error: %s", e)
    finally:
        manager.disconnect()
