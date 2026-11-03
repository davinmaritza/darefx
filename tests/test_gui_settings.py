import os
import tempfile
from pathlib import Path
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
from darefx.gui.components.settings_dialog import SettingsDialog, load_env_values, save_env_values

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_save_and_load_env_values() -> None:
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write("RISK_PER_TRADE_PCT=0.015\nBE_TRIGGER_PIPS=15.0\nAUTO_TRADE=true\n")
        env_path = Path(f.name)

    values = load_env_values(env_path)
    assert values["RISK_PER_TRADE_PCT"] == "0.015"
    assert values["BE_TRIGGER_PIPS"] == "15.0"

    save_env_values(env_path, {"RISK_PER_TRADE_PCT": "0.02", "BE_TRIGGER_PIPS": "20.0"})
    updated = load_env_values(env_path)
    assert updated["RISK_PER_TRADE_PCT"] == "0.02"
    assert updated["BE_TRIGGER_PIPS"] == "20.0"
    env_path.unlink()
