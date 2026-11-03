import os
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from darefx.gui.worker import TradingEngineWorker

@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app

def test_worker_signals_and_initialization(qapp) -> None:
    worker = TradingEngineWorker(simulation=True)
    assert worker is not None
    assert hasattr(worker, "account_updated")
    assert hasattr(worker, "positions_updated")
    assert hasattr(worker, "analysis_completed")
    assert hasattr(worker, "log_emitted")

def test_worker_poll_cycle_emits_data(qapp) -> None:
    worker = TradingEngineWorker(simulation=True)
    results = {}

    worker.account_updated.connect(lambda acc: results.setdefault("acc", acc))
    worker.positions_updated.connect(lambda pos: results.setdefault("pos", pos))

    worker.poll_account_and_positions()
    assert "acc" in results
    assert "pos" in results
    assert results["acc"].balance >= 0.0
