from typing import Any, Dict, List
from PyQt6 import QtCore
from app_frantoio.util.time_utils import fmt_ts

# 0=Nome, 1=Peso, 2=Prezzo (lordo), 3=Abbuono, 4=Ora, 5=Pagamento
COLS = ["Nome", "Peso (kg)", "Prezzo (€)", "Abbuono (€)", "Ora", "Pagamento"]


class MolitureModel(QtCore.QAbstractTableModel):
    def __init__(self, rows: List[Dict[str, Any]], euro_per_kg: float, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = rows or []
        try:
            self._euro = float(euro_per_kg)
        except Exception:
            self._euro = 0.0

    # ---- API per aggiornare i dati ----
    def set_rows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows or []
        self.endResetModel()

    def row_at(self, row: int) -> Dict[str, Any]:
        return self._rows[row]

    def all_rows(self) -> List[Dict[str, Any]]:
        return self._rows

    # ---- Qt Model basics ----
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

        try:
            abbuono_f = float(r.get("abbuono") or 0.0)
        except Exception:
            abbuono_f = 0.0

        ts = r.get("dataOra")
        pagamento = r.get("pagamento") or ""

        # Per l'editor (EditRole) restituiamo valori "grezzi" non formattati
        if role == QtCore.Qt.ItemDataRole.EditRole:
            if c == 0: return name
            if c == 1: return weight_f
            if c == 2: return prezzo
            if c == 3: return abbuono_f   # <-- importante: il float reale, non "0.00"
            if c == 4: return fmt_ts(ts)  # non editabile, ma non fa danni
            if c == 5: return pagamento

        # Per la visualizzazione (DisplayRole) restituiamo testo formattato
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if c == 0: return str(name)
            if c == 1: return f"{weight_f:.2f}"
            if c == 2: return f"{prezzo:.2f}"
            if c == 3: return f"{abbuono_f:.2f}"
            if c == 4: return fmt_ts(ts)
            if c == 5: return pagamento

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return int(QtCore.Qt.AlignmentFlag.AlignCenter)

        return None

    def flags(self, index):
        base = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        # Editabili: Abbuono (3) e Pagamento (5)
        if index.column() in (3, 5):
            base |= QtCore.Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index, value, role):
        if not index.isValid() or role != QtCore.Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()

        # Pagamento (colonna 5)
        if col == 5:
            new_val = str(value)
            if self._rows[row].get("pagamento") == new_val:
                return True
            self._rows[row]["pagamento"] = new_val
            self.dataChanged.emit(index, index, [
                QtCore.Qt.ItemDataRole.DisplayRole,
                QtCore.Qt.ItemDataRole.EditRole
            ])
            return True

        # Abbuono (colonna 3)
        if col == 3:
            try:
                txt = str(value).strip().replace(",", ".")
                v = float(txt) if txt else 0.0
                if v < 0:
                    v = 0.0
            except Exception:
                v = 0.0

            if float(self._rows[row].get("abbuono", 0.0)) == v:
                return True

            self._rows[row]["abbuono"] = v
            self.dataChanged.emit(index, index, [
                QtCore.Qt.ItemDataRole.DisplayRole,
                QtCore.Qt.ItemDataRole.EditRole
            ])
            return True

        return False
