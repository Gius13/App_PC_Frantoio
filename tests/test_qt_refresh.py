"""Regressioni PyQt6 per selezione, ordinamento e calendario.

Richiede PyQt6; è eseguibile headless con QT_QPA_PLATFORM=offscreen.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets, QtGui
from app_frantoio.ui.theme import apply_theme, palette_colors

from app_frantoio.models.moliture_model import MolitureModel
from app_frantoio.ui.calendar import configure_calendar


def record(n: int, when: int) -> dict:
    return {
        "id": f"record-{n}", "name": f"Cliente {n}",
        "weight": float(n + 1), "abbuono": 0.0, "pagamento": "",
        "dataOra": when, "_source": "firebase",
    }


class QtRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.model = MolitureModel([], 0.16)
        self.proxy = QtCore.QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(QtCore.Qt.ItemDataRole.UserRole)

        self.table = QtWidgets.QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(4, QtCore.Qt.SortOrder.AscendingOrder)
        self.table.resize(700, 320)
        self.table.show()
        self.app.processEvents()

    def tearDown(self):
        self.table.close()

    def _selected_id(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        source = self.proxy.mapToSource(sel[0])
        return self.model.row_at(source.row())["id"]

    def test_selection_survives_refresh_and_new_record(self):
        t0 = 1793952000000
        initial = [record(i, t0 + i * 60_000) for i in range(80)]
        self.model.set_rows(initial)
        self.app.processEvents()

        self.table.selectRow(55)
        self.table.verticalScrollBar().setValue(35)
        self.app.processEvents()
        original_scroll = self.table.verticalScrollBar().value()
        self.assertEqual(self._selected_id(), "record-55")

        resets = []
        self.model.modelReset.connect(lambda: resets.append(True))
        self.assertFalse(self.model.set_rows([r.copy() for r in initial]))
        self.assertEqual(resets, [])
        self.assertEqual(self._selected_id(), "record-55")
        self.assertEqual(self.table.verticalScrollBar().value(), original_scroll)

        self.assertTrue(self.model.set_rows(initial + [record(80, t0 + 80 * 60_000)]))
        self.app.processEvents()
        self.assertEqual(self._selected_id(), "record-55")
        self.assertEqual(resets, [])
        self.assertEqual(self.table.verticalScrollBar().value(), original_scroll)

        changed = [r.copy() for r in initial]
        changed[55]["pagamento"] = "POS"
        self.model.set_rows(changed + [record(80, t0 + 80 * 60_000)])
        self.app.processEvents()
        self.assertEqual(self._selected_id(), "record-55")
        self.assertEqual(resets, [])

    def test_time_sort_uses_numeric_timestamp(self):
        t0 = 1793952000000
        self.model.set_rows([
            record(1, t0 + 20_000), record(2, t0 + 3_000),
            record(3, t0 + 100_000)
        ])
        self.app.processEvents()
        order = [
            self.model.row_at(self.proxy.mapToSource(self.proxy.index(i, 0)).row())["id"]
            for i in range(3)
        ]
        self.assertEqual(order, ["record-2", "record-1", "record-3"])

    def test_calendar_uses_independent_style(self):
        edit = QtWidgets.QDateEdit()
        configure_calendar(edit)
        calendar = edit.calendarWidget()
        self.assertEqual(calendar.firstDayOfWeek(), QtCore.Qt.DayOfWeek.Monday)
        self.assertIn("selection-background-color", calendar.styleSheet())
        edit.setDate(QtCore.QDate(2026, 11, 6))
        self.assertEqual(edit.date(), QtCore.QDate(2026, 11, 6))


    def test_calendar_paint_cell_in_both_themes(self):
        edit = QtWidgets.QDateEdit()
        configure_calendar(edit)
        calendar = edit.calendarWidget()
        date = QtCore.QDate(2026, 11, 6)
        for theme in ("light", "dark"):
            apply_theme(theme)
            calendar.setSelectedDate(date)
            calendar.showSelectedDate()
            image = QtGui.QImage(60, 50, QtGui.QImage.Format.Format_ARGB32)
            image.fill(QtGui.QColor(palette_colors(theme)["panel"]))
            painter = QtGui.QPainter(image)
            calendar.paintCell(painter, QtCore.QRect(0, 0, 60, 50), date)
            painter.end()
            self.assertFalse(image.isNull())
            selected = QtGui.QColor(palette_colors(theme)["accent"])
            self.assertTrue(any(
                image.pixelColor(x, y) == selected
                for x in range(6, 54) for y in range(6, 44)
            ), f"Il giorno selezionato non risulta rosso nel tema {theme}")
        edit.close()
        apply_theme("light")


if __name__ == "__main__":
    unittest.main()
