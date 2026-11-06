"""Calendario con tema nero/rosso indipendente dalla tabella principale.

Uno stylesheet locale evita che lo stile della QTableView principale
distorca la griglia dei giorni nel popup su macOS.
"""
from PyQt6 import QtCore, QtWidgets

from app_frantoio.ui.theme import calendar_stylesheet


def configure_calendar(date_editor: QtWidgets.QDateTimeEdit) -> None:
    """Installa un popup calendario coerente col tema attivo."""
    date_editor.setCalendarPopup(True)
    calendar = QtWidgets.QCalendarWidget(date_editor)
    calendar.setProperty("frantoioCalendar", True)
    calendar.setFirstDayOfWeek(QtCore.Qt.DayOfWeek.Monday)
    calendar.setGridVisible(False)
    calendar.setVerticalHeaderFormat(
        QtWidgets.QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
    )
    calendar.setHorizontalHeaderFormat(
        QtWidgets.QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
    )
    calendar.setMinimumSize(308, 245)
    calendar.setStyleSheet(calendar_stylesheet())
    date_editor.setCalendarWidget(calendar)
