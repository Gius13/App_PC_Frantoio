from __future__ import annotations
from datetime import date, timedelta
from typing import TYPE_CHECKING, Dict, Tuple, List, Callable

from PyQt6 import QtWidgets, QtCore, QtGui

if TYPE_CHECKING:
    from app_frantoio.core.repository import HybridRepository


_EMPTY_METHOD_LABEL = "Da Saldare"  # etichetta per pagamento non impostato


# Worker generico per thread pool
class _WorkerSignals(QtCore.QObject):
    done = QtCore.pyqtSignal(object)   # result
    error = QtCore.pyqtSignal(str)


class _FuncWorker(QtCore.QRunnable):
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @QtCore.pyqtSlot()
    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.done.emit(res)
        except Exception as e:
            self.signals.error.emit(str(e))


class ReportsPage(QtWidgets.QWidget):
    """
    Report veloci basati SOLO su SQLite (aggregazioni SQL).
    - Selettori Dal/Al + bottoni Oggi/Settimana/Mese
    - Auto-refresh al cambio date (debounced 250ms)
    - Riepilogo: Kg, Lordo, Abbuoni, Netto
    - Tabella per Metodo pagamento (Kg, Lordo, Netto; vuoto -> "Da Saldare")
    - Tabella Giornaliera nel periodo
    - Refresh in background (niente blocchi UI) con token per scartare risultati obsoleti
    """

    def __init__(self, repo: HybridRepository, euro_per_kg: float, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.euro_per_kg = float(euro_per_kg)

        self._pool = QtCore.QThreadPool.globalInstance()
        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)  # debounce 250ms
        self._debounce.timeout.connect(self._refresh_async)

        self._refresh_seq = 0  # token per scartare risultati vecchi
        self._busy = False

        main = QtWidgets.QVBoxLayout(self)

        # --- Barra controlli ---
        ctrls_row1 = QtWidgets.QHBoxLayout()
        ctrls_row1.addWidget(QtWidgets.QLabel("Dal:"))
        self.dt_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.dt_from.setDisplayFormat("dd/MM/yyyy")
        self.dt_from.setDate(QtCore.QDate.currentDate())
        ctrls_row1.addWidget(self.dt_from)

        ctrls_row1.addWidget(QtWidgets.QLabel("Al:"))
        self.dt_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.dt_to.setDisplayFormat("dd/MM/yyyy")
        self.dt_to.setDate(QtCore.QDate.currentDate())
        ctrls_row1.addWidget(self.dt_to)

        ctrls_row1.addStretch(1)

        self.btn_today = QtWidgets.QPushButton("Oggi")
        self.btn_week = QtWidgets.QPushButton("Settimana")
        self.btn_month = QtWidgets.QPushButton("Mese")
        self.btn_refresh = QtWidgets.QPushButton("Aggiorna")

        ctrls_row1.addWidget(self.btn_today)
        ctrls_row1.addWidget(self.btn_week)
        ctrls_row1.addWidget(self.btn_month)
        ctrls_row1.addWidget(self.btn_refresh)

        main.addLayout(ctrls_row1)

        # --- Riepilogo ---
        summary = QtWidgets.QHBoxLayout()
        self.lbl_kg = QtWidgets.QLabel("Kg totali: 0.00")
        self.lbl_lordo = QtWidgets.QLabel("Lordo: € 0.00")
        self.lbl_abbuoni = QtWidgets.QLabel("Abbuoni: € 0.00")
        self.lbl_netto = QtWidgets.QLabel("Netto: € 0.00")
        for w in (self.lbl_kg, self.lbl_lordo, self.lbl_abbuoni, self.lbl_netto):
            w.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            w.setMinimumWidth(160)
            summary.addWidget(w)
        main.addLayout(summary)

        # --- Splitter per tabelle ---
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        # Tabella per metodo pagamento
        pay_panel = QtWidgets.QWidget()
        pay_layout = QtWidgets.QVBoxLayout(pay_panel)
        pay_layout.setContentsMargins(0, 0, 0, 0)
        lbl_pay = QtWidgets.QLabel("Totali per Metodo di pagamento")
        lbl_pay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.table_pay = QtWidgets.QTableView()
        self.model_pay = QtGui.QStandardItemModel(0, 4, self)
        self.model_pay.setHorizontalHeaderLabels(["Metodo", "Kg", "Lordo (€)", "Netto (€)"])
        self.table_pay.setModel(self.model_pay)
        self.table_pay.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_pay.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table_pay.horizontalHeader().setStretchLastSection(True)
        self.table_pay.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        pay_layout.addWidget(lbl_pay)
        pay_layout.addWidget(self.table_pay)

        # Tabella giornaliera
        day_panel = QtWidgets.QWidget()
        day_layout = QtWidgets.QVBoxLayout(day_panel)
        day_layout.setContentsMargins(0, 0, 0, 0)
        lbl_days = QtWidgets.QLabel("Riepilogo giornaliero nel periodo")
        lbl_days.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.table_days = QtWidgets.QTableView()
        self.model_days = QtGui.QStandardItemModel(0, 5, self)
        self.model_days.setHorizontalHeaderLabels(["Data", "Kg", "Lordo (€)", "Abbuoni (€)", "Netto (€)"])
        self.table_days.setModel(self.model_days)
        self.table_days.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_days.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table_days.horizontalHeader().setStretchLastSection(True)
        self.table_days.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        day_layout.addWidget(lbl_days)
        day_layout.addWidget(self.table_days)

        splitter.addWidget(pay_panel)
        splitter.addWidget(day_panel)
        splitter.setSizes([300, 300])
        main.addWidget(splitter)

        # --- Signals: auto refresh con debounce + bottoni rapidi ---
        self.dt_from.dateChanged.connect(self._debounce_refresh)
        self.dt_to.dateChanged.connect(self._debounce_refresh)
        self.btn_refresh.clicked.connect(self.refresh)  # manuale (senza debounce)

        self.btn_today.clicked.connect(self._set_today)
        self.btn_week.clicked.connect(self._set_week)
        self.btn_month.clicked.connect(self._set_month)

        # Primo caricamento
        QtCore.QTimer.singleShot(0, self.refresh)

    # ---------------- Helpers ----------------
    def _selected_dates(self) -> Tuple[date, date]:
        qf = self.dt_from.date()
        qt = self.dt_to.date()
        d1 = date(qf.year(), qf.month(), qf.day())
        d2 = date(qt.year(), qt.month(), qt.day())
        if d2 < d1:
            d1, d2 = d2, d1
        return d1, d2

    def _fmt_money(self, v: float) -> str:
        return f"{v:.2f}"

    def _fmt_kg(self, v: float) -> str:
        return f"{v:.2f}"

    def _set_today(self):
        today = QtCore.QDate.currentDate()
        # blocco signals per evitare due debounce consecutivi
        self._set_dates_safely(today, today)

    def _set_week(self):
        qtoday = QtCore.QDate.currentDate()
        py_today = date(qtoday.year(), qtoday.month(), qtoday.day())
        weekday = py_today.weekday()  # 0=lunedì .. 6=domenica
        monday = py_today - timedelta(days=weekday)
        sunday = monday + timedelta(days=6)
        self._set_dates_safely(QtCore.QDate(monday.year, monday.month, monday.day),
                               QtCore.QDate(sunday.year, sunday.month, sunday.day))

    def _set_month(self):
        qtoday = QtCore.QDate.currentDate()
        y, m = qtoday.year(), qtoday.month()
        first = QtCore.QDate(y, m, 1)
        # ultimo giorno mese
        next_first = QtCore.QDate(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
        last = next_first.addDays(-1)
        self._set_dates_safely(first, last)

    def _set_dates_safely(self, qfrom: QtCore.QDate, qto: QtCore.QDate):
        self.dt_from.blockSignals(True)
        self.dt_to.blockSignals(True)
        self.dt_from.setDate(qfrom)
        self.dt_to.setDate(qto)
        self.dt_from.blockSignals(False)
        self.dt_to.blockSignals(False)
        self._debounce_refresh()

    # --------------- Refresh (pubblico) ---------------
    def refresh(self):
        # refresh immediato (senza debounce), comunque async
        self._refresh_async()

    def _debounce_refresh(self):
        self._debounce.start()

    # --------------- Async ---------------
    def _refresh_async(self):
        if self._busy:
            # incrementa seq per invalidare il job in corso quando completa
            self._refresh_seq += 1
            # lasciamo finire il job corrente ma ignoreremo il suo risultato
        seq = self._refresh_seq + 1
        self._refresh_seq = seq
        self._busy = True

        d1, d2 = self._selected_dates()
        euro = self.euro_per_kg

        def _job():
            totals = self.repo.report_totals_sqlite(d1, d2, euro)
            daily = self.repo.report_daily_sqlite(d1, d2, euro)
            return {"seq": seq, "totals": totals, "daily": daily}

        worker = _FuncWorker(_job)
        worker.signals.done.connect(self._on_done)
        worker.signals.error.connect(self._on_error)
        self._pool.start(worker)

    @QtCore.pyqtSlot(object)
    def _on_done(self, res: object):
        try:
            data = dict(res or {})
            seq = int(data.get("seq", -1))
            # se nel frattempo l'utente ha cambiato ancora date, scarta questo risultato
            if seq != self._refresh_seq:
                return

            totals = data.get("totals") or {}
            daily = data.get("daily") or []

            # Riepilogo
            kg = float(totals.get("kg", 0.0))
            lordo = float(totals.get("lordo", 0.0))
            abbuoni = float(totals.get("abbuoni", 0.0))
            netto = float(totals.get("netto", lordo - abbuoni))

            self.lbl_kg.setText(f"Kg totali: {self._fmt_kg(kg)}")
            self.lbl_lordo.setText(f"Lordo: € {self._fmt_money(lordo)}")
            self.lbl_abbuoni.setText(f"Abbuoni: € {self._fmt_money(abbuoni)}")
            self.lbl_netto.setText(f"Netto: € {self._fmt_money(netto)}")

            # Tabelle
            by_pay: Dict[str, Tuple[float, float]] = totals.get("by_pagamento", {}) or {}
            self._populate_pay_table(by_pay, abbuoni)
            self._populate_days_table(daily)
        finally:
            self._busy = False

    @QtCore.pyqtSlot(str)
    def _on_error(self, msg: str):
        self._busy = False
        QtWidgets.QMessageBox.warning(self, "Report", f"Errore lettura report: {msg}")

    # --------------- Popolamento tabelle ---------------
    def _populate_pay_table(self, by_pay: Dict[str, Tuple[float, float]], abbuoni_total: float):
        """
        by_pay: { 'Contanti': (kg, lordo), '': (kg, lordo), ... }
        - Metodo vuoto -> 'Da Saldare'
        - Netto per gruppo = lordo_gruppo - quota_abbuoni_proporzionale_ai_kg
        """
        self.model_pay.removeRows(0, self.model_pay.rowCount())

        tot_kg = sum(kg for (kg, _lordo) in by_pay.values()) or 0.0

        items: List[Tuple[str, float, float]] = []
        for raw_pay, (kg, lordo) in by_pay.items():
            label = (raw_pay or "").strip() or _EMPTY_METHOD_LABEL
            items.append((label, float(kg or 0.0), float(lordo or 0.0)))

        items.sort(key=lambda x: x[0].lower())

        for label, kg, lordo in items:
            quota = (kg / tot_kg * abbuoni_total) if tot_kg > 0 else 0.0
            netto = lordo - quota

            row = [
                QtGui.QStandardItem(label),
                QtGui.QStandardItem(self._fmt_kg(kg)),
                QtGui.QStandardItem(self._fmt_money(lordo)),
                QtGui.QStandardItem(self._fmt_money(netto)),
            ]
            for it in row:
                it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.model_pay.appendRow(row)

        self.table_pay.resizeColumnsToContents()
        self.table_pay.horizontalHeader().setStretchLastSection(True)

    def _populate_days_table(self, daily_rows: List[Dict[str, float]]):
        """
        daily_rows: lista di dict {'data': 'gg/mm/aaaa', 'kg':..., 'lordo':..., 'abbuoni':..., 'netto':...}
        """
        self.model_days.removeRows(0, self.model_days.rowCount())

        for r in daily_rows:
            data = str(r.get("data", ""))
            kg = float(r.get("kg", 0.0))
            lordo = float(r.get("lordo", 0.0))
            abbuoni = float(r.get("abbuoni", 0.0))
            netto = float(r.get("netto", lordo - abbuoni))

            row = [
                QtGui.QStandardItem(data),
                QtGui.QStandardItem(self._fmt_kg(kg)),
                QtGui.QStandardItem(self._fmt_money(lordo)),
                QtGui.QStandardItem(self._fmt_money(abbuoni)),
                QtGui.QStandardItem(self._fmt_money(netto)),
            ]
            for it in row:
                it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.model_days.appendRow(row)

        self.table_days.resizeColumnsToContents()
        self.table_days.horizontalHeader().setStretchLastSection(True)
