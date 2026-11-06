"""Test SQLite, senza connessione Firebase o interfaccia grafica."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app_frantoio.core.sqlite_client import SQLiteClient
from app_frantoio.util.time_utils import TZ
from datetime import datetime


class SQLiteEditsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = SQLiteClient(str(Path(self.temp.name) / "moliture.db"))
        self.now_ms = int(datetime(2026, 11, 6, 12, 0, tzinfo=TZ).timestamp() * 1000)
        self.row = {
            "id": "abc123", "name": "Cliente",
            "weight": 250.0, "abbuono": 0.0,
            "pagamento": "", "dataOra": self.now_ms
        }
        self.db.upsert_many([self.row])

    def test_edit_is_partial(self):
        self.db.update_fields("abc123", {"name": "Cliente aggiornato"})
        record = self.db.fetch_day(date(2026, 11, 6))[0]
        self.assertEqual(record["name"], "Cliente aggiornato")
        self.assertEqual(record["weight"], 250.0)

    def test_local_override_survives_mirror(self):
        self.db.update_fields("abc123", {"weight": 100.0}, local_override=True)
        self.db.upsert_many([dict(self.row, weight=900.0)])
        record = self.db.fetch_day(date(2026, 11, 6))[0]
        self.assertEqual(record["weight"], 100.0)

    def test_local_deletion_survives_mirror(self):
        self.db.delete_one("abc123")
        self.db.upsert_many([self.row])
        self.assertEqual(self.db.fetch_day(date(2026, 11, 6)), [])

    def test_missing_record(self):
        with self.assertRaises(LookupError):
            self.db.update_fields("does-not-exist", {"name": "Changed"})


if __name__ == "__main__":
    unittest.main()
