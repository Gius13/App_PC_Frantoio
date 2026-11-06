"""Smoke test dell'intera finestra principale con dati simulati."""
import os
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets, QtCore, QtTest

from app_frantoio.ui.main_window import MainWindow
from app_frantoio.util.time_utils import TZ


class FakeRepository:
    def __init__(self):
        self.calls = []

    def fetch_range(self, start, end):
        self.calls.append((start, end))
        return []

    def mirror_only(self):
        return 0

    def report_totals_sqlite(self, start, end, price):
        return {"kg": 0, "lordo": 0, "abbuoni": 0,
                "netto": 0, "by_pagamento": {}}

    def report_daily_sqlite(self, start, end, price):
        return []


class MainWindowSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.app.setStyle("Fusion")

    def test_filters_start_collapsed_and_keep_criteria_when_closed(self):
        repo = FakeRepository()
        w = MainWindow(
            {"theme": "dark", "euro_per_kg": 0.16,
             "poll_ms": 300000, "mirror_interval_minutes": 9999},
            repo,
        )
        try:
            w.timer.stop()
            w.sync_timer.stop()
            w.show()
            self.app.processEvents()

            # All'avvio la tabella occupa la pagina; le azioni restano visibili.
            self.assertTrue(w.filters.isHidden())
            self.assertFalse(w.btn_toggle_filters.isChecked())
            self.assertTrue(w.btn_refresh.isVisible())
            self.assertTrue(w.btn_export.isVisible())
            self.assertEqual(w.filter_summary.text(), "Oggi")

            w.btn_toggle_filters.click()
            self.assertFalse(w.filters.isHidden())
            self.assertTrue(w.btn_toggle_filters.isChecked())

            # Filtra: la chiusura deve soltanto nascondere il pannello.
            w.filters.search_edit.setText("Mario")
            w.filters.payment_combo.setCurrentIndex(1)
            self.assertIn("2 filtri", w.filter_summary.text())
            self.assertEqual(w.proxy._query, "mario")
            self.assertEqual(w.proxy._payment, "__unpaid__")

            w.btn_toggle_filters.click()
            self.assertTrue(w.filters.isHidden())
            self.assertFalse(w.btn_toggle_filters.isChecked())
            self.assertTrue(w.btn_refresh.isVisible())
            self.assertIn("2 filtri", w.filter_summary.text())
            self.assertEqual(w.filters.search_edit.text(), "Mario")
            self.assertEqual(w.filters.payment_combo.currentData(), "__unpaid__")
            self.assertEqual(w.proxy._query, "mario")

            # Riaprendo, tutti i campi mantengono i valori già selezionati.
            w.btn_toggle_filters.click()
            self.assertFalse(w.filters.isHidden())
            self.assertEqual(w.filters.search_edit.text(), "Mario")
            self.assertEqual(w.filters.payment_combo.currentData(), "__unpaid__")
        finally:
            w.timer.stop()
            w.sync_timer.stop()
            w.close()

    def test_window_assembles_and_range_controls_work(self):
        repo = FakeRepository()
        w = MainWindow(
            {"theme": "dark", "euro_per_kg": 0.16,
             "poll_ms": 300000, "mirror_interval_minutes": 9999},
            repo,
        )
        try:
            w.timer.stop()
            w.sync_timer.stop()
            self.assertEqual(w.proxy.sortColumn(), 4)
            self.assertEqual(
                w.table.horizontalHeader().sectionResizeMode(0),
                QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
            )
            self.assertEqual(w.filters.mode_combo.currentData(), "day")
            self.assertIsNotNone(w.filters.date_edit.calendarWidget())
            self.assertIsNotNone(w.filters.date_from.calendarWidget())
            w.filters.mode_combo.setCurrentIndex(1)
            self.assertTrue(w.filters.is_range_mode())
            start, end = w.filters.scope()
            self.assertLess(start, end)
            self.assertEqual(w._applied_scope, (start, end))
            # Esplicita una ricerca sul periodo.
            w.filters.searchRequested.emit()
            for _ in range(20):
                self.app.processEvents()
                QtTest.QTest.qWait(5)
            self.assertTrue(repo.calls)
        finally:
            w.timer.stop()
            w.sync_timer.stop()
            w.close()


if __name__ == "__main__":
    unittest.main()
