from __future__ import annotations
import sqlite3
from datetime import date
from typing import Any, Dict, List, Tuple
from app_frantoio.util.time_utils import day_bounds_ts_ms


def _ensure_archive_db(path: str) -> sqlite3.Connection:
    """
    - Crea il DB e la tabella moliture se non esistono.
    - Esegue migrazioni minime (aggiunta colonna abbuono).
    - Crea indici utili per i report/ricerche.
    Ritorna una connessione aperta (da chiudere).
    """
    con = sqlite3.connect(path)
    cur = con.cursor()

    # Tabella base
    cur.execute("""
        CREATE TABLE IF NOT EXISTS moliture (
            id TEXT PRIMARY KEY,
            name TEXT,
            weight REAL,
            pagamento TEXT,
            dataOra INTEGER
        )
    """)

    # Migrazione: aggiungi colonna 'abbuono' se manca
    cur.execute("PRAGMA table_info(moliture)")
    cols = [row[1] for row in cur.fetchall()]  # nome colonna = row[1]
    if "abbuono" not in cols:
        cur.execute("ALTER TABLE moliture ADD COLUMN abbuono REAL NOT NULL DEFAULT 0.0")

    # Indici per performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_moliture_dataOra ON moliture(dataOra)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_moliture_pagamento ON moliture(COALESCE(pagamento,''))")

    con.commit()
    return con


class SQLiteClient:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Garantiamo schema e indici
        _ensure_archive_db(self.db_path)

    # ---------------- Lettura giorno (UI lista) ----------------
    def fetch_day(self, d: date) -> List[Dict[str, Any]]:
        a_ms, b_ms = day_bounds_ts_ms(d)
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, weight, pagamento, dataOra, abbuono
            FROM moliture
            WHERE dataOra BETWEEN ? AND ?
            ORDER BY dataOra ASC
        """, (a_ms, b_ms))
        rows: List[Dict[str, Any]] = []
        for rid, name, weight, pagamento, dataOra, abbuono in cur.fetchall():
            rows.append({
                "id": rid,
                "name": name,
                "weight": float(weight or 0.0),
                "pagamento": pagamento or "",
                "dataOra": int(dataOra or 0),
                "abbuono": float(abbuono or 0.0),
                "_source": "sqlite",
            })
        con.close()
        return rows

    # ---------------- Aggiornamenti singolo campo ----------------
    def update_pagamento(self, rid: str, pagamento: str) -> None:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("UPDATE moliture SET pagamento=? WHERE id=?", (pagamento, rid))
        con.commit()
        con.close()

    def update_abbuono(self, rid: str, abbuono: float) -> None:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("UPDATE moliture SET abbuono=? WHERE id=?", (float(abbuono), rid))
        con.commit()
        con.close()

    # ---------------- Upsert (mirror da Firebase) ----------------
    def upsert_many(self, rows: List[Dict[str, Any]]) -> int:
        """
        Inserisce/Aggiorna molti record per id (PRIMARY KEY).
        Non cancella nulla.
        """
        if not rows:
            return 0

        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        to_ins: List[Tuple[Any, ...]] = []

        for r in rows:
            rid = r.get("id")
            if not rid:
                continue

            name = r.get("name") or r.get("nome") or ""
            try:
                weight = float(r.get("weight") or r.get("peso") or 0.0)
            except Exception:
                weight = 0.0
            pagamento = (r.get("pagamento") or "").strip()
            try:
                dataOra = int(float(r.get("dataOra") or 0))
            except Exception:
                dataOra = 0
            try:
                abbuono = float(r.get("abbuono") or 0.0)
            except Exception:
                abbuono = 0.0

            to_ins.append((rid, name, weight, pagamento, dataOra, abbuono))

        cur.executemany("""
            INSERT INTO moliture (id, name, weight, pagamento, dataOra, abbuono)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name      = excluded.name,
                weight    = excluded.weight,
                pagamento = excluded.pagamento,
                dataOra   = excluded.dataOra,
                abbuono   = excluded.abbuono
        """, to_ins)

        con.commit()
        affected = cur.rowcount  # numero righe toccate nell'ultimo statement
        con.close()
        return affected

    # ---------------- Cancellazione esplicita (da UI) ----------------
    def delete_one(self, rid: str) -> None:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("DELETE FROM moliture WHERE id=?", (rid,))
        con.commit()
        con.close()

    # ---------------- API per report veloci (solo SQLite) ----------------
    def sum_weight_abbuoni_range(self, a_ms: int, b_ms: int) -> Tuple[float, float]:
        """
        Ritorna (kg_totali, abbuoni_totali) nel range [a_ms, b_ms].
        """
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(weight),0), COALESCE(SUM(abbuono),0)
            FROM moliture
            WHERE dataOra BETWEEN ? AND ?
        """, (a_ms, b_ms))
        kg, abbuoni = cur.fetchone() or (0.0, 0.0)
        con.close()
        return float(kg or 0.0), float(abbuoni or 0.0)

    def group_by_pagamento_range(self, a_ms: int, b_ms: int, euro_per_kg: float) -> Dict[str, Tuple[float, float]]:
        """
        Ritorna un dict: { metodo_pagamento: (kg_totali, lordo = kg*euro_per_kg) }
        Metodo vuoto è restituito come '' (la UI mostrerà 'Da Saldare').
        """
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("""
            SELECT COALESCE(pagamento,''), COALESCE(SUM(weight),0)
            FROM moliture
            WHERE dataOra BETWEEN ? AND ?
            GROUP BY COALESCE(pagamento,'')
            ORDER BY 1
        """, (a_ms, b_ms))
        by: Dict[str, Tuple[float, float]] = {}
        for pagamento, kg in cur.fetchall() or []:
            kgf = float(kg or 0.0)
            lordo = kgf * float(euro_per_kg)
            by[str(pagamento or "")] = (kgf, lordo)
        con.close()
        return by

    def daily_aggregates_range(self, a_ms: int, b_ms: int, euro_per_kg: float) -> List[Dict[str, float]]:
        """
        Ritorna una lista di dict giornalieri ordinati per data:
        [{'data':'gg/mm/aaaa','kg':..., 'lordo':..., 'abbuoni':..., 'netto':...}, ...]
        """
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        # dataOra è in millisecondi; convertiamo a datetime locale e poi estraiamo 'date(...)'
        cur.execute("""
            SELECT
                date(datetime(dataOra/1000,'unixepoch','localtime')) AS d,
                COALESCE(SUM(weight),0) AS kg,
                COALESCE(SUM(abbuono),0) AS abb
            FROM moliture
            WHERE dataOra BETWEEN ? AND ?
            GROUP BY d
            ORDER BY d ASC
        """, (a_ms, b_ms))
        out: List[Dict[str, float]] = []
        for dstr, kg, abb in cur.fetchall() or []:
            kgf = float(kg or 0.0)
            abbf = float(abb or 0.0)
            lordo = kgf * float(euro_per_kg)
            netto = lordo - abbf
            # format gg/mm/aaaa
            y, m, d = dstr.split("-")
            out.append({
                "data": f"{d}/{m}/{y}",
                "kg": kgf,
                "lordo": lordo,
                "abbuoni": abbf,
                "netto": netto,
            })
        con.close()
        return out
