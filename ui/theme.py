"""Temi chiaro/scuro per PyQt6: palette antracite, nero, bianco e rosso.

Il tema si applica a QApplication: anche dialog di login, report e finestre
secondarie ereditano immediatamente lo stesso aspetto.
"""
from __future__ import annotations

from string import Template
from PyQt6 import QtGui, QtWidgets

THEME_LIGHT = "light"
THEME_DARK = "dark"
VALID_THEMES = (THEME_LIGHT, THEME_DARK)

_COLORS = {
    THEME_LIGHT: {
        "bg": "#f5f5f5",
        "panel": "#ffffff",
        "panel_alt": "#fafafa",
        "panel_hover": "#f6e8e9",
        "text": "#171717",
        "muted": "#656565",
        "border": "#d8d8d8",
        "header": "#ececec",
        "accent": "#b91c2b",
        "accent_hover": "#961320",
        "accent_soft": "#fae5e7",
        "selected_text": "#ffffff",
        "danger_bg": "#fff3f3",
        "disabled": "#a3a3a3",
        "gradient_end": "#86111f",
        "focus": "#b91c2b",
    },
    THEME_DARK: {
        "bg": "#111113",
        "panel": "#1d1d20",
        "panel_alt": "#252528",
        "panel_hover": "#332025",
        "text": "#f2f2f2",
        "muted": "#b4b4b7",
        "border": "#424246",
        "header": "#29292d",
        "accent": "#db3042",
        "accent_hover": "#fa4659",
        "accent_soft": "#40232a",
        "selected_text": "#ffffff",
        "danger_bg": "#311c20",
        "disabled": "#85858a",
        "gradient_end": "#a31c30",
        "focus": "#f04b5a",
    },
}

_current_theme = THEME_LIGHT


def normalize_theme(value: str | None) -> str:
    return value if value in VALID_THEMES else THEME_LIGHT


def current_theme() -> str:
    return _current_theme


def palette_colors(theme: str) -> dict[str, str]:
    return _COLORS[normalize_theme(theme)].copy()


_THEME_QSS = Template(r"""
QWidget {
    background-color: $bg;
    color: $text;
    font-family: 'Inter', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog, QTabWidget, QScrollArea, QSplitter {
    background-color: $bg;
}
QLabel, QGroupBox, QFrame#transparentFrame {
    background: transparent;
}
QLabel#pageTitle, QLabel#dialogTitle {
    color: $text;
    font-size: 23px;
    font-weight: 700;
}
QLabel#mutedLabel, QLabel#brandSubtitle { color: $muted; }
QLabel#brandTitle {
    color: $accent;
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 1px;
}
QToolBar#appToolbar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 $panel, stop:0.75 $panel, stop:1 $header);
    border: none;
    border-bottom: 2px solid $accent;
    padding: 9px 18px;
    spacing: 7px;
}
QToolBar#appToolbar::separator {
    background: $border;
    width: 1px;
    margin: 5px;
}
QLabel#editSummary, QLabel#summaryCard {
    border: 1px solid $border;
    border-radius: 12px;
    background-color: $panel;
    padding: 14px;
    font-size: 15px;
    font-weight: 650;
}
QTabWidget::pane {
    border: none;
    background: $bg;
}
QTabBar::tab {
    color: $muted;
    background: $bg;
    padding: 12px 22px;
    margin-right: 6px;
    border-bottom: 3px solid transparent;
    font-weight: 600;
}
QTabBar::tab:hover { color: $accent; }
QTabBar::tab:selected {
    color: $accent;
    border-bottom: 3px solid $accent;
}
QTableView {
    background: $panel;
    alternate-background-color: $panel_alt;
    gridline-color: $border;
    border: 1px solid $border;
    border-radius: 10px;
    selection-background-color: $accent_soft;
    selection-color: $text;
    outline: 0;
}
QTableView::item {
    padding: 8px;
    color: $text;
    border: none;
}
QTableView::item:selected {
    background: $accent_soft;
    color: $text;
    border-left: 3px solid $accent;
}
QHeaderView::section {
    color: $text;
    background: $header;
    border: none;
    border-bottom: 1px solid $border;
    padding: 11px 8px;
    font-weight: 700;
}
QPushButton {
    color: $text;
    background: $panel;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: $panel_hover;
    border: 1px solid $accent;
}
QPushButton:disabled {
    color: $disabled;
    background: $header;
}
QPushButton#primaryButton,
QDialogButtonBox QPushButton:default {
    color: $selected_text;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 $accent, stop:1 $gradient_end);
    border: 1px solid $accent;
}
QPushButton#primaryButton:hover,
QDialogButtonBox QPushButton:default:hover {
    background: $accent_hover;
    color: $selected_text;
}
QPushButton#dangerButton {
    color: $accent;
    background: $danger_bg;
    border-color: $accent;
}
QPushButton#dangerButton:hover { background: $accent_soft; }
QLineEdit, QComboBox, QDateEdit, QDateTimeEdit,
QDoubleSpinBox, QSpinBox, QTextEdit {
    color: $text;
    background: $panel;
    border: 1px solid $border;
    border-radius: 7px;
    min-height: 28px;
    padding: 5px 8px;
    selection-background-color: $accent;
    selection-color: $selected_text;
}
QLineEdit:focus, QComboBox:focus,
QDateEdit:focus, QDateTimeEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 2px solid $focus;
}
QComboBox::drop-down, QDateEdit::drop-down, QDateTimeEdit::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    color: $text;
    background: $panel;
    border: 1px solid $border;
    selection-background-color: $accent;
    selection-color: $selected_text;
}
QComboBox#themeSwitch {
    min-width: 98px;
    border: 1px solid $accent;
    font-weight: 600;
}
QScrollBar:vertical {
    width: 11px;
    background: $bg;
    margin: 0;
}
QScrollBar:horizontal {
    height: 11px;
    background: $bg;
    margin: 0;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: $border;
    border-radius: 5px;
    min-height: 22px;
    min-width: 22px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: $accent;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}
QProgressBar {
    background: $panel;
    color: $text;
    border: 1px solid $border;
    border-radius: 5px;
}
QProgressBar::chunk { background: $accent; border-radius: 5px; }
QStatusBar {
    color: $muted;
    background: $header;
    border-top: 1px solid $border;
}
QToolTip {
    color: $text;
    background: $panel;
    border: 1px solid $accent;
}
QMenu {
    color: $text;
    background: $panel;
    border: 1px solid $border;
}
QMenu::item:selected { background: $accent_soft; }
""")

_CALENDAR_QSS = Template(r"""
QCalendarWidget {
    background: $panel;
    color: $text;
    border: 1px solid $border;
    border-radius: 9px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: $header;
    border: none;
    min-height: 38px;
}
QCalendarWidget QToolButton {
    color: $text;
    background: transparent;
    border: none;
    padding: 5px;
    min-width: 25px;
    font-weight: 700;
}
QCalendarWidget QToolButton:hover { background: $accent_soft; color: $accent; }
QCalendarWidget QMenu { background: $panel; color: $text; }
QCalendarWidget QSpinBox {
    color: $text;
    background: $panel;
    border: 1px solid $border;
    padding: 2px 4px;
    min-height: 22px;
}
QCalendarWidget QAbstractItemView,
QCalendarWidget QTableView {
    color: $text;
    background: $panel;
    alternate-background-color: $panel;
    gridline-color: transparent;
    border: none;
    border-radius: 0;
    selection-background-color: $accent;
    selection-color: $selected_text;
    font-size: 13px;
    outline: none;
}
QCalendarWidget QTableView::item {
    background: $panel;
    color: $text;
    border: none;
    border-radius: 3px;
    padding: 0;
    margin: 0;
}
QCalendarWidget QAbstractItemView::item:selected,
QCalendarWidget QTableView::item:selected {
    color: $selected_text;
    background: $accent;
    border: none;
}
""")


def theme_stylesheet(theme: str) -> str:
    return _THEME_QSS.substitute(_COLORS[normalize_theme(theme)])


def calendar_stylesheet(theme: str | None = None) -> str:
    return _CALENDAR_QSS.substitute(_COLORS[normalize_theme(theme or _current_theme)])


def apply_theme(theme: str) -> str:
    """Attiva il tema per tutte le finestre Qt esistenti e future."""
    global _current_theme
    _current_theme = normalize_theme(theme)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        colors = _COLORS[_current_theme]
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(colors["bg"]))
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(colors["text"]))
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(colors["panel"]))
        palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(colors["panel_alt"]))
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(colors["text"]))
        palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(colors["panel"]))
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(colors["text"]))
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(colors["accent"]))
        palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(colors["selected_text"]))
        palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor(colors["muted"]))
        app.setPalette(palette)
        app.setStyleSheet(theme_stylesheet(_current_theme))
        # I calendari hanno uno stylesheet locale: dopo il cambio tema
        # devono essere aggiornati esplicitamente.
        for widget in app.allWidgets():
            if isinstance(widget, QtWidgets.QCalendarWidget) and widget.property("frantoioCalendar"):
                widget.setStyleSheet(calendar_stylesheet(_current_theme))
                widget.update()
    return _current_theme
