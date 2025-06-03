import pytest
from vm_refiller.utils.retry import retry_sync

def test_retry_success_after_fail():
    state = {"n":0}
    def fn():
        state["n"] += 1
        if state["n"] < 2:
            raise ValueError("boom")
        return "ok"
    assert retry_sync(fn, retries=3, backoff=0) == "ok"
    assert state["n"] == 2

def test_retry_raises_after_exhaust():
    with pytest.raises(RuntimeError):
        retry_sync(lambda: (_ for _ in ()).throw(RuntimeError("x")), 2, 0)
