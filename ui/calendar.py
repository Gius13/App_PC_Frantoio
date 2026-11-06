"""Calendario ridisegnato per macOS, Windows e Linux.

Qt usa internamente una tabella per QCalendarWidget. I temi generali delle
QTableView possono compromettere colori, selezione e spaziatura dei giorni.
Disegniamo quindi ogni giorno esplicitamente, lasciando a Qt la gestione
di date, focus da tastiera e cambio mese.
"""
from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from app_frantoio.ui.theme import (
    calendar_stylesheet, current_theme, palette_colors,
)


class FrantoioCalendar(QtWidgets.QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("frantoioCalendar")
        self.setProperty("frantoioCalendar", True)
        self.setLocale(QtCore.QLocale(QtCore.QLocale.Language.Italian,
                                      QtCore.QLocale.Country.Italy))
        self.setFirstDayOfWeek(QtCore.Qt.DayOfWeek.Monday)
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(self.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(self.HorizontalHeaderFormat.ShortDayNames)
        self.setMinimumSize(336, 286)
        self.setStyleSheet(calendar_stylesheet())

    def paintCell(self, painter: QtGui.QPainter, rect: QtCore.QRect,
                  date: QtCore.QDate) -> None:
        """Giorno selezionato a pillola rossa, 'oggi' con bordo sottile.

        Il calendario resta navigabile con mouse e tastiera; le date
        inattive sono poco evidenti senza diventare invisibili.
        """
        colors = palette_colors(current_theme())
        selected = date == self.selectedDate()
        is_today = date == QtCore.QDate.currentDate()
        in_month = date.month() == self.monthShown() and date.year() == self.yearShown()

        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(rect, QtGui.QColor(colors["panel"]))

        inner = QtCore.QRectF(rect).adjusted(3.0, 3.0, -3.0, -3.0)
        radius = min(inner.width(), inner.height()) / 2.3
        if selected:
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(colors["accent"]))
            painter.drawRoundedRect(inner, radius, radius)
            text_color = colors["selected_text"]
        else:
            if is_today:
                outline = QtGui.QPen(QtGui.QColor(colors["accent"]), 1.7)
                painter.setPen(outline)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(inner.adjusted(1, 1, -1, -1), radius, radius)
            text_color = colors["text"] if in_month else colors["muted"]
            if not in_month:
                c = QtGui.QColor(text_color)
                c.setAlpha(110)
                text_color = c

        font = painter.font()
        font.setWeight(QtGui.QFont.Weight.DemiBold if selected or is_today
                       else QtGui.QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QtGui.QPen(QtGui.QColor(text_color)))
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, str(date.day()))
        painter.restore()


def configure_calendar(date_editor: QtWidgets.QDateTimeEdit) -> None:
    """Associa il calendario personalizzato al campo data."""
    date_editor.setCalendarPopup(True)
    calendar = FrantoioCalendar(date_editor)
    date_editor.setCalendarWidget(calendar)
