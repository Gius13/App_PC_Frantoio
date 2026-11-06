"""Finestra di modifica completa di una molitura."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from PyQt6 import QtWidgets, QtCore

from app_frantoio.core.record_validation import validate_record_changes
from app_frantoio.util.time_utils import TZ
from app_frantoio.ui.calendar import configure_calendar


class EditRecordDialog(QtWidgets.QDialog):
    def __init__(self, record: Mapping[str, Any], euro_per_kg: float, parent=None):
        super().__init__(parent)
        self.original = dict(record)
        self.euro_per_kg = float(euro_per_kg)
        self._changes: dict[str, Any] = {}

        self.setWindowTitle("Modifica molitura")
        self.setMinimumWidth(460)
        self.setModal(True)

        main = QtWidgets.QVBoxLayout(self)
        main.setSpacing(16)

        title = QtWidgets.QLabel("Modifica record")
        title.setObjectName("dialogTitle")
        main.addWidget(title)

        hint = QtWidgets.QLabel("Correggi i dati e salva. L'identificativo del record non cambia.")
        hint.setWordWrap(True)
        hint.setObjectName("mutedLabel")
        main.addWidget(hint)

        form = QtWidgets.QFormLayout()
        form.setSpacing(12)

        self.name_edit = QtWidgets.QLineEdit(str(record.get("name") or record.get("nome") or ""))
        self.name_edit.setMaxLength(120)
        form.addRow("Cliente", self.name_edit)

        self.weight_edit = QtWidgets.QDoubleSpinBox()
        self.weight_edit.setDecimals(3)
        self.weight_edit.setRange(0.001, 100_000)
        self.weight_edit.setSuffix(" kg")
        self.weight_edit.setValue(float(record.get("weight") if record.get("weight") is not None else record.get("peso") or 0))
        form.addRow("Peso", self.weight_edit)

        self.discount_edit = QtWidgets.QDoubleSpinBox()
        self.discount_edit.setDecimals(2)
        self.discount_edit.setRange(0, 1_000_000)
        self.discount_edit.setPrefix("€ ")
        self.discount_edit.setValue(float(record.get("abbuono") or 0))
        form.addRow("Abbuono", self.discount_edit)

        self.payment_edit = QtWidgets.QComboBox()
        self.payment_edit.setEditable(True)
        self.payment_edit.addItems(["", "Contanti", "POS", "Assegno", "Olio"])
        current_payment = str(record.get("pagamento") or "")
        self.payment_edit.setCurrentText(current_payment)
        form.addRow("Pagamento", self.payment_edit)

        self.datetime_edit = QtWidgets.QDateTimeEdit()
        configure_calendar(self.datetime_edit)
        self.datetime_edit.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        timestamp = int(float(record.get("dataOra") or 0))
        if timestamp > 0:
            dt = datetime.fromtimestamp(timestamp / 1000, TZ)
        else:
            dt = datetime.now(TZ)
        qdate = QtCore.QDate(dt.year, dt.month, dt.day)
        qtime = QtCore.QTime(dt.hour, dt.minute, dt.second, dt.microsecond // 1000)
        self.datetime_edit.setDateTime(QtCore.QDateTime(qdate, qtime))
        form.addRow("Data e ora", self.datetime_edit)

        main.addLayout(form)

        self.summary = QtWidgets.QLabel()
        self.summary.setObjectName("editSummary")
        main.addWidget(self.summary)
        self.weight_edit.valueChanged.connect(self._update_summary)
        self.discount_edit.valueChanged.connect(self._update_summary)
        self._update_summary()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save).setText("Salva modifiche")
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)

    def _update_summary(self):
        gross = self.weight_edit.value() * self.euro_per_kg
        net = gross - self.discount_edit.value()
        self.summary.setText(f"Lordo: € {gross:,.2f}     Netto: € {net:,.2f}")

    def _validate_and_accept(self):
        qd = self.datetime_edit.date()
        qt = self.datetime_edit.time()
        local_datetime = datetime(
            qd.year(), qd.month(), qd.day(),
            qt.hour(), qt.minute(), qt.second(), qt.msec() * 1000,
            tzinfo=TZ,
        )
        proposed = {
            "name": self.name_edit.text(),
            "weight": self.weight_edit.value(),
            "abbuono": self.discount_edit.value(),
            "pagamento": self.payment_edit.currentText(),
            "dataOra": int(local_datetime.timestamp() * 1000),
        }
        try:
            self._changes = validate_record_changes(self.original, proposed)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Dati non validi", str(exc))
            return
        self.accept()

    def changed_fields(self) -> dict[str, Any]:
        return self._changes.copy()
