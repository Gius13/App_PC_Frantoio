"""Filtri locali per la lista moliture, combinabili tra loro.

Il modello sorgente non viene alterato. Tutte le ricerche testuali e
numeriche avvengono sui record già caricati per il periodo selezionato.
"""
from __future__ import annotations

from PyQt6 import QtCore


class MolitureFilterProxy(QtCore.QSortFilterProxyModel):
    OTHER_METHODS = frozenset({"Contanti", "POS", "Assegno", "Olio"})

    def __init__(self, parent=None):
        super().__init__(parent)
        self._query = ""
        self._payment = ""
        self._min_weight = 0.0
        self._max_weight = 0.0
        self.setSortRole(QtCore.Qt.ItemDataRole.UserRole)
        self.setDynamicSortFilter(True)

    def set_search_text(self, value: str):
        value = (value or "").strip().casefold()
        if value != self._query:
            self._query = value
            self.invalidateFilter()

    def set_payment(self, value: str):
        value = value or ""
        if value != self._payment:
            self._payment = value
            self.invalidateFilter()

    def set_weight_bounds(self, minimum: float = 0, maximum: float = 0):
        lo, hi = max(0, float(minimum)), max(0, float(maximum))
        if (lo, hi) != (self._min_weight, self._max_weight):
            self._min_weight, self._max_weight = lo, hi
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        record = model.row_at(source_row)
        payment = str(record.get("pagamento") or "").strip()
        wanted = self._payment
        if wanted == "__unpaid__":
            if payment:
                return False
        elif wanted == "__other__":
            if not payment or payment in self.OTHER_METHODS:
                return False
        elif wanted and payment != wanted:
            return False

        try:
            weight = float(record.get("weight") if record.get("weight") is not None else record.get("peso") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        if self._min_weight > 0 and weight < self._min_weight:
            return False
        if self._max_weight > 0 and weight > self._max_weight:
            return False

        if self._query:
            # Nome, peso, prezzo, abbuono, data e metodo pagamento.
            fields = (
                str(model.data(model.index(source_row, column), QtCore.Qt.ItemDataRole.DisplayRole) or "")
                for column in range(model.columnCount())
            )
            return self._query in " ".join(fields).casefold()
        return True
