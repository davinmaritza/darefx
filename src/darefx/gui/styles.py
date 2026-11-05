"""Clean Professional Minimalist (Light / Neutral Gray Enterprise Banking) Theme for DareFX."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    # Neutral Grayscale
    BG_PRIMARY: str = "#F8FAFC"      # Slate 50 (clean light background)
    BG_SURFACE: str = "#FFFFFF"      # Pure white card/table background
    BG_SUBTLE: str = "#F1F5F9"       # Slate 100 for hovered rows / headers
    BORDER_LIGHT: str = "#E2E8F0"    # Slate 200 border
    BORDER_STRONG: str = "#CBD5E1"   # Slate 300 divider

    # Typography
    TEXT_PRIMARY: str = "#0F172A"    # Slate 900 (deep readable charcoal)
    TEXT_MUTED: str = "#64748B"      # Slate 500 (secondary label gray)
    TEXT_ON_DARK: str = "#FFFFFF"

    # Accents & Financial Indicators
    ACCENT_PRIMARY: str = "#0284C7"  # Sky 600 (enterprise blue)
    ACCENT_PRIMARY_HOVER: str = "#0369A1"
    ACCENT_SUCCESS: str = "#15803D"  # Green 700 (solid profit green)
    ACCENT_SUCCESS_BG: str = "#DCFCE7"
    ACCENT_DANGER: str = "#B91C1C"   # Red 700 (controlled loss red)
    ACCENT_DANGER_BG: str = "#FEE2E2"
    ACCENT_WARNING: str = "#B45309"  # Amber 700
    ACCENT_WARNING_BG: str = "#FEF3C7"


def get_application_stylesheet() -> str:
    """Return comprehensive enterprise banking QSS stylesheet."""
    return f"""
    QMainWindow, QWidget#CentralWidget {{
        background-color: {ThemeColors.BG_PRIMARY};
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
        color: {ThemeColors.TEXT_PRIMARY};
        font-size: 13px;
    }}

    QFrame.metricCard {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        border-radius: 8px;
        padding: 12px;
    }}

    QTableWidget {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        border-radius: 6px;
        gridline-color: {ThemeColors.BORDER_LIGHT};
        selection-background-color: {ThemeColors.BG_SUBTLE};
        selection-color: {ThemeColors.TEXT_PRIMARY};
    }}

    QHeaderView::section {{
        background-color: {ThemeColors.BG_SUBTLE};
        color: {ThemeColors.TEXT_MUTED};
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        border: none;
        border-bottom: 1px solid {ThemeColors.BORDER_STRONG};
        padding: 6px 8px;
    }}

    QPushButton {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_STRONG};
        border-radius: 6px;
        color: {ThemeColors.TEXT_PRIMARY};
        padding: 6px 14px;
        font-weight: 500;
        font-size: 12px;
    }}

    QPushButton:hover {{
        background-color: {ThemeColors.BG_SUBTLE};
    }}

    QPushButton.primaryBtn {{
        background-color: {ThemeColors.ACCENT_PRIMARY};
        border: 1px solid {ThemeColors.ACCENT_PRIMARY};
        color: {ThemeColors.TEXT_ON_DARK};
        font-weight: 600;
    }}

    QPushButton.primaryBtn:hover {{
        background-color: {ThemeColors.ACCENT_PRIMARY_HOVER};
    }}

    QPushButton.dangerBtn {{
        background-color: {ThemeColors.ACCENT_DANGER_BG};
        border: 1px solid #FCA5A5;
        color: {ThemeColors.ACCENT_DANGER};
        font-weight: 600;
    }}

    QPushButton.dangerBtn:hover {{
        background-color: #F87171;
        color: #FFFFFF;
    }}

    QPushButton.successBtn {{
        background-color: {ThemeColors.ACCENT_SUCCESS_BG};
        border: 1px solid #86EFAC;
        color: {ThemeColors.ACCENT_SUCCESS};
        font-weight: 600;
    }}

    QPushButton.successBtn:hover {{
        background-color: #4ADE80;
        color: #FFFFFF;
    }}

    QTextEdit#LogConsole {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        border-radius: 6px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
        color: {ThemeColors.TEXT_PRIMARY};
    }}

    QLineEdit, QDoubleSpinBox, QComboBox {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_STRONG};
        border-radius: 6px;
        padding: 5px 8px;
        color: {ThemeColors.TEXT_PRIMARY};
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {ThemeColors.ACCENT_PRIMARY};
    }}

    QTabWidget::pane {{
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        background-color: {ThemeColors.BG_PRIMARY};
        border-radius: 8px;
    }}

    QTabBar::tab {{
        background-color: {ThemeColors.BG_SUBTLE};
        color: {ThemeColors.TEXT_MUTED};
        padding: 8px 18px;
        margin-right: 4px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-weight: 600;
        font-size: 12px;
    }}

    QTabBar::tab:selected {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.ACCENT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER_STRONG};
        border-bottom: 2px solid {ThemeColors.ACCENT_PRIMARY};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {ThemeColors.BORDER_LIGHT};
        color: {ThemeColors.TEXT_PRIMARY};
    }}
    """


def get_badge_style(variant: str) -> str:
    """Generate inline stylesheet for status badges."""
    variant = variant.lower()
    if variant in ("buy", "active", "profit", "success"):
        return f"background-color: {ThemeColors.ACCENT_SUCCESS_BG}; color: {ThemeColors.ACCENT_SUCCESS}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
    if variant in ("sell", "danger", "loss", "shutdown"):
        return f"background-color: {ThemeColors.ACCENT_DANGER_BG}; color: {ThemeColors.ACCENT_DANGER}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
    if variant in ("warning", "paused", "neutral"):
        return f"background-color: {ThemeColors.ACCENT_WARNING_BG}; color: {ThemeColors.ACCENT_WARNING}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
    return f"background-color: {ThemeColors.BG_SUBTLE}; color: {ThemeColors.TEXT_MUTED}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
