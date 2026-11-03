def test_pyside6_is_available() -> None:
    import PySide6.QtCore
    import PySide6.QtWidgets
    assert PySide6.__version__ is not None
