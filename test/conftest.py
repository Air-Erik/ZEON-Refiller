import sys
import types

# Создаём заглушки
fake = types.ModuleType("fake")
sys.modules["uiautomator2"] = fake
sys.modules["scr"] = fake
sys.modules["scr.core"] = fake
sys.modules["scr.core.VMware"] = types.ModuleType("scr.core.VMware")

# Добавляем нужный класс‑заглушку
vsphere_manager_mod = types.ModuleType("scr.core.VMware.VSphereManager")
vsphere_manager_mod.VSphereManager = object

# Регистрируем модуль в sys.modules
sys.modules["scr.core.VMware.VSphereManager"] = vsphere_manager_mod

# Остальные, если не добавлены ранее
sys.modules["scr.GameTutorial"] = types.ModuleType("scr.GameTutorial")
sys.modules["scr.GameTutorial"].GameTutorial = object
sys.modules["scr.BlissInitSetup"] = types.ModuleType("scr.BlissInitSetup")
sys.modules["scr.BlissInitSetup"].BlisInitSetup = object


import asyncio
import pytest
from types import ModuleType, SimpleNamespace

from vm_refiller.pending_counter import pending


# 🧪 Мокаем тяжёлые/внешние зависимости (uiautomator2, ADB, scr)
_FAKE_MODULES = [
    "uiautomator2",
    "scr",
    "scr.BlissInitSetup",
    "scr.GameTutorial",
    "scr.core",
    "scr.core.VMware",
    "scr.core.VMware.BlissOSController",
]

@pytest.fixture(scope="session", autouse=True)
def _patch_optional_deps():
    fake_modules = [
        "uiautomator2",
        "scr",
        "scr.GameTutorial",
        "scr.BlissInitSetup",
        "scr.core",
        "scr.core.VMware",
        "scr.core.VMware.BlissOSController",
    ]

    for name in fake_modules:
        sys.modules.setdefault(name, types.ModuleType(name))


# 🔄 Сброс глобального счётчика перед и после каждого теста
@pytest.fixture(autouse=True)
def reset_pending():
    asyncio.get_event_loop().run_until_complete(pending.dec())
    yield
    asyncio.get_event_loop().run_until_complete(pending.dec())


# 🤖 Заглушка пула (используется в test_clone_worker, test_replenisher)
@pytest.fixture
def dummy_pool():
    """
    Мини-заглушка VSpherePoolManager со списком вызовов и фейковыми методами.
    """
    calls = []

    def _rec(name):
        calls.append(name)

    dummy = SimpleNamespace(
        clone_vm=lambda *a, **kw: _rec("clone") or "vm",
        power_on_vm=lambda *a, **kw: _rec("power_on"),
        wait_for_vm_ready=lambda *a, **kw: _rec("wait_ip") or "10.0.0.1",
        restart_vm=lambda *a, **kw: _rec("restart"),
        power_off_vm=lambda *a, **kw: _rec("power_off"),
        mark_ready=lambda *a, **kw: _rec("mark_ready"),
        mark_fault=lambda *a, **kw: _rec("mark_fault"),
        list_fault_vms=lambda: [],
        delete_vm_by_name=lambda *_: None,
        count_ready=lambda: 0,
    )
    dummy._calls = calls
    return dummy
