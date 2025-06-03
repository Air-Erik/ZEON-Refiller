"""
VSpherePoolManager
──────────────────
Управление пулом ВМ одного окружения (cfg.vm_prefix)
и минимальный housekeeping для Replenisher.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import uuid
from typing import Dict, List, Set, Union

from pyVmomi import vim
from source.core.VMware.VSphereManager import (
    VSphereManager, ensure_vm_connection
)
from .config import cfg


class VSpherePoolManager(VSphereManager):
    # ──────────────────────────── init ────────────────────────────
    def __init__(
        self,
        host: str,
        user: str,
        pwd: str,
        port: int = 443,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(host, user, pwd, port)

        # внешний логгер, если передан
        if logger:
            self.logger = logger

        # фильтр убирает «мусорный» debug из базового класса
        class _NoMoidSpam(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
                return not record.getMessage().startswith("Список всех ВМ:")

        self.logger.addFilter(_NoMoidSpam())

        # собственные поля
        self._vm_prefix: str = cfg.vm_prefix.strip()
        self._lock: asyncio.Lock = asyncio.Lock()

        self._available: Set[str] = set()
        self._allocated: Dict[uuid.UUID, str] = {}
        self._last_snapshot: frozenset[str] | None = None

        self._initialize_free_machines()

    # — context manager —
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    # ─────────── helpers ────────────
    @ensure_vm_connection
    def _is_vm_in_env_folder(self, vm: vim.VirtualMachine) -> bool:
        current = vm.parent
        while current:
            if getattr(current, "name", None) == self._vm_prefix:
                return True
            current = getattr(current, "parent", None)
        return False

    def _env_vms(self) -> List[vim.VirtualMachine]:
        return [vm for vm in self._get_vm_list() if self._is_vm_in_env_folder(vm)]

    def _snapshot_and_log(self) -> None:
        names = frozenset(vm.name for vm in self._env_vms())
        if names != self._last_snapshot:
            self.logger.debug(
                "Список ВМ в папке «%s» (%d): %s",
                self._vm_prefix,
                len(names),
                sorted(names),
            )
            self._last_snapshot = names

    # ───────── init кэша ──────────
    def _initialize_free_machines(self) -> None:
        prefix_login = f"[{self._vm_prefix}] VM2login_"
        for vm in self._env_vms():
            if vm.name.startswith(prefix_login):
                self._available.add(vm.name)
        self.logger.info("Найдено ready ВМ: %s", len(self._available))

    # ───────── refresh / ready ─────────
    async def _refresh(self) -> None:
        async with self._lock:
            prefix_login = f"[{self._vm_prefix}] VM2login_"
            self._available = {
                vm.name for vm in self._env_vms() if vm.name.startswith(prefix_login)
            }
            self._snapshot_and_log()

    async def count_ready(self) -> int:
        await self._refresh()
        return len(self._available)

    # ───── выборки для Replenisher ─────
    def list_fault_vms(self) -> List[str]:
        prefix_err = f"[{self._vm_prefix}] VMError_"
        return [vm.name for vm in self._env_vms() if vm.name.startswith(prefix_err)]

    def list_init_vms(self, older_than_minutes: int = 0) -> List[str]:
        """
        VMInit_*, которые «зависли» дольше указанного TTL (минуты, UTC).

        • Если older_than_minutes <= 0 — возвращаем пустой список.
        • Если у ВМ нет createDate/bootTime (обычно сразу после клона),
          считаем её «молодой» и тоже пропускаем.
        """
        if older_than_minutes <= 0:
            return []

        prefix_init = f"[{self._vm_prefix}] VMInit_"
        cutoff = _dt.datetime.utcnow() - _dt.timedelta(minutes=older_than_minutes)
        victims: List[str] = []

        for vm in self._env_vms():
            if not vm.name.startswith(prefix_init):
                continue
            created = (
                getattr(vm.config, "createDate", None)
                or getattr(vm.runtime, "bootTime", None)
            )
            if created and created.replace(tzinfo=None) <= cutoff:
                victims.append(vm.name)

        return victims

    # ───────── смена статусов ─────────
    @ensure_vm_connection
    def _rename_with_suffix(
        self, vm_or_name: Union[str, vim.VirtualMachine], new_suffix: str
    ) -> None:
        vm = (
            vm_or_name
            if isinstance(vm_or_name, vim.VirtualMachine)
            else self.get_obj([vim.VirtualMachine], vm_or_name)
        )
        suffix = vm.name.rsplit("_", 1)[-1]
        self.rename_vm(vm, f"[{self._vm_prefix}] {new_suffix}_{suffix}")

    @ensure_vm_connection
    def mark_ready(self, vm_or_name: Union[str, vim.VirtualMachine]) -> None:
        self._rename_with_suffix(vm_or_name, "VM2login")

    @ensure_vm_connection
    def mark_fault(self, vm_or_name: Union[str, vim.VirtualMachine]) -> None:
        self._rename_with_suffix(vm_or_name, "VMError")

    # ───── housekeeping ─────
    def delete_vm_by_name(self, name: str) -> None:
        vm = self.get_obj([vim.VirtualMachine], name)
        self.power_off_vm(vm)
        self.delete_vm(vm)

    # ───── keep-alive для NSX CLI ─────
    def ensure_nsx_alive(self) -> None:
        nsx = getattr(self, "nsx", None)
        if nsx and hasattr(nsx, "reconnect"):
            try:
                nsx.reconnect()  # type: ignore[attr-defined]
            except Exception:
                self.logger.debug("nsx.reconnect() failed — ignored")


# ───────── manual test ─────────
if __name__ == "__main__":  # pragma: no cover
    import asyncio

    with VSpherePoolManager(
        cfg.vcenter_host, cfg.vcenter_user, cfg.vcenter_password
    ) as pool:
        print("Ready:", asyncio.run(pool.count_ready()))
