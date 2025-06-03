from vm_refiller.config import cfg

def test_env_loaded_from_file():
    # переменные из .env действительно в модели
    assert cfg.min_ready_vm == 3
    assert cfg.golden_name == "GoldenVM"
