import sqlite3
from datetime import date
from typing import Any, Dict, List
from app_frantoio.util.time_utils import day_bounds_ts_ms

def _ensure_archive_db(path: str):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS moliture (
            id TEXT PRIMARY KEY,
            name TEXT,
            weight REAL,
            pagamento TEXT,
            dataOra INTEGER
        )
    """)
    con.commit()
    return con

class SQLiteClient:
    def __init__(self, db_path: str):
        self.db_path = db_path
        _ensure_archive_db(self.db_path)

    def fetch_day(self, d: date):
        a_ms, b_ms = day_bounds_ts_ms(d)
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, weight, pagamento, dataOra
            FROM moliture
            WHERE dataOra BETWEEN ? AND ?
            ORDER BY dataOra ASC
        """, (a_ms, b_ms))
        rows = []
        for rid, name, weight, pagamento, dataOra in cur.fetchall():
            rows.append({
                "id": rid, "name": name, "weight": weight,
                "pagamento": pagamento, "dataOra": dataOra,
                "_source": "sqlite"
            })
        con.close()
        return rows

    def update_pagamento(self, rid: str, pagamento: str):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("UPDATE moliture SET pagamento=? WHERE id=?", (pagamento, rid))
        con.commit()
        con.close()

    def upsert_many(self, rows: List[Dict[str, Any]]):
        """Inserisce o aggiorna molti record (id unique)."""
        if not rows:
            return 0
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        to_ins = []
        for r in rows:
            rid = r.get("id")
            if not rid:
                continue
            name = r.get("name") or r.get("nome") or ""
            try:
                weight = float(r.get("weight") or r.get("peso") or 0)
            except Exception:
                weight = 0.0
            pagamento = r.get("pagamento") or ""
            try:
                dataOra = int(float(r.get("dataOra") or 0))
            except Exception:
                dataOra = 0
            to_ins.append((rid, name, weight, pagamento, dataOra))
        cur.executemany("""
            INSERT INTO moliture(id,name,weight,pagamento,dataOra)
            VALUES (?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                weight=excluded.weight,
                pagamento=excluded.pagamento,
                dataOra=excluded.dataOra
        """, to_ins)
        con.commit()
        affected = cur.rowcount
        con.close()
        return affected

    def delete_one(self, rid: str):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("DELETE FROM moliture WHERE id=?", (rid,))
        con.commit()
        con.close()
