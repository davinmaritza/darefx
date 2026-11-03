"""Quick test script to diagnose GUI initialization on VM 126."""
import sys
import traceback

print("1. Checking PySide6 import...")
try:
    from PySide6.QtWidgets import QApplication
    print("   PySide6 imported successfully.")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("2. Checking darefx.gui imports...")
try:
    from darefx.gui.main_window import DareFXMainWindow
    print("   DareFXMainWindow imported successfully.")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("3. Instantiating QApplication...")
try:
    app = QApplication.instance() or QApplication(sys.argv)
    print("   QApplication instantiated.")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("4. Instantiating DareFXMainWindow (simulation=True)...")
try:
    window = DareFXMainWindow(simulation=True)
    print("   DareFXMainWindow instantiated successfully.")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("5. Showing window...")
try:
    window.show()
    print("   window.show() succeeded.")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("All initialization checks PASSED!")
