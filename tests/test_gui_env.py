def test_pyside6_is_available() -> None:
    import pytest
    try:
        import PySide6.QtCore
        import PySide6.QtWidgets
    except ImportError as err:
        pytest.skip(f"PySide6/Qt libraries unavailable: {err}")
    assert PySide6.__version__ is not None
