"""Ricerca intervalli misti e filtri senza rete Firebase reale."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from app_frantoio.core.repository import HybridRepository
from app_frantoio.core.sqlite_client import SQLiteClient
from app_frantoio.models.filter_proxy import MolitureFilterProxy
from app_frantoio.models.moliture_model import MolitureModel
from app_frantoio.ui.search_panel import MolitureSearchPanel
from app_frantoio.util.time_utils import TZ


def ts(d: date, hour: int = 12):
    return int(datetime(d.year, d.month, d.day, hour, tzinfo=TZ).timestamp() * 1000)


def record(rid, d, name="Cliente", kg=100, method="POS"):
    return {
        "id": rid, "name": name, "weight": kg, "abbuono": 0,
        "pagamento": method, "dataOra": ts(d),
    }


class FakeFirebase:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def fetch(self):
        self.calls += 1
        return self.rows

    def fetch_range(self, start_ms, end_ms):
        self.calls += 1
        return [
            row for row in self.rows
            if start_ms <= row["dataOra"] < end_ms
        ]


class RangeRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sqlite = SQLiteClient(str(Path(self.temp.name) / "archive.db"))
        today = datetime.now(TZ).date()
        self.old = today - timedelta(days=12)
        self.recent = today - timedelta(days=1)
        self.other = today + timedelta(days=2)
        self.sqlite.upsert_many([
            record("old", self.old, "Mario", 75),
            record("shadow", self.recent, "Duplicato", 55),
        ])
        self.fb = FakeFirebase([
            record("recent", self.recent, "Luigi", 125, "Contanti"),
            record("future", self.other, "Anna", 90),
        ])
        self.repo = HybridRepository(self.fb, self.sqlite, 7, 7)

    def test_range_merges_older_sqlite_and_recent_firebase(self):
        rows = self.repo.fetch_range(self.old, self.recent)
        self.assertEqual([x["id"] for x in rows], ["old", "recent"])
        self.assertEqual([x["_source"] for x in rows], ["sqlite", "firebase"])
        self.assertEqual(self.fb.calls, 1)

    def test_old_range_does_not_call_firebase(self):
        rows = self.repo.fetch_range(self.old, self.old)
        self.assertEqual([x["id"] for x in rows], ["old"])
        self.assertEqual(self.fb.calls, 0)

    def test_recent_range_uses_one_firebase_fetch(self):
        rows = self.repo.fetch_range(self.recent, self.other)
        self.assertEqual([x["id"] for x in rows], ["recent", "future"])
        self.assertEqual(self.fb.calls, 1)

    def test_invalid_ranges(self):
        with self.assertRaises(ValueError):
            self.repo.fetch_range(self.recent, self.old)
        with self.assertRaises(ValueError):
            self.repo.fetch_range(self.old, self.old + timedelta(days=367))


class FilterUIFirstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_combined_search_and_payment_filter(self):
        model = MolitureModel([
            record("1", date(2026, 11, 5), "Mario", 200, "POS"),
            record("2", date(2026, 11, 6), "Lucia", 90, ""),
            record("3", date(2026, 11, 6), "Marco", 300, "Contanti"),
        ], 0.16)
        proxy = MolitureFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_search_text("ma")
        self.assertEqual(proxy.rowCount(), 2)
        proxy.set_payment("POS")
        self.assertEqual(proxy.rowCount(), 1)
        proxy.set_weight_bounds(100, 250)
        self.assertEqual(proxy.rowCount(), 1)
        proxy.set_weight_bounds(250, 350)
        self.assertEqual(proxy.rowCount(), 0)
        proxy.set_search_text("")
        proxy.set_payment("__unpaid__")
        proxy.set_weight_bounds(0, 0)
        self.assertEqual(proxy.rowCount(), 1)

    def test_range_panel_and_reset(self):
        panel = MolitureSearchPanel()
        self.assertEqual(panel.scope()[0], panel.scope()[1])
        panel.mode_combo.setCurrentIndex(1)
        self.assertTrue(panel.is_range_mode())
        self.assertLess(panel.scope()[0], panel.scope()[1])
        self.assertTrue(panel.btn_apply.isVisibleTo(panel) or not panel.isVisible())
        panel.search_edit.setText("Mario")
        panel.payment_combo.setCurrentIndex(1)
        panel.reset_filters()
        self.assertFalse(panel.is_range_mode())
        self.assertEqual(panel.search_edit.text(), "")
        self.assertEqual(panel.payment_combo.currentData(), "")
        panel.close()


if __name__ == "__main__":
    unittest.main()
