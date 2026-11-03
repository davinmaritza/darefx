import os
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
try:
    from PySide6.QtWidgets import QApplication
    from darefx.gui.main_window import DareFXMainWindow
except ImportError as err:
    pytest.skip(f"PySide6/Qt GUI libraries unavailable: {err}", allow_module_level=True)

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_main_window_initialization(qapp) -> None:
    window = DareFXMainWindow(simulation=True)
    assert window.windowTitle() == "DareFX — AI Algorithmic Trading Terminal"
    assert window.worker is not None
    assert window.metric_balance is not None
    assert window.positions_table is not None
    assert window.control_panel is not None
    window._force_quit()
