from datetime import datetime, timedelta, date
from typing import Any, Dict, List
from app_frantoio.util.time_utils import TZ, in_day
from app_frantoio.core.fb_client import FirebaseRestClient 
from app_frantoio.core.sqlite_client import SQLiteClient

class HybridRepository:
    """Legge: Firebase (ultimi N giorni) o SQLite (storico).
       Sync periodico: duplica tutto da Firebase -> SQLite e ripulisce Firebase > retention."""
    def __init__(self, firebase_client: FirebaseRestClient, sqlite_client: SQLiteClient,
                 hybrid_days: int, retention_days: int):
        self.fb = firebase_client
        self.sql = sqlite_client
        self.hybrid_days = max(0, int(hybrid_days))
        self.retention_days = max(1, int(retention_days))

    def _is_in_firebase_window(self, d: date) -> bool:
        today = datetime.now(TZ).date()
        return (today - d).days <= self.hybrid_days

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

    def mirror_and_cleanup(self) -> Dict[str, int]:
        """Duplica TUTTI i record da Firebase a SQLite e cancella quelli più vecchi di retention_days su Firebase."""
        fb_rows = self.fb.fetch()
        self.sql.upsert_many(fb_rows)

        cutoff_date = datetime.now(TZ).date() - timedelta(days=self.retention_days)
        cutoff_ms = int(datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day, 23, 59, 59, 999000, tzinfo=TZ).timestamp() * 1000)

        to_delete = []
        for r in fb_rows:
            try:
                ts = int(float(r.get("dataOra") or 0))
            except Exception:
                ts = 0
            if ts and ts <= cutoff_ms:
                rid = r.get("id")
                if rid:
                    to_delete.append(rid)

        if to_delete:
            self.fb.delete_many(to_delete)

        return {"mirrored": len(fb_rows), "deleted": len(to_delete)}

    def delete_record(self, rid: str, source: str):
        """Cancella un record dalla sua sorgente."""
        if not rid:
            raise ValueError("ID mancante")
        if source == "firebase":
            return self.fb.delete_one(rid)
        elif source == "sqlite":
            return self.sql.delete_one(rid)
        else:
            raise ValueError(f"Sorgente sconosciuta: {source}")
