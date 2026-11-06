from __future__ import annotations
import os
from datetime import date
from PyQt6 import QtWidgets, QtCore, QtGui
from pathlib import Path
import pandas as pd
from typing import TYPE_CHECKING, Optional, Callable

from app_frantoio.resources import resource_path
from app_frantoio.models.moliture_model import MolitureModel
from app_frantoio.models.filter_proxy import MolitureFilterProxy
from app_frantoio.ui.search_panel import MolitureSearchPanel
from app_frantoio.util.time_utils import fmt_ts, fmt_date_time
from app_frantoio.ui.reports_widget import ReportsPage
from app_frantoio.ui.edit_record_dialog import EditRecordDialog
from app_frantoio.ui.theme import apply_theme, normalize_theme
from app_frantoio.util.config import save_config
from app_frantoio.ui.calendar import configure_calendar

if TYPE_CHECKING:
    from app_frantoio.core.repository import HybridRepository


# ---------------------- Icona app ----------------------
def _find_icon_path() -> Path:
    try:
        p = Path(resource_path("app.ico"))
        if p.exists():
            return p
    except Exception:
        pass
    base = Path(QtCore.QCoreApplication.applicationDirPath())
    for c in [
        base / "resources" / "app.ico",
        base / "app_frantoio" / "resources" / "app.ico",
        base / "app.ico",
    ]:
        if c.exists():
            return c
    return Path()


def _app_icon() -> QtGui.QIcon:
    p = _find_icon_path()
    return QtGui.QIcon(str(p)) if p.exists() else QtGui.QIcon()


# ---------------------- LoginDialog ----------------------
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


# ---------------------- Worker generico (thread pool) ----------------------
class _WorkerSignals(QtCore.QObject):
    done = QtCore.pyqtSignal(object)   # result
    error = QtCore.pyqtSignal(str)     # error message


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


# ---------------------- Delegate Abbuono ----------------------
class AbbuonoDelegate(QtWidgets.QStyledItemDelegate):
    editingStarted = QtCore.pyqtSignal()

    def createEditor(self, parent, option, index):
        self.editingStarted.emit()  # pausa timer subito
        edit = QtWidgets.QLineEdit(parent)
        edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        rx = QtCore.QRegularExpression(r"^\s*\d{0,12}([.,]\d{0,2})?\s*$")
        edit.setValidator(QtGui.QRegularExpressionValidator(rx, edit))
        edit.returnPressed.connect(lambda: self.commitData.emit(edit))
        edit.returnPressed.connect(lambda: self.closeEditor.emit(
            edit, QtWidgets.QAbstractItemDelegate.EndEditHint.NoHint))
        edit.editingFinished.connect(lambda: self.commitData.emit(edit))
        edit.editingFinished.connect(lambda: self.closeEditor.emit(
            edit, QtWidgets.QAbstractItemDelegate.EndEditHint.NoHint))
        return edit

    def setEditorData(self, editor, index):
        val = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        try:
            editor.setText(f"{float(val or 0.0):.2f}")
        except Exception:
            editor.setText("0.00")

    def setModelData(self, editor, model, index):
        txt = editor.text().strip().replace(",", ".")
        try:
            value = float(txt) if txt else 0.0
        except ValueError:
            value = 0.0
        model.setData(index, value, QtCore.Qt.ItemDataRole.EditRole)


# ---------------------- MainWindow ----------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg, repo: HybridRepository):
        super().__init__()
        self.cfg = cfg
        self.repo = repo
        self.euro_per_kg = float(cfg.get("euro_per_kg", 0.30))
        self.poll_ms = max(1000, min(2000, int(cfg.get("poll_ms", 2000))))
        self._export_path = None
        self._busy = False  # fix cursore/ri-entrance
        self._sync_busy = False
        self._save_busy = False
        self._edit_open = False
        self._suppress_model_auto_save = False

        # tracking selezione per evitare "rimbalzi" dopo refresh
        self._last_selected_id: Optional[str] = None
        self._sel_serial: int = 0  # aumenta ad ogni cambio selezione
        self._updating_table = False
        self._refresh_pending = False

        self.setWindowTitle("Frantoio | Gestione moliture")
        self._theme = apply_theme(normalize_theme(self.cfg.get("theme", "light")))
        self.resize(1200, 700)
        self.setWindowIcon(_app_icon())

        # Barra superiore sempre visibile, anche nella sezione Report.
        self.app_toolbar = QtWidgets.QToolBar("Barra principale", self)
        self.app_toolbar.setObjectName("appToolbar")
        self.app_toolbar.setMovable(False)
        self.app_toolbar.setFloatable(False)
        self.addToolBar(self.app_toolbar)
        self.brand_label = QtWidgets.QLabel("FRANTOIO")
        self.brand_label.setObjectName("brandTitle")
        self.app_toolbar.addWidget(self.brand_label)
        self.brand_subtitle = QtWidgets.QLabel("  /  Gestione moliture")
        self.brand_subtitle.setObjectName("brandSubtitle")
        self.app_toolbar.addWidget(self.brand_subtitle)

        toolbar_spacer = QtWidgets.QWidget(self)
        toolbar_spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.app_toolbar.addWidget(toolbar_spacer)
        self.theme_label = QtWidgets.QLabel("Aspetto:  ")
        self.app_toolbar.addWidget(self.theme_label)
        self.theme_switch = QtWidgets.QComboBox()
        self.theme_switch.setObjectName("themeSwitch")
        self.theme_switch.setAccessibleName("Selezione tema dell'applicazione")
        self.theme_switch.addItem("Chiaro", "light")
        self.theme_switch.addItem("Scuro", "dark")
        self.theme_switch.setCurrentIndex(1 if self._theme == "dark" else 0)
        self.theme_switch.setToolTip(
            "Cambia aspetto. La scelta viene salvata per i prossimi avvii."
        )
        self.app_toolbar.addWidget(self.theme_switch)

        # TABS
        self.tabs = QtWidgets.QTabWidget(self)

        # --- TAB 1: Lista ---
        page_list = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(page_list)
        vbox.setContentsMargins(22, 18, 22, 18)
        vbox.setSpacing(16)

        # Il calendario del singolo giorno rimane sempre visibile.
        self.filters = MolitureSearchPanel(self)

        # Barra compatta: le azioni quotidiane restano visibili, i filtri no.
        table_toolbar = QtWidgets.QHBoxLayout()
        table_toolbar.setSpacing(10)
        heading = QtWidgets.QLabel("Moliture")
        heading.setObjectName("pageTitle")
        table_toolbar.addWidget(heading)
        table_toolbar.addStretch(1)

        self.day_picker_label = QtWidgets.QLabel("Giorno:")
        table_toolbar.addWidget(self.day_picker_label)
        table_toolbar.addWidget(self.filters.date_edit)

        self.filter_summary = QtWidgets.QLabel("Oggi")
        self.filter_summary.setObjectName("filterSummary")
        self.filter_summary.setToolTip("Periodo e filtri attualmente applicati")
        table_toolbar.addWidget(self.filter_summary)

        self.btn_toggle_filters = QtWidgets.QPushButton("Ricerca e filtri")
        self.btn_toggle_filters.setObjectName("filterToggleButton")
        self.btn_toggle_filters.setCheckable(True)
        self.btn_toggle_filters.setChecked(False)
        self.btn_toggle_filters.setAccessibleName("Mostra o nascondi i filtri di ricerca")
        self.btn_toggle_filters.setToolTip("Apri i filtri per ricerca, date e pagamenti")
        table_toolbar.addWidget(self.btn_toggle_filters)

        self.btn_refresh = QtWidgets.QPushButton("Aggiorna")
        self.btn_refresh.setObjectName("subtleButton")
        table_toolbar.addWidget(self.btn_refresh)
        self.btn_export = QtWidgets.QPushButton("Esporta Excel")
        table_toolbar.addWidget(self.btn_export)
        vbox.addLayout(table_toolbar)

        vbox.addWidget(self.filters)
        self.date_edit = self.filters.date_edit
        self.search_edit = self.filters.search_edit
        self._applied_scope = self.filters.scope()
        self.filters.hide()  # Alla prima apertura si vede solo la tabella.
        self._update_filter_summary()

        self.table = QtWidgets.QTableView()
        self.model = MolitureModel([], self.euro_per_kg, self)
        self.proxy = MolitureFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        # Dalla prima molitura all'ultima, secondo il timestamp reale.
        self.table.sortByColumn(4, QtCore.Qt.SortOrder.AscendingOrder)
        self.table.verticalHeader().setDefaultSectionSize(43)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        # Il nome si adatta automaticamente al contenuto, anche dopo l'arrivo
        # di nuovi record; le altre colonne conservano larghezze indipendenti.
        # La scansione Qt di tutte le celle ad ogni refresh era lenta su Windows.
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 230)
        vbox.addWidget(self.table)

        # Doppio clic apre sempre la finestra completa di modifica.
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        self.abbuono_delegate = AbbuonoDelegate(self.table)
        self.table.setItemDelegateForColumn(3, self.abbuono_delegate)

        self.model.dataChanged.connect(self.on_model_changed)

        self.abbuono_delegate.editingStarted.connect(self._on_editor_start)
        self.abbuono_delegate.commitData.connect(self._on_editor_commit)
        self.abbuono_delegate.closeEditor.connect(self._on_editor_closed)

        # traccia ogni cambio selezione dell'utente
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        footer = QtWidgets.QHBoxLayout()
        self.lbl_tot = QtWidgets.QLabel("0 moliture · 0,00 kg")
        self.lbl_tot.setObjectName("resultsSummary")
        footer.addWidget(self.lbl_tot)
        footer.addStretch(1)
        footer.addWidget(QtWidgets.QLabel("Pagamento rapido:"))
        self.cmb_pagamento_quick = QtWidgets.QComboBox()
        self.cmb_pagamento_quick.addItems(["", "Contanti", "POS", "Assegno", "Olio"])
        self.btn_edit_row = QtWidgets.QPushButton("Modifica record")
        self.btn_edit_row.setObjectName("primaryButton")
        self.btn_set_pagamento = QtWidgets.QPushButton("Applica pagamento")
        self.btn_delete_row = QtWidgets.QPushButton("Elimina")
        self.btn_delete_row.setObjectName("dangerButton")
        footer.addWidget(self.btn_edit_row)
        footer.addWidget(self.cmb_pagamento_quick)
        footer.addWidget(self.btn_set_pagamento)
        footer.addWidget(self.btn_delete_row)
        vbox.addLayout(footer)

        self.tabs.addTab(page_list, "Lista")

        # --- TAB 2: Report ---
        self.reports_page = ReportsPage(self.repo, self.euro_per_kg, self)
        self.tabs.addTab(self.reports_page, "Report")

        self.setCentralWidget(self.tabs)

        # Thread pool
        self._pool = QtCore.QThreadPool.globalInstance()

        # Timer refresh tabella (auto): NON mostra cursore
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.poll_ms)
        self.timer.timeout.connect(self._automatic_refresh)

        # Timer mirror (senza cleanup)
        self.sync_timer = QtCore.QTimer(self)
        minutes = max(1, int(self.cfg.get("mirror_interval_minutes", 5)))
        self.sync_timer.setInterval(minutes * 60 * 1000)
        self.sync_timer.timeout.connect(self.auto_sync)

        # Signals
        # Le modifiche a periodo e filtri sono gestite dal pannello ricerca.
        self.filters.scopeChanged.connect(self._on_scope_changed)
        self.filters.searchRequested.connect(
            lambda: self.refresh_data(show_cursor=True, apply_scope=True)
        )
        self.filters.filtersChanged.connect(self._apply_local_filters)
        self.btn_toggle_filters.toggled.connect(self._toggle_filters)
        self.btn_refresh.clicked.connect(
            lambda _checked=False: self.refresh_data(show_cursor=True, apply_scope=True)
        )
        self.btn_export.clicked.connect(self.export_excel)
        self.btn_edit_row.clicked.connect(self.on_edit_clicked)
        self.table.doubleClicked.connect(self.on_edit_clicked)
        self.theme_switch.currentIndexChanged.connect(self._change_theme)
        self.btn_set_pagamento.clicked.connect(self.on_set_pagamento_clicked)
        self.btn_delete_row.clicked.connect(self.on_delete_clicked)

        # Avvio
        QtCore.QTimer.singleShot(200, self.refresh_data)              # primo load (show_cursor=True)
        # Il mirror completo non deve rallentare il primo caricamento.
        QtCore.QTimer.singleShot(15000, self.auto_sync)
        self.timer.start()
        self.sync_timer.start()

    def _toggle_filters(self, expanded: bool) -> None:
        """Mostra o nasconde il pannello senza modificare i filtri attivi."""
        self.filters.setVisible(expanded)
        self.btn_toggle_filters.setText(
            "Nascondi filtri" if expanded else "Ricerca e filtri"
        )
        self.btn_toggle_filters.setToolTip(
            "Chiudi il pannello, mantenendo la ricerca corrente"
            if expanded else "Apri i filtri per ricerca, date e pagamenti"
        )
        if expanded:
            self.search_edit.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)

    def _update_filter_summary(self) -> None:
        """Mantiene leggibile la ricerca corrente anche a pannello chiuso."""
        start, end = self._applied_scope
        if start != end:
            label = f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
        elif start == date.today():
            label = "Oggi"
        else:
            label = start.strftime("%d/%m/%Y")

        count = 0
        if self.filters.search_edit.text().strip():
            count += 1
        if self.filters.payment_combo.currentData():
            count += 1
        if self.filters.min_weight.value() > 0:
            count += 1
        if self.filters.max_weight.value() > 0:
            count += 1
        if count:
            label += f" · {count} " + ("filtro" if count == 1 else "filtri")
        self.filter_summary.setText(label)

    def _automatic_refresh(self) -> None:
        # La ricerca storica può coprire centinaia di giorni. Non scaricare
        # l'intero intervallo ogni tre secondi: serve il pulsante Cerca.
        if not self.filters.is_range_mode() and not self._edit_open:
            self.refresh_data(show_cursor=False)

    def _on_scope_changed(self) -> None:
        self.refresh_data(show_cursor=False, apply_scope=True)
        self._update_filter_summary()

    def _apply_local_filters(self) -> None:
        self.proxy.set_search_text(self.filters.search_edit.text())
        self.proxy.set_payment(self.filters.payment_combo.currentData() or "")
        self.proxy.set_weight_bounds(
            self.filters.min_weight.value(), self.filters.max_weight.value()
        )
        self.update_total(self.model.all_rows())
        self._update_filter_summary()

    def _change_theme(self, _index: int) -> None:
        """Applica il tema subito e salva la preferenza nell'area utente."""
        requested = normalize_theme(self.theme_switch.currentData())
        if requested == self._theme:
            return
        self._theme = apply_theme(requested)
        self.cfg["theme"] = self._theme
        try:
            save_config(self.cfg)
        except OSError as exc:
            self.statusBar().showMessage(
                f"Tema attivato, ma non è stato possibile salvare la preferenza: {exc}",
                7000,
            )
        else:
            self.statusBar().showMessage(
                "Tema scuro attivato." if requested == "dark" else "Tema chiaro attivato.",
                3000,
            )

    # ---------------------- Helpers selezione ----------------------
    def _on_selection_changed(self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection):
        if self._updating_table:
            return
        self._last_selected_id = self._current_selected_id()
        self._sel_serial += 1

    def _current_selected_id(self) -> Optional[str]:
        sm = self.table.selectionModel()
        if sm is None:
            return None
        selected = sm.selectedRows()
        if not selected:
            return None
        source = self.proxy.mapToSource(selected[0])
        if not source.isValid():
            return None
        return self.model.row_at(source.row()).get("id")

    def _reselect_by_id(self, rid: Optional[str]) -> bool:
        """Ripristina la selezione senza scrollTo: mai saltare in cima."""
        if not rid:
            return False
        if self._current_selected_id() == rid:
            return True  # Qt ha già mantenuto la selezione: non toccarla.
        sm = self.table.selectionModel()
        if sm is None:
            return False
        for row_index, row in enumerate(self.model.all_rows()):
            if row.get("id") != rid:
                continue
            proxy_idx = self.proxy.mapFromSource(self.model.index(row_index, 0))
            if not proxy_idx.isValid():
                return False  # record nascosto dal filtro, non forzare la vista
            blocker = QtCore.QSignalBlocker(sm)
            try:
                sm.select(
                    proxy_idx,
                    QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
                    | QtCore.QItemSelectionModel.SelectionFlag.Rows,
                )
                sm.setCurrentIndex(
                    proxy_idx, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate
                )
            finally:
                del blocker
            return True
        return False

    def _selected_date(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    # ---------------------- Busy UI / Cursor fix ----------------------
    def _set_busy(self, busy: bool):
        """Il polling non deve disabilitare tabella e pulsante Modifica."""
        self._busy = busy
        self.btn_refresh.setEnabled(not busy)
        if busy:
            self.statusBar().showMessage("Aggiornamento moliture...", 3000)

    def _resize_name_column(self, rows):
        """Una scansione leggera dei nomi, senza ResizeToContents Qt."""
        fm = self.table.fontMetrics()
        width = max(230, max(
            (fm.horizontalAdvance(str(row.get("name") or row.get("nome") or ""))
             for row in rows),
            default=0,
        ) + 46)
        self.table.setColumnWidth(0, min(width, 520))

    # ---------------------- Refresh (in background) ----------------------
    def refresh_data(self, show_cursor: bool = True, apply_scope: bool = False):
        if self.table.state() == QtWidgets.QAbstractItemView.State.EditingState:
            return
        if apply_scope:
            proposed_scope = self.filters.scope()
            if (proposed_scope[1] - proposed_scope[0]).days > 366:
                QtWidgets.QMessageBox.warning(
                    self, "Intervallo troppo ampio",
                    "Seleziona un intervallo massimo di 367 giorni."
                )
                return
            self._applied_scope = proposed_scope
            self._update_filter_summary()

        if self._busy or self._save_busy or self._edit_open:
            # Se l'utente cambia periodo durante una richiesta, effettua
            # la nuova ricerca alla sua conclusione; mai mostrare dati vecchi.
            if apply_scope or show_cursor:
                self._refresh_pending = True
            return

        requested_scope = self._applied_scope
        selection_at_start = self._current_selected_id()
        serial_at_start = self._sel_serial

        if show_cursor:
            self._set_busy(True)
        else:
            self._busy = True

        worker = _FuncWorker(self.repo.fetch_range, *requested_scope)
        worker.signals.done.connect(
            lambda rows: self._on_refresh_done(
                rows, requested_scope, selection_at_start,
                serial_at_start, show_cursor
            )
        )
        worker.signals.error.connect(
            lambda msg: self._on_refresh_error(msg, requested_scope, show_cursor)
        )
        self._pool.start(worker)

    def _finish_refresh(self, show_cursor: bool):
        if show_cursor:
            self._set_busy(False)
        else:
            self._busy = False
        if self._refresh_pending and not self._edit_open and not self._save_busy:
            self._refresh_pending = False
            QtCore.QTimer.singleShot(
                0, lambda: self.refresh_data(show_cursor=False)
            )

    def _on_refresh_done(self, rows, requested_scope: tuple[date, date],
                         selection_at_start: Optional[str],
                         serial_at_start: int, show_cursor: bool):
        try:
            # Scarta un vecchio snapshot caricato mentre un pagamento
            # veniva aggiornato: altrimenti sovrascriverebbe la cella subito.
            if (requested_scope != self._applied_scope
                    or self._edit_open or self._save_busy):
                self._refresh_pending = True
                return

            vbar = self.table.verticalScrollBar()
            hbar = self.table.horizontalScrollBar()
            vpos, hpos = vbar.value(), hbar.value()
            selected_now = self._current_selected_id()
            target = (
                selected_now if self._sel_serial != serial_at_start
                else selection_at_start
            )

            rows_list = list(rows or [])
            rows_list.sort(key=lambda row: int(float(row.get("dataOra") or 0)))
            self._updating_table = True
            try:
                changed = self.model.set_rows(rows_list)
                if changed:
                    self._resize_name_column(rows_list)
                    self._reselect_by_id(target)
                    vbar.setValue(min(vpos, vbar.maximum()))
                    hbar.setValue(min(hpos, hbar.maximum()))
                self._last_selected_id = self._current_selected_id()
            finally:
                self._updating_table = False
            self.update_total(rows_list)
        finally:
            self._finish_refresh(show_cursor)

    def _on_refresh_error(self, msg: str,
                          requested_scope: tuple[date, date], show_cursor: bool):
        self._finish_refresh(show_cursor)
        if requested_scope != self._applied_scope:
            return
        if show_cursor:
            QtWidgets.QMessageBox.warning(self, "Ricerca moliture", f"Errore: {msg}")
        else:
            self.statusBar().showMessage(f"Impossibile aggiornare: {msg}", 6000)

    def update_total(self, rows):
        total_kg = 0.0
        visible = self.proxy.rowCount()
        for i in range(visible):
            idx = self.proxy.mapToSource(self.proxy.index(i, 0))
            r = self.model.row_at(idx.row())
            try:
                total_kg += float(r.get("weight") or r.get("peso") or 0)
            except (TypeError, ValueError):
                pass
        self.lbl_tot.setText(
            f"{visible} di {len(rows)} moliture  ·  {total_kg:,.2f} kg nei risultati"
        )

    # ---------------------- Auto-sync (mirror in background) ----------------------
    def auto_sync(self):
        if self._busy or self._sync_busy or self._save_busy:
            return
        self._sync_busy = True

        def _mirror():
            return self.repo.mirror_only()

        worker = _FuncWorker(_mirror)
        def on_sync_done(mirrored):
            self._sync_busy = False
            self.statusBar().showMessage(f"Sincronizzati {mirrored} record.", 5000)
        def on_sync_error(msg):
            self._sync_busy = False
            self.statusBar().showMessage(f"Sincronizzazione non riuscita: {msg}", 7000)
        worker.signals.done.connect(on_sync_done)
        worker.signals.error.connect(on_sync_error)
        self._pool.start(worker)

    def on_edit_clicked(self, *args):
        # Letture e sincronizzazioni Firebase non bloccano l'editor.
        if self._save_busy or self._edit_open:
            return
        selected = self.table.selectionModel().selectedRows()
        view_index = selected[0] if selected else self.table.currentIndex()
        if (not view_index.isValid() and args
                and isinstance(args[0], QtCore.QModelIndex)):
            view_index = args[0]
        if not view_index.isValid():
            QtWidgets.QMessageBox.information(
                self, "Modifica", "Seleziona una molitura."
            )
            return
        source_index = self.proxy.mapToSource(view_index)
        if not source_index.isValid():
            return

        original = self.model.row_at(source_index.row()).copy()
        self._edit_open = True
        self.timer.stop()
        try:
            dlg = EditRecordDialog(original, self.euro_per_kg, self)
            if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return
            changes = dlg.changed_fields()
            if not changes:
                self.statusBar().showMessage("Nessuna modifica da salvare.", 3000)
                return
            self._save_busy = True
            self.btn_edit_row.setEnabled(False)
            self.statusBar().showMessage("Salvataggio modifiche in corso...")
            worker = _FuncWorker(self.repo.update_record, original, changes)
            worker.signals.done.connect(self._on_record_saved)
            worker.signals.error.connect(self._on_record_save_failed)
            self._pool.start(worker)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Modifica non disponibile",
                f"Impossibile aprire la finestra di modifica: {exc}"
            )
        finally:
            self._edit_open = False
            if not self._save_busy:
                if not self.timer.isActive():
                    self.timer.start()
                if self._refresh_pending and not self._busy:
                    self._refresh_pending = False
                    QtCore.QTimer.singleShot(
                        0, lambda: self.refresh_data(show_cursor=False)
                    )

    def _on_record_saved(self, changes):
        self._save_busy = False
        self.btn_edit_row.setEnabled(True)
        self.statusBar().showMessage("Modifiche salvate correttamente.", 5000)
        self._refresh_pending = False
        self.refresh_data(show_cursor=False, apply_scope=True)
        self.reports_page.refresh()
        if not self.timer.isActive():
            self.timer.start()

    def _on_record_save_failed(self, msg):
        self._save_busy = False
        self.btn_edit_row.setEnabled(True)
        QtWidgets.QMessageBox.warning(self, "Salvataggio non riuscito", msg)
        self.refresh_data(show_cursor=False, apply_scope=True)
        if not self.timer.isActive():
            self.timer.start()

    # ---------------------- Azioni UI ----------------------
    def _patch_row_without_auto_save(self, rid: str, changes: dict) -> bool:
        """Aggiorna la tabella senza attivare il vecchio editor inline."""
        self._suppress_model_auto_save = True
        try:
            return self.model.patch_record_locally(rid, changes)
        finally:
            self._suppress_model_auto_save = False

    def on_set_pagamento_clicked(self):
        if self._save_busy:
            self.statusBar().showMessage(
                "Salvataggio già in corso: riprova dopo la conferma.", 5500
            )
            return
        if self._edit_open:
            self.statusBar().showMessage(
                "Concludi la modifica del record prima di cambiare il pagamento.",
                5500,
            )
            return

        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QtWidgets.QMessageBox.information(
                self, "Pagamento", "Seleziona una molitura."
            )
            return
        source_idx = self.proxy.mapToSource(selected[0])
        if not source_idx.isValid():
            QtWidgets.QMessageBox.warning(
                self, "Pagamento", "La riga selezionata non è più disponibile."
            )
            return
        row = self.model.row_at(source_idx.row()).copy()
        rid = row.get("id")
        if not rid:
            QtWidgets.QMessageBox.warning(self, "Pagamento", "ID record mancante.")
            return

        payment = self.cmb_pagamento_quick.currentText()
        previous_payment = row.get("pagamento") or ""
        if payment == previous_payment:
            self.statusBar().showMessage(
                "Il metodo di pagamento è già impostato.", 3500
            )
            return
        source = row.get("_source", "firebase")
        self._save_quick_change(
            lambda: self.repo.update_pagamento(rid, payment, source),
            f"Pagamento aggiornato: {payment or 'Da saldare'}",
            optimistic=(rid, {"pagamento": payment}, {"pagamento": previous_payment}),
        )

    def on_delete_clicked(self):
        if self._busy or self._save_busy or self._sync_busy:
            return
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            QtWidgets.QMessageBox.information(self, "Cancella", "Seleziona una riga prima.")
            return

        idx = idxs[0]
        row = self.model.row_at(self.proxy.mapToSource(idx).row())
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
        source = row.get("_source", "firebase")

        msg = (
            "Vuoi cancellare il record selezionato dalla sua sorgente?\n\n"
            f"Nome: {name}\nPeso: {w:.2f} kg\nOra: {when}\n"
            f"Sorgente: {source.upper()}"
        )
        reply = QtWidgets.QMessageBox.question(
            self,
            "Conferma cancellazione",
            msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self._save_busy = True
        worker = _FuncWorker(self.repo.delete_record, rid, source)
        def done(_result):
            self._save_busy = False
            self.statusBar().showMessage("Record cancellato.", 4000)
            self.refresh_data(show_cursor=False)
            self.reports_page.refresh()
        def failed(message):
            self._save_busy = False
            QtWidgets.QMessageBox.warning(self, "Errore cancellazione", message)
            self.refresh_data(show_cursor=False)
        worker.signals.done.connect(done)
        worker.signals.error.connect(failed)
        self._pool.start(worker)

    def on_model_changed(self, topLeft: QtCore.QModelIndex, bottomRight: QtCore.QModelIndex, roles):
        if self._suppress_model_auto_save:
            return
        row = topLeft.row()
        col = topLeft.column()
        r = self.model.row_at(row)
        rid = r.get("id")
        if not rid:
            return
        source = r.get("_source", "firebase")

        if col == 3:  # Abbuono
            try:
                val = float(r.get("abbuono") or 0.0)
            except Exception:
                val = 0.0
            QtCore.QTimer.singleShot(0, lambda rid=rid, val=val, src=source: self._save_abbuono(rid, val, src))

        elif col == 5:  # Pagamento
            val = r.get("pagamento") or ""
            QtCore.QTimer.singleShot(0, lambda rid=rid, val=val, src=source: self._save_pagamento(rid, val, src))

    # --- gestione editor per evitare refresh in edit ---
    def _on_editor_start(self, *args):
        self.timer.stop()

    def _on_editor_commit(self, *args):
        self.timer.stop()

    def _on_editor_closed(self, *args):
        if not self.timer.isActive():
            self.timer.start()

    # --- salvataggi posticipati ---
    def _save_abbuono(self, rid: str, val: float, source: str):
        self._save_quick_change(
            lambda: self.repo.update_abbuono(rid, val, source),
            f"Abbuono aggiornato a € {val:.2f}"
        )

    def _save_pagamento(self, rid: str, val: str, source: str):
        self._save_quick_change(
            lambda: self.repo.update_pagamento(rid, val, source),
            f"Pagamento aggiornato: {val or 'Da saldare'}"
        )

    def _save_quick_change(self, action, success_message, optimistic=None):
        """Scrive in background e aggiorna immediatamente la riga.

        Il polling e la sincronizzazione non devono far sparire il comando:
        una richiesta gia avviata potra terminare, ma il suo snapshot viene
        scartato in _on_refresh_done finche _save_busy e vero.
        """
        if self._save_busy:
            self.statusBar().showMessage(
                "Salvataggio già in corso: attendi la conferma.", 5500
            )
            return
        self._save_busy = True
        self.btn_set_pagamento.setEnabled(False)
        self.timer.stop()
        if optimistic is not None:
            rid, new_values, _old_values = optimistic
            self._patch_row_without_auto_save(rid, new_values)
            self.statusBar().showMessage(
                "Salvataggio pagamento in corso...", 0
            )

        worker = _FuncWorker(action)

        def done(_result):
            self._save_busy = False
            self.btn_set_pagamento.setEnabled(True)
            self.statusBar().showMessage(success_message, 5000)
            # La conferma remota c'e; rileggere i dati per riallineare
            # tabella ed eventuali filtri applicati al pagamento.
            self._refresh_pending = False
            self.refresh_data(show_cursor=False)
            self.reports_page.refresh()
            if not self.timer.isActive():
                self.timer.start()

        def failed(message):
            # In caso di errore non mostrare un pagamento mai salvato.
            if optimistic is not None:
                rid, _new_values, old_values = optimistic
                self._patch_row_without_auto_save(rid, old_values)
            self._save_busy = False
            self.btn_set_pagamento.setEnabled(True)
            self._refresh_pending = False
            self.statusBar().showMessage(
                "Pagamento non salvato: valore precedente ripristinato.", 8000
            )
            QtWidgets.QMessageBox.warning(
                self, "Salvataggio non riuscito",
                f"{message}\nIl pagamento precedente è stato ripristinato."
            )
            self.refresh_data(show_cursor=False)
            if not self.timer.isActive():
                self.timer.start()

        worker.signals.done.connect(done)
        worker.signals.error.connect(failed)
        self._pool.start(worker)

    # ---------------------- Export Excel ----------------------
    def export_excel(self):
        # Esporta soltanto i risultati filtrati, non tutte le moliture
        # della giornata/periodo caricato.
        rows = [
            self.model.row_at(self.proxy.mapToSource(self.proxy.index(i, 0)).row())
            for i in range(self.proxy.rowCount())
        ]
        if not rows:
            QtWidgets.QMessageBox.information(self, "Export", "Nessun risultato da esportare.")
            return

        start_date, end_date = self._applied_scope
        sheet_name = (
            start_date.strftime("%d.%m.%Y")
            if start_date == end_date
            else f"{start_date:%d.%m}-{end_date:%d.%m.%Y}"
        )

        df = pd.DataFrame(rows)
        if "name" not in df.columns and "nome" in df.columns:
            df["name"] = df["nome"]
        if "weight" not in df.columns and "peso" in df.columns:
            df["weight"] = df["peso"]

        df["Data e ora"] = df["dataOra"].apply(fmt_date_time)
        df["abbuono"] = pd.to_numeric(df.get("abbuono", 0.0), errors="coerce").fillna(0.0)
        df["Prezzo (€)"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0) * float(self.euro_per_kg)

        cols = ["name", "weight", "Prezzo (€)", "abbuono", "Data e ora", "pagamento"]
        cols = [c for c in cols if c in df.columns]
        df = df[cols]
        df.columns = ["Nome", "Peso (Kg)", "Prezzo (€)", "Abbuono (€)", "Data e ora", "Metodo di Pagamento"]

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

            for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                for cell in row:
                    cell.alignment = Alignment(horizontal="center", vertical="center")

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
                self, "Export", f"Esportato nel foglio '{sheet_name}' di {os.path.basename(file_path)}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore export", str(e))
