"""DareFX Native Desktop GUI Application Entrypoint."""

import os
from pathlib import Path
import sys
from dotenv import load_dotenv

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from darefx.gui.main_window import DareFXMainWindow


def main() -> None:
    # Load environment variables
    load_dotenv()
    simulation = os.getenv("MT5_SIMULATION", "false").lower() == "true"

    app = QApplication(sys.argv)
    app.setApplicationName("DareFX Trading Station")
    app.setOrganizationName("DareFX")

    logo_path = Path(__file__).resolve().parent / "assets" / "logo" / "darefx-app.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    window = DareFXMainWindow(simulation=simulation)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
