from __future__ import annotations
import os
from datetime import date, datetime
from PyQt6 import QtWidgets, QtCore, QtGui
from pathlib import Path
import pandas as pd
from app_frantoio.resources import resource_path
from app_frantoio.models.moliture_model import MolitureModel
from app_frantoio.util.time_utils import fmt_ts
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from app_frantoio.core.repository import HybridRepository
    
def _find_icon_path() -> Path:
    # 1) icona impacchettata nel modulo (sviluppo / bundle con --collect-data)
    try:
        p = Path(resource_path("app.ico"))
        if p.exists():
            return p
    except Exception:
        pass

    # 2) icona installata accanto all'eseguibile: {app}\resources\app.ico
    base = Path(QtCore.QCoreApplication.applicationDirPath())
    candidates = [
        base / "resources" / "app.ico",
        base / "app_frantoio" / "resources" / "app.ico",
        base / "app.ico",
    ]
    for c in candidates:
        if c.exists():
            return c

    return Path()  # non trovata

def _app_icon() -> QtGui.QIcon:
    p = _find_icon_path()
    if p.exists():
        return QtGui.QIcon(str(p))
    return QtGui.QIcon()


class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(_app_icon())
        self.setWindowTitle("Accesso")
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("email@example.com")
        self.passw = QtWidgets.QLineEdit()
        self.passw.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.passw.setPlaceholderText("Password (min 6 caratteri)")
        form.addRow("Email", self.email)
        form.addRow("Password", self.passw)
        layout.addLayout(form)

        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

        btns = QtWidgets.QHBoxLayout()
        self.btnCancel = QtWidgets.QPushButton("Annulla")
        self.btnLogin = QtWidgets.QPushButton("Accedi")
        # Focus/Invio su "Accedi"
        self.btnLogin.setDefault(True)
        self.btnLogin.setFocus()
        btns.addStretch(1)
        btns.addWidget(self.btnCancel)
        btns.addWidget(self.btnLogin)
        layout.addLayout(btns)

        self.btnLogin.clicked.connect(self.accept)
        self.btnCancel.clicked.connect(self.reject)

    def get_credentials(self):
        return self.email.text().strip(), self.passw.text().strip()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg, repo: HybridRepository):
        super().__init__()
        self.cfg = cfg
        self.repo = repo
        self.euro_per_kg = float(cfg.get("euro_per_kg", 0.30))
        self.poll_ms = int(cfg.get("poll_ms", 3000))
        self._export_path = None

        self.setWindowTitle("Gestione Moliture - PC")
        self.resize(1000, 600)
        self.setWindowIcon(_app_icon())

        central = QtWidgets.QWidget(self)
        vbox = QtWidgets.QVBoxLayout(central)

        # Barra controlli (solo data)
        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Data:"))
        self.date_edit = QtWidgets.QDateEdit(calendarPopup=True)
        self.date_edit.setDate(QtCore.QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        controls.addWidget(self.date_edit)
        controls.addStretch(1)
        self.btn_refresh = QtWidgets.QPushButton("Aggiorna")
        self.btn_export = QtWidgets.QPushButton("Export Excel")
        controls.addWidget(self.btn_refresh)
        controls.addWidget(self.btn_export)
        vbox.addLayout(controls)

        # Tabella
        self.table = QtWidgets.QTableView()
        self.model = MolitureModel([], self.euro_per_kg, self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        vbox.addWidget(self.table)

        # Footer
        footer = QtWidgets.QHBoxLayout()
        self.lbl_tot = QtWidgets.QLabel("Totale kg: 0.00")
        footer.addWidget(self.lbl_tot)
        footer.addStretch(1)
        footer.addWidget(QtWidgets.QLabel("Pagamento rapido:"))
        self.cmb_pagamento_quick = QtWidgets.QComboBox()
        self.cmb_pagamento_quick.addItems(["", "Contanti", "POS", "Assegno", "Olio"])
        self.btn_set_pagamento = QtWidgets.QPushButton("Imposta su riga selezionata")
        # Pulsante Cancella record
        self.btn_delete_row = QtWidgets.QPushButton("Cancella record selezionato")

        footer.addWidget(self.cmb_pagamento_quick)
        footer.addWidget(self.btn_set_pagamento)
        footer.addWidget(self.btn_delete_row)
        vbox.addLayout(footer)

        self.setCentralWidget(central)

        # Timer: refresh tabella
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.poll_ms)
        self.timer.timeout.connect(self.refresh_data)

        # Timer: mirror + cleanup automatico
        self.sync_timer = QtCore.QTimer(self)
        minutes = max(1, int(self.cfg.get("mirror_interval_minutes", 5)))
        self.sync_timer.setInterval(minutes * 60 * 1000)
        self.sync_timer.timeout.connect(self.auto_sync)

        # Signals
        self.date_edit.dateChanged.connect(self.refresh_data)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_export.clicked.connect(self.export_excel)
        self.btn_set_pagamento.clicked.connect(self.on_set_pagamento_clicked)
        self.btn_delete_row.clicked.connect(self.on_delete_clicked)

        # Avvio
        QtCore.QTimer.singleShot(200, self.refresh_data)
        QtCore.QTimer.singleShot(1000, self.auto_sync)  # prima sync subito dopo l'avvio
        self.timer.start()
        self.sync_timer.start()

    # ---- Helpers per preservare selezione/scroll ----
    def _current_selected_id(self) -> Optional[str]:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        row = self.model.row_at(sel[0].row())
        return row.get("id")

    def _reselect_by_id(self, rid: Optional[str]):
        if not rid:
            return
        rows = self.model.all_rows()
        for r_idx, r in enumerate(rows):
            if r.get("id") == rid:
                idx = self.model.index(r_idx, 0)
                sm = self.table.selectionModel()
                sm.select(
                    idx,
                    QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect |
                    QtCore.QItemSelectionModel.SelectionFlag.Rows
                )
                self.table.setCurrentIndex(idx)
                self.table.scrollTo(idx, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter)
                break

    def _selected_date(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    def refresh_data(self):
        # memorizza selezione e scroll prima del reset
        prev_id = self._current_selected_id()
        vscroll = self.table.verticalScrollBar().value()

        d = self._selected_date()
        try:
            self._rows_for_day = self.repo.fetch_day(d)
        except Exception as e:
            self._rows_for_day = []
            QtWidgets.QMessageBox.warning(self, "Lettura dati", f"Errore: {e}")

        rows = list(self._rows_for_day)
        try:
            rows.sort(key=lambda r: int(float(r.get("dataOra") or 0)))
        except Exception:
            pass

        # aggiorna model
        self.model.set_rows(rows)
        self.update_total(rows)

        # ripristina scroll e selezione
        self.table.verticalScrollBar().setValue(vscroll)
        self._reselect_by_id(prev_id)

    def update_total(self, rows):
        total = 0.0
        for r in rows:
            w = r.get("weight") or r.get("peso") or 0
            try:
                total += float(w)
            except Exception:
                pass
        self.lbl_tot.setText(f"Totale kg: {total:.2f}")

    def auto_sync(self):
        """Duplica tutto FB -> SQLite e cancella da FB > retention_days."""
        try:
            res = self.repo.mirror_and_cleanup()
            self.statusBar().showMessage(
                f"Sync eseguito: salvati {res['mirrored']} record su SQLite, "
                f"cancellati {res['deleted']} oltre retention.",
                5000
            )
        except Exception as e:
            self.statusBar().showMessage(f"Sync fallito: {e}", 5000)

    def on_set_pagamento_clicked(self):
        # Pausa auto-refresh per evitare flicker mentre aggiorni
        self.timer.stop()
        try:
            idxs = self.table.selectionModel().selectedRows()
            if not idxs:
                QtWidgets.QMessageBox.information(self, "Pagamento", "Seleziona una riga prima.")
                return
            idx = idxs[0]
            row = self.model.row_at(idx.row())
            pagamento = self.cmb_pagamento_quick.currentText()
            rid = row.get("id")
            if not rid:
                raise ValueError("ID mancante")
            source = row.get("_source", "firebase")
            self.repo.update_pagamento(rid, pagamento, source)
            row["pagamento"] = pagamento
            self.model.dataChanged.emit(
                self.model.index(idx.row(), 4),
                self.model.index(idx.row(), 4),
                [QtCore.Qt.ItemDataRole.DisplayRole]
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore aggiornamento", f"{e}")
        finally:
            self.timer.start()

    def on_delete_clicked(self):
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            QtWidgets.QMessageBox.information(self, "Cancella", "Seleziona una riga prima.")
            return

        idx = idxs[0]
        row = self.model.row_at(idx.row())
        rid = row.get("id")
        if not rid:
            QtWidgets.QMessageBox.warning(self, "Cancella", "ID record mancante.")
            return

        name = row.get("name") or row.get("nome") or ""
        w = row.get("weight") or row.get("peso") or 0
        try:
            w = float(w)
        except Exception:
            w = 0.0
        when = fmt_ts(row.get("dataOra"))

        msg = f"Vuoi cancellare il record selezionato?\n\nNome: {name}\nPeso: {w:.2f} kg\nOra: {when}"
        reply = QtWidgets.QMessageBox.question(
            self,
            "Conferma cancellazione",
            msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            source = row.get("_source", "firebase")
            self.repo.delete_record(rid, source)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore cancellazione", str(e))
            return

        self.refresh_data()
        self.statusBar().showMessage("Record cancellato.", 3000)

    # Export (stesso file, foglio = data selezionata, celle centrate + autofit)
    def export_excel(self):
        rows = self.model.all_rows()
        if not rows:
            QtWidgets.QMessageBox.information(self, "Export", "Nessun dato da esportare.")
            return

        d = self._selected_date()
        sheet_name = d.strftime("%d.%m.%Y")

        df = pd.DataFrame(rows)
        if "name" not in df.columns and "nome" in df.columns:
            df["name"] = df["nome"]
        if "weight" not in df.columns and "peso" in df.columns:
            df["weight"] = df["peso"]

        df["Ora"] = df.get("dataOra", "").apply(fmt_ts)
        cols = [c for c in ["name", "weight", "Ora", "pagamento"] if c in df.columns]
        df = df[cols]
        df.columns = ["Nome", "Peso (Kg)", "Ora", "Metodo di Pagamento"]

        if not self._export_path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Seleziona file Excel", "molitura.xlsx", "Excel (*.xlsx)"
            )
            if not path:
                return
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self._export_path = path
        file_path = self._export_path

        try:
            from openpyxl import load_workbook
            from openpyxl.utils import get_column_letter
            from openpyxl.styles import Alignment

            if os.path.exists(file_path):
                with pd.ExcelWriter(file_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
            else:
                with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)

            wb = load_workbook(file_path)
            ws = wb[sheet_name]

            # Centra celle
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                for cell in row:
                    cell.alignment = Alignment(horizontal="center", vertical="center")

            # Auto-fit larghezza colonne
            for col_idx in range(1, ws.max_column + 1):
                col_letter = get_column_letter(col_idx)
                max_len = 0
                for cell in ws[col_letter]:
                    text = "" if cell.value is None else str(cell.value)
                    if len(text) > max_len:
                        max_len = len(text)
                ws.column_dimensions[col_letter].width = max_len + 2

            wb.save(file_path)
            QtWidgets.QMessageBox.information(
                self, "Export",
                f"Esportato nel foglio '{sheet_name}' di {os.path.basename(file_path)}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore export", str(e))
