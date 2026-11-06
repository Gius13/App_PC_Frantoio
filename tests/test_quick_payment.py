"""Regressioni Windows: il pagamento rapido non deve perdere i clic.

Le richieste sono simulate; non si toccano Firebase o l'archivio reale.
"""
import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from app_frantoio.ui.main_window import MainWindow


class PaymentRepository:
    def __init__(self):
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.failed = False
        self.current_payment = ""
        self.row = {
            "id": "payment-test", "name": "Cliente test", "weight": 120.,
            "abbuono": 0., "dataOra": 1793952000000,
            "pagamento": "", "_source": "firebase",
        }

    def fetch_range(self, start, end):
        return [dict(self.row, pagamento=self.current_payment)]

    def update_pagamento(self, rid, payment, source):
        self.calls.append((rid, payment, source))
        self.started.set()
        if not self.release.wait(timeout=4):
            raise RuntimeError("Test: operazione non completata")
        if self.failed:
            raise RuntimeError("Firebase non raggiungibile")
        self.current_payment = payment

    def mirror_only(self):
        return 0

    def report_totals_sqlite(self, *args):
        return {"kg": 0, "lordo": 0, "abbuoni": 0,
                "netto": 0, "by_pagamento": {}}

    def report_daily_sqlite(self, *args):
        return []


class QuickPaymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.repo = PaymentRepository()
        self.window = MainWindow(
            {"theme": "light", "euro_per_kg": .16,
             "poll_ms": 300000, "mirror_interval_minutes": 9999},
            self.repo,
        )
        self.window.timer.stop()
        self.window.sync_timer.stop()
        self.window.model.set_rows([self.repo.row.copy()])
        self.window.table.selectRow(0)
        self.window.cmb_pagamento_quick.setCurrentText("Contanti")

    def tearDown(self):
        self.repo.release.set()
        self.wait_until(lambda: not self.window._save_busy, timeout=5)
        self.window.timer.stop()
        self.window.sync_timer.stop()
        self.window.close()

    def wait_until(self, condition, timeout=4):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(.015)
        self.app.processEvents()
        return bool(condition())

    def payment_in_table(self):
        return self.window.model.row_at(0)["pagamento"]

    def test_works_during_fetch_and_mirror_and_shows_value_immediately(self):
        self.window._busy = True
        self.window._sync_busy = True
        self.window.on_set_pagamento_clicked()
        self.assertTrue(self.window._save_busy)
        self.assertEqual(self.payment_in_table(), "Contanti")
        self.assertTrue(self.repo.started.wait(timeout=2))
        self.assertEqual(self.repo.calls, [
            ("payment-test", "Contanti", "firebase"),
        ])

        # Una lettura partita PRIMA della scrittura non deve rimpiazzare
        # temporaneamente il nuovo pagamento con il valore obsoleto.
        stale = [self.repo.row.copy()]
        self.window._on_refresh_done(
            stale, self.window._applied_scope,
            "payment-test", self.window._sel_serial, False
        )
        self.assertEqual(self.payment_in_table(), "Contanti")
        self.assertTrue(self.window._refresh_pending)

        self.repo.release.set()
        self.assertTrue(self.wait_until(lambda: not self.window._save_busy))
        self.assertTrue(self.wait_until(lambda: self.repo.current_payment == "Contanti"))
        self.assertTrue(self.wait_until(lambda: self.payment_in_table() == "Contanti"))

        # Una richiesta iniziata PRIMA del cambio, ma arrivata DOPO
        # la conferma del server, deve essere ignorata.
        original_serial = self.window._mutation_serial - 1
        self.window._on_refresh_done(
            stale, self.window._applied_scope, "payment-test",
            self.window._sel_serial, False, original_serial,
        )
        self.assertEqual(self.payment_in_table(), "Contanti")
        self.assertTrue(self.window._refresh_pending)

    def test_failure_restores_previous_payment_and_notifies(self):
        self.repo.failed = True
        with patch("app_frantoio.ui.main_window.QtWidgets.QMessageBox.warning") as warning:
            self.window.on_set_pagamento_clicked()
            self.assertEqual(self.payment_in_table(), "Contanti")
            self.repo.release.set()
            self.assertTrue(self.wait_until(lambda: not self.window._save_busy))
            self.assertEqual(self.payment_in_table(), "")
            self.assertEqual(self.repo.current_payment, "")
            self.assertTrue(self.wait_until(lambda: warning.called))
            self.assertIn(
                "ripristinato", warning.call_args.args[2].lower()
            )

    def test_second_click_while_saving_shows_feedback_no_duplicate_write(self):
        self.window.on_set_pagamento_clicked()
        self.assertEqual(self.payment_in_table(), "Contanti")
        self.assertTrue(self.repo.started.wait(timeout=2))
        self.window.on_set_pagamento_clicked()
        self.assertEqual(len(self.repo.calls), 1)
        self.assertIn("Salvataggio", self.window.statusBar().currentMessage())
        self.repo.release.set()
        self.assertTrue(self.wait_until(lambda: not self.window._save_busy))


if __name__ == "__main__":
    unittest.main()
