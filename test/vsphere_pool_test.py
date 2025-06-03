import os
import uuid
import asyncio
import logging

from filelock import FileLock

VM_FILE = "vms.txt"
LOCK_FILE = "vms.txt.lock"


class DummyVM:
    """Просто объект с именем ВМ"""
    def __init__(self, name):
        self.name = name

class VSpherePoolManager:
    _READY = "ready"
    _FAULT = "fault"

    def __init__(self, host: str = "", user: str = "", pwd: str = "", port: int = 443) -> None:
        self._lock = asyncio.Lock()
        self._vm_prefix = os.getenv("VM_PREFIX", "Prod").strip()
        self.logger = logging.getLogger(__name__)  

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def disconnect(self):
        pass

    async def _refresh(self) -> None:
        pass  # В тесте не нужен, мы всегда читаем файл напрямую

    def _read_vms(self):
        if not os.path.exists(VM_FILE):
            return []
        with FileLock(LOCK_FILE):
            with open(VM_FILE, "r") as f:
                lines = f.read().splitlines()
                return lines

    def _write_vms(self, lines):
        with FileLock(LOCK_FILE):
            with open(VM_FILE, "w") as f:
                f.write("\n".join(lines) + "\n")

    async def count_ready(self) -> int:
        vms = self._read_vms()
        ready_vms = [v for v in vms if v.startswith(f"[{self._vm_prefix}] VM2login_")]
        self.logger.info(f"[count_ready] Found {len(ready_vms)} ready VMs")
        return len(ready_vms)

    def clone_vm(self, source_vm_name: str, new_vm_name: str) -> DummyVM:
        vms = self._read_vms()
        vms.append(new_vm_name)
        self._write_vms(vms)
        self.logger.info(f"[clone_vm] Cloned {source_vm_name} → {new_vm_name}")
        return DummyVM(new_vm_name)

    def power_on_vm(self, vm: DummyVM) -> None:
        self.logger.info(f"[power_on_vm] Powered on {vm.name}")

    def wait_for_vm_ready(self, vm: DummyVM, timeout: int = 300) -> str:
        self.logger.info(f"[wait_for_vm_ready] VM {vm.name} is ready (simulated)")
        return f"192.168.0.{int(uuid.uuid4().int % 254) + 1}"  # фейковый IP

    def power_off_vm(self, vm: DummyVM) -> None:
        self.logger.info(f"[power_off_vm] Powered off {vm.name}")

    def mark_ready(self, vm_or_name: str) -> None:
        old_name = vm_or_name if isinstance(vm_or_name, str) else vm_or_name.name
        suffix = old_name.rsplit("_", 1)[-1]
        new_name = f"[{self._vm_prefix}] VM2login_{suffix}"

        vms = self._read_vms()
        if old_name in vms:
            vms.remove(old_name)
        vms.append(new_name)
        self._write_vms(vms)
        self.logger.info(f"[mark_ready] {old_name} → {new_name}")

    def mark_fault(self, vm_or_name: str) -> None:
        old_name = vm_or_name if isinstance(vm_or_name, str) else vm_or_name.name
        suffix = old_name.rsplit("_", 1)[-1]
        new_name = f"[{self._vm_prefix}] VMError_{suffix}"

        vms = self._read_vms()
        if old_name in vms:
            vms.remove(old_name)
        vms.append(new_name)
        self._write_vms(vms)
        self.logger.info(f"[mark_fault] {old_name} → {new_name}")

    def list_fault_vms(self) -> list[str]:
        fault_prefix = f"[{self._vm_prefix}] VMError_"
        return [v for v in self._read_vms() if v.startswith(fault_prefix)]

    def delete_vm_by_name(self, name: str) -> None:
        vms = self._read_vms()
        if name in vms:
            vms.remove(name)
            self._write_vms(vms)
            self.logger.info(f"[delete_vm_by_name] Удалена ВМ {name}")

