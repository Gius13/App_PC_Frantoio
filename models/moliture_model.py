from typing import Any, Dict, List
from PyQt6 import QtCore
from app_frantoio.util.time_utils import fmt_ts

COLS = ["Nome", "Peso (kg)", "Prezzo (€)", "Ora", "Pagamento"]

class MolitureModel(QtCore.QAbstractTableModel):
    def __init__(self, rows: List[Dict[str, Any]], euro_per_kg: float, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._euro = euro_per_kg

    def set_rows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(COLS)

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return COLS[section]
            return section + 1
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return int(QtCore.Qt.AlignmentFlag.AlignCenter)
        return None

    def data(self, index, role):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        c = index.column()

        name = r.get("name") or r.get("nome") or ""
        weight = r.get("weight") or r.get("peso") or 0
        try:
            weight_f = float(weight)
        except Exception:
            weight_f = 0.0
        prezzo = weight_f * self._euro
        ts = r.get("dataOra")
        pagamento = r.get("pagamento") or ""

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if c == 0: return str(name)
            if c == 1: return f"{weight_f:.2f}"
            if c == 2: return f"{prezzo:.2f}"
            if c == 3: return fmt_ts(ts)
            if c == 4: return pagamento

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return int(QtCore.Qt.AlignmentFlag.AlignCenter)

        return None

    def flags(self, index):
        base = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.column() == 4:
            base |= QtCore.Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index, value, role):
        if role == QtCore.Qt.ItemDataRole.EditRole and index.column() == 4:
            self._rows[index.row()]["pagamento"] = str(value)
            self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DisplayRole])
            return True
        return False

    def row_at(self, row: int):
        return self._rows[row]

    def all_rows(self):
        return self._rows
