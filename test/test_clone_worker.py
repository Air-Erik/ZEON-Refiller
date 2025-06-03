import traceback
from vm_refiller.builder import CloneWorker
from vm_refiller.tasks import WorkerResult, CloneTask
import uuid


def test_worker_happy_path(dummy_pool, mocker):
    # Патчим VSpherePoolManager внутри модуля builder
    mocker.patch("vm_refiller.builder.VSpherePoolManager", return_value=dummy_pool)
    q = mocker.Mock()                          # очередь для результата
    task = CloneTask(uuid.uuid4())

    CloneWorker(task, q)                           # синхронный запуск
    result: WorkerResult = q.put.call_args[0][0]

    assert result.status == "ok"
    assert "VM2login" in result.vm_name
    assert dummy_pool._calls == [
        "clone", "power_on", "wait_ip",
        "power_off", "mark_ready"
    ]

def test_worker_error_path(dummy_pool, mocker):
    dummy_pool.clone_vm = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail"))
    mocker.patch("vm_refiller.builder.VSpherePoolManager", return_value=dummy_pool)
    q = mocker.Mock()
    task = CloneTask(uuid.uuid4())
    CloneWorker(task, q)
    res = q.put.call_args[0][0]
    assert res.status == "err"
    assert "fail" in res.message
