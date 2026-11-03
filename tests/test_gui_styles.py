from darefx.gui.styles import ThemeColors, get_application_stylesheet, get_badge_style

def test_theme_colors_exist() -> None:
    assert ThemeColors.BG_PRIMARY.startswith("#")
    assert ThemeColors.TEXT_PRIMARY.startswith("#")
    assert ThemeColors.ACCENT_SUCCESS.startswith("#")
    assert ThemeColors.ACCENT_DANGER.startswith("#")

def test_stylesheet_returns_valid_qss() -> None:
    qss = get_application_stylesheet()
    assert "QMainWindow" in qss
    assert "QPushButton" in qss
    assert "QTableWidget" in qss

def test_badge_style_generation() -> None:
    buy_badge = get_badge_style("buy")
    sell_badge = get_badge_style("sell")
    assert "background-color" in buy_badge
    assert "background-color" in sell_badge
