from typing import Protocol


class IVSpherePoolManager(Protocol):
    async def count_ready(self) -> int:
        """Возвращает количество готовых виртуальных машин в пуле."""
        ...

    def connection_info(self) -> str:
        """Информация о соединении (опционально, можно вернуть строку с хостом/логином)."""
        ...
