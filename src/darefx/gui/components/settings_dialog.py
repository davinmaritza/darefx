"""Settings configuration dialog with .env persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from darefx.gui.styles import ThemeColors


def load_env_values(env_path: Path) -> dict[str, str]:
    """Parse key-value pairs from .env file."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip("'\"")
    return values


def save_env_values(env_path: Path, new_values: dict[str, str]) -> None:
    """Update or append key-value pairs in .env while preserving unrelated lines."""
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines: list[str] = []

    for line in existing_lines:
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#") and "=" in trimmed:
            k, _ = trimmed.split("=", 1)
            key = k.strip()
            if key in new_values:
                new_lines.append(f"{key}={new_values[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for k, v in new_values.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class SettingsDialog(QDialog):
    """Dialog for editing trading and risk parameters directly from GUI."""

    def __init__(self, env_path: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Parameter DareFX")
        self.resize(450, 380)
        self.env_path = env_path or Path(".env")
        self.current_values = load_env_values(self.env_path)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)

        header = QLabel("Konfigurasi Parameter Trading & Risiko")
        header.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {ThemeColors.TEXT_PRIMARY};")
        main_layout.addWidget(header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Risk per Trade %
        self.spin_risk = QDoubleSpinBox()
        self.spin_risk.setRange(0.1, 10.0)
        self.spin_risk.setSingleStep(0.1)
        self.spin_risk.setValue(float(self.current_values.get("RISK_PER_TRADE_PCT", "0.01")) * 100.0)
        self.spin_risk.setSuffix(" %")
        form.addRow("Risiko per Trade:", self.spin_risk)

        # BE Trigger Pips
        self.spin_be = QDoubleSpinBox()
        self.spin_be.setRange(5.0, 100.0)
        self.spin_be.setSingleStep(1.0)
        self.spin_be.setValue(float(self.current_values.get("BE_TRIGGER_PIPS", "15.0")))
        self.spin_be.setSuffix(" pips")
        form.addRow("Trigger Break-Even:", self.spin_be)

        # Confidence Threshold AI
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.30, 0.90)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(float(self.current_values.get("CONFIDENCE_THRESHOLD", "0.40")))
        form.addRow("AI Threshold (Min Conf):", self.spin_conf)

        # Symbol
        self.txt_symbol = QLineEdit(self.current_values.get("SYMBOL", "EURUSD"))
        form.addRow("Pasangan Mata Uang:", self.txt_symbol)

        # Auto-Trade Default
        self.chk_autotrade = QCheckBox("Aktifkan Auto-Trade saat bot pertama kali menyala")
        self.chk_autotrade.setChecked(self.current_values.get("AUTO_TRADE", "true").lower() == "true")
        form.addRow("Auto-Trade Awal:", self.chk_autotrade)

        main_layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Simpan & Terapkan")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._handle_save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _handle_save(self) -> None:
        try:
            updates = {
                "RISK_PER_TRADE_PCT": f"{self.spin_risk.value() / 100.0:.4f}",
                "BE_TRIGGER_PIPS": f"{self.spin_be.value():.1f}",
                "CONFIDENCE_THRESHOLD": f"{self.spin_conf.value():.2f}",
                "SYMBOL": self.txt_symbol.text().strip().upper(),
                "AUTO_TRADE": "true" if self.chk_autotrade.isChecked() else "false",
            }
            save_env_values(self.env_path, updates)
            QMessageBox.information(self, "Pengaturan Tersimpan", "Konfigurasi berhasil disimpan ke file .env!")
            self.accept()
        except Exception as err:
            QMessageBox.critical(self, "Gagal Menyimpan", f"Terjadi kesalahan saat menyimpan: {err}")
