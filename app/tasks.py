# vm_refiller/tasks.py
import asyncio
import uuid
from dataclasses import dataclass
from typing import Literal

CLONE_QUEUE: asyncio.Queue["CloneTask"] = asyncio.Queue()


@dataclass
class CloneTask:
    job_id: uuid.UUID


@dataclass
class WorkerResult:
    status: Literal["ok", "err"]
    vm_name: str
    message: str | None = None
