from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Tuple
from app_frantoio.util.time_utils import TZ, in_day
from app_frantoio.core.fb_client import FirebaseRestClient
from app_frantoio.core.sqlite_client import SQLiteClient


class HybridRepository:
    """
    Lettura operativa (lista del giorno): Firebase entro finestra ibrida, altrimenti SQLite.
    Report: SOLO SQLite (veloce e locale).
    Mirror: copia i dati da Firebase a SQLite, senza cancellazioni automatiche.
    """
    def __init__(self, firebase_client: FirebaseRestClient, sqlite_client: SQLiteClient,
                 hybrid_days: int, retention_days: int):
        self.fb = firebase_client
        self.sql = sqlite_client
        self.hybrid_days = max(0, int(hybrid_days))
        self.retention_days = max(1, int(retention_days))

    def _is_in_firebase_window(self, d: date) -> bool:
        today = datetime.now(TZ).date()
        return (today - d).days <= self.hybrid_days

    # ------------------ Lista giorno (UI principale) ------------------
    def fetch_day(self, d: date) -> List[Dict[str, Any]]:
        if self._is_in_firebase_window(d):
            rows = self.fb.fetch()
            out = []
            for r in rows:
                if in_day(r.get("dataOra"), d):
                    rr = r.copy()
                    rr["_source"] = "firebase"
                    out.append(rr)
            try:
                out.sort(key=lambda r: int(float(r.get("dataOra") or 0)))
            except Exception:
                pass
            return out
        else:
            return self.sql.fetch_day(d)

    def update_pagamento(self, rid: str, pagamento: str, source: str):
        if source == "firebase":
            return self.fb.update_pagamento(rid, pagamento)
        elif source == "sqlite":
            return self.sql.update_pagamento(rid, pagamento)
        else:
            raise ValueError("Sorgente sconosciuta per update")

    def update_abbuono(self, rid: str, abbuono: float, source: str = "sqlite"):
        if source == "firebase":
            return self.fb.update_abbuono(rid, abbuono)
        elif source == "sqlite":
            return self.sql.update_abbuono(rid, abbuono)
        else:
            raise ValueError("Sorgente sconosciuta per update")

    def delete_record(self, rid: str, source: str):
        if not rid:
            raise ValueError("ID mancante")
        if source == "firebase":
            return self.fb.delete_one(rid)
        elif source == "sqlite":
            return self.sql.delete_one(rid)
        else:
            raise ValueError(f"Sorgente sconosciuta: {source}")

    # ------------------ Mirror (senza cleanup automatico) ------------------
    def mirror_only(self) -> int:
        """
        Copia TUTTI i record da Firebase in SQLite (upsert).
        NON cancella nulla su SQLite.
        """
        fb_rows = self.fb.fetch()
        self.sql.upsert_many(fb_rows)
        return len(fb_rows)

    # ------------------ Report: SOLO SQLite (veloce) ------------------
    def report_totals_sqlite(self, d1: date, d2: date, euro_per_kg: float) -> Dict[str, Any]:
        """
        Ritorna:
        {
          "kg": float,
          "lordo": float,
          "abbuoni": float,
          "netto": float,
          "by_pagamento": { metodo: (kg, lordo) }
        }
        """
        a_ms = int(datetime(d1.year, d1.month, d1.day, 0, 0, 0, tzinfo=TZ).timestamp() * 1000)
        b_ms = int(datetime(d2.year, d2.month, d2.day, 23, 59, 59, 999000, tzinfo=TZ).timestamp() * 1000)

        # Totali globali
        kg, abbuoni = self.sql.sum_weight_abbuoni_range(a_ms, b_ms)
        kg = float(kg or 0.0)
        abbuoni = float(abbuoni or 0.0)
        lordo = kg * float(euro_per_kg)
        netto = lordo - abbuoni

        # Per metodo pagamento (GROUP BY)
        by_pay = self.sql.group_by_pagamento_range(a_ms, b_ms, euro_per_kg)

        return {
            "kg": kg,
            "lordo": lordo,
            "abbuoni": abbuoni,
            "netto": netto,
            "by_pagamento": by_pay,  # dict[str, (kg, lordo)]
        }

    def report_daily_sqlite(self, d1: date, d2: date, euro_per_kg: float) -> List[Dict[str, float]]:
        """
        Lista di righe giornaliere ordinate per data:
        [{"data":"gg/mm/aaaa","kg":...,"lordo":...,"abbuoni":...,"netto":...}, ...]
        """
        a_ms = int(datetime(d1.year, d1.month, d1.day, 0, 0, 0, tzinfo=TZ).timestamp() * 1000)
        b_ms = int(datetime(d2.year, d2.month, d2.day, 23, 59, 59, 999000, tzinfo=TZ).timestamp() * 1000)
        rows = self.sql.daily_aggregates_range(a_ms, b_ms, euro_per_kg)
        return rows

    # Compat per la ReportsPage precedente (se l'hai già usata)
    def aggregate_totals(self, d1: date, d2: date, euro_per_kg: float) -> Dict[str, Any]:
        return self.report_totals_sqlite(d1, d2, euro_per_kg)

    def aggregate_daily(self, d1: date, d2: date, euro_per_kg: float) -> List[Dict[str, float]]:
        return self.report_daily_sqlite(d1, d2, euro_per_kg)
