"""Clean metric summary card widget."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from darefx.gui.styles import ThemeColors


class MetricCard(QFrame):
    """Clean financial metric card displaying title, primary value, and subtitle."""

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        is_positive: bool | None = None,
        parent: QFrame | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "metricCard")
        self.setObjectName("MetricCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; font-size: 20px; font-weight: 700;")

        self.subtitle_label = QLabel(subtitle)
        self._apply_subtitle_color(is_positive)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def _apply_subtitle_color(self, is_positive: bool | None) -> None:
        if is_positive is True:
            color = ThemeColors.ACCENT_SUCCESS
        elif is_positive is False:
            color = ThemeColors.ACCENT_DANGER
        else:
            color = ThemeColors.TEXT_MUTED
        self.subtitle_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 500;")

    def update_values(self, value: str, subtitle: str = "", is_positive: bool | None = None) -> None:
        self.value_label.setText(value)
        self.subtitle_label.setText(subtitle)
        self._apply_subtitle_color(is_positive)
