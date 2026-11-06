"""Calendario compatto per QDateEdit e QDateTimeEdit (macOS/Windows).

Lo stylesheet generale della QTableView non deve deformare le celle del
QCalendarWidget: i giorni hanno dimensioni, contrasto e selezione propri.
"""
from PyQt6 import QtCore, QtWidgets


CALENDAR_STYLE = """
QCalendarWidget {
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #d5e0ee;
    border-radius: 10px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: #eef4fd;
    border: none;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    min-height: 38px;
}
QCalendarWidget QToolButton {
    color: #1d3555;
    background: transparent;
    border: none;
    padding: 5px;
    min-width: 25px;
    font-weight: 700;
}
QCalendarWidget QToolButton:hover { background: #dbeafe; }
QCalendarWidget QMenu { background: #ffffff; color: #1e293b; }
QCalendarWidget QSpinBox {
    color: #1d3555;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    min-height: 22px;
    padding: 2px 4px;
}
QCalendarWidget QAbstractItemView,
QCalendarWidget QTableView {
    background: #ffffff;
    alternate-background-color: #ffffff;
    color: #25344b;
    border: none;
    border-radius: 0px;
    gridline-color: transparent;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: none;
    font-size: 13px;
}
QCalendarWidget QTableView::item {
    border: none;
    border-radius: 4px;
    padding: 0px;
    margin: 0px;
}
QCalendarWidget QAbstractItemView::item:selected,
QCalendarWidget QTableView::item:selected {
    background: #2563eb;
    color: #ffffff;
}
"""


def configure_calendar(date_editor: QtWidgets.QDateTimeEdit) -> None:
    """Installa un widget calendario isolato dal tema delle tabelle principali."""
    date_editor.setCalendarPopup(True)
    calendar = QtWidgets.QCalendarWidget(date_editor)
    calendar.setFirstDayOfWeek(QtCore.Qt.DayOfWeek.Monday)
    calendar.setGridVisible(False)
    calendar.setVerticalHeaderFormat(
        QtWidgets.QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
    )
    calendar.setHorizontalHeaderFormat(
        QtWidgets.QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
    )
    calendar.setMinimumSize(308, 245)
    calendar.setStyleSheet(CALENDAR_STYLE)
    # Stesso stile sul date editor, ma nessuna personalizzazione globale delle
    # celle QTableView del calendario.
    date_editor.setCalendarWidget(calendar)
