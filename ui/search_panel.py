"""Pannello di ricerca per giorno o intervallo di date."""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6 import QtCore, QtWidgets

from app_frantoio.ui.calendar import configure_calendar


def py_date(qdate: QtCore.QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def soft_combo(parent=None) -> QtWidgets.QComboBox:
    """Combo Qt non-nativa: popup coerente, più morbido su macOS."""
    combo = QtWidgets.QComboBox(parent)
    popup = QtWidgets.QListView(combo)
    popup.setObjectName("softComboPopup")
    popup.setSpacing(3)
    popup.setUniformItemSizes(True)
    combo.setView(popup)
    combo.setMinimumHeight(40)
    return combo


class MolitureSearchPanel(QtWidgets.QFrame):
    scopeChanged = QtCore.pyqtSignal()
    searchRequested = QtCore.pyqtSignal()
    filtersChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterCard")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(20, 17, 20, 18)
        outer.setSpacing(13)

        heading_row = QtWidgets.QHBoxLayout()
        heading_row.setSpacing(10)
        self.header = QtWidgets.QLabel("RICERCA MOLITURE")
        self.header.setObjectName("sectionEyebrow")
        heading_row.addWidget(self.header)
        self.hint = QtWidgets.QLabel("Filtra i record senza interrompere il lavoro")
        self.hint.setObjectName("mutedLabel")
        heading_row.addWidget(self.hint)
        heading_row.addStretch()
        outer.addLayout(heading_row)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(10)
        date_row.addWidget(QtWidgets.QLabel("Periodo"))
        self.mode_combo = soft_combo(self)
        self.mode_combo.addItem("Un giorno", "day")
        self.mode_combo.addItem("Più giorni", "range")
        self.mode_combo.setAccessibleName("Modalità ricerca per data")
        date_row.addWidget(self.mode_combo)

        # Il giorno singolo viene mostrato nella barra superiore principale,
        # fuori dal pannello filtri. Rimane sempre disponibile.
        self.date_edit = QtWidgets.QDateEdit(self)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setAccessibleName("Seleziona il giorno delle moliture")
        configure_calendar(self.date_edit)
        self.date_edit.setDate(QtCore.QDate.currentDate())

        self.range_group = QtWidgets.QWidget(self)
        self.range_group.setObjectName("rangeControls")
        range_layout = QtWidgets.QHBoxLayout(self.range_group)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(10)
        range_layout.addWidget(QtWidgets.QLabel("Dal"))
        self.date_from = QtWidgets.QDateEdit()
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        configure_calendar(self.date_from)
        self.date_from.setDate(QtCore.QDate.currentDate().addDays(-7))
        range_layout.addWidget(self.date_from)
        range_layout.addWidget(QtWidgets.QLabel("Al"))
        self.date_to = QtWidgets.QDateEdit()
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        configure_calendar(self.date_to)
        self.date_to.setDate(QtCore.QDate.currentDate())
        range_layout.addWidget(self.date_to)
        date_row.addWidget(self.range_group)

        self.btn_apply = QtWidgets.QPushButton("Cerca nel periodo")
        self.btn_apply.setObjectName("primaryButton")
        date_row.addWidget(self.btn_apply)
        date_row.addStretch()
        outer.addLayout(date_row)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(10)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Nome cliente, data o altri dettagli...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(220)
        self.search_edit.setAccessibleName("Ricerca testuale moliture")
        filter_row.addWidget(self.search_edit, 3)

        self.payment_combo = soft_combo(self)
        self.payment_combo.setAccessibleName("Filtro metodo di pagamento")
        self.payment_combo.addItem("Tutti i pagamenti", "")
        self.payment_combo.addItem("Da saldare", "__unpaid__")
        for method in ("Contanti", "POS", "Assegno", "Olio"):
            self.payment_combo.addItem(method, method)
        self.payment_combo.addItem("Altri metodi", "__other__")
        filter_row.addWidget(self.payment_combo, 2)

        self.min_weight = QtWidgets.QDoubleSpinBox()
        self.min_weight.setRange(0, 100000)
        self.min_weight.setDecimals(2)
        self.min_weight.setSingleStep(10)
        self.min_weight.setSpecialValueText("Kg min")
        self.min_weight.setAccessibleName("Peso minimo in kg")
        filter_row.addWidget(self.min_weight, 1)

        self.max_weight = QtWidgets.QDoubleSpinBox()
        self.max_weight.setRange(0, 100000)
        self.max_weight.setDecimals(2)
        self.max_weight.setSingleStep(10)
        self.max_weight.setSpecialValueText("Kg max")
        self.max_weight.setAccessibleName("Peso massimo in kg")
        filter_row.addWidget(self.max_weight, 1)

        self.btn_clear = QtWidgets.QPushButton("Azzera filtri")
        self.btn_clear.setObjectName("subtleButton")
        filter_row.addWidget(self.btn_clear)
        outer.addLayout(filter_row)

        self.range_group.hide()
        self.btn_apply.hide()
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.date_edit.dateChanged.connect(self._day_changed)
        self.btn_apply.clicked.connect(lambda _checked=False: self.searchRequested.emit())
        self.btn_clear.clicked.connect(self.reset_filters)
        self.search_edit.textChanged.connect(lambda _value: self.filtersChanged.emit())
        self.payment_combo.currentIndexChanged.connect(lambda _idx: self.filtersChanged.emit())
        self.min_weight.valueChanged.connect(lambda _value: self.filtersChanged.emit())
        self.max_weight.valueChanged.connect(lambda _value: self.filtersChanged.emit())

    def is_range_mode(self) -> bool:
        return self.mode_combo.currentData() == "range"

    def scope(self) -> tuple[date, date]:
        if not self.is_range_mode():
            d = py_date(self.date_edit.date())
            return d, d
        left, right = py_date(self.date_from.date()), py_date(self.date_to.date())
        return (left, right) if left <= right else (right, left)

    def _day_changed(self, _date: QtCore.QDate):
        """Cambiare il giorno riporta alla vista giornaliera, anche da range."""
        if self.is_range_mode():
            # _mode_changed emette già scopeChanged una volta sola.
            self.mode_combo.setCurrentIndex(0)
        else:
            self.scopeChanged.emit()

    def _mode_changed(self, _index: int):
        expanded = self.is_range_mode()
        self.range_group.setVisible(expanded)
        self.btn_apply.setVisible(expanded)
        self.scopeChanged.emit()

    def reset_filters(self, _checked=False):
        """Ripristina giorno odierno e tutti i filtri, senza richieste duplicate."""
        self.blockSignals(True)
        try:
            self.search_edit.clear()
            self.payment_combo.setCurrentIndex(0)
            self.min_weight.setValue(0)
            self.max_weight.setValue(0)
            self.date_edit.setDate(QtCore.QDate.currentDate())
            self.date_from.setDate(QtCore.QDate.currentDate().addDays(-7))
            self.date_to.setDate(QtCore.QDate.currentDate())
            self.mode_combo.setCurrentIndex(0)
        finally:
            self.blockSignals(False)
        self.filtersChanged.emit()
        self.scopeChanged.emit()
