import importlib

def test_app_entry_module_is_importable() -> None:
    mod = importlib.import_module("app")
    assert hasattr(mod, "main")
