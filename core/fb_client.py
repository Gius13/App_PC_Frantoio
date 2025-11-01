from typing import Any, Dict, List
import requests


class FirebaseRestClient:
    def __init__(self, database_url: str, collection: str, get_token_callable):
        self.db_url = database_url.rstrip("/")
        self.collection = collection.strip("/")
        self._get_token = get_token_callable

    def _url(self, path: str = "") -> str:
        # path va passato come "" oppure "/{push_id}"
        return f"{self.db_url}/{self.collection}{path}.json"

    def fetch(self) -> List[Dict[str, Any]]:
        """Legge TUTTI i record della collection. (FIX: niente duplicati)"""
        token = self._get_token() if callable(self._get_token) else None
        params = {"auth": token} if token else {}

        r = requests.get(self._url(""), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        rows: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict):
                    row = val.copy()
                    row["id"] = key
                    # normalizza abbuono PRIMA di aggiungere la riga
                    try:
                        row["abbuono"] = float(val.get("abbuono") or 0.0)
                    except Exception:
                        row["abbuono"] = 0.0
                    rows.append(row)  # <-- UN SOLO append
        return rows

    def update_pagamento(self, push_id: str, pagamento: str):
        token = self._get_token() if callable(self._get_token) else None
        params = {"auth": token} if token else {}
        r = requests.patch(
            self._url(f"/{push_id}"),
            params=params,
            json={"pagamento": pagamento},
            timeout=15
        )
        r.raise_for_status()
        return r.json()

    def update_abbuono(self, push_id: str, abbuono: float):
        token = self._get_token() if callable(self._get_token) else None
        params = {"auth": token} if token else {}
        r = requests.patch(
            self._url(f"/{push_id}"),
            params=params,
            json={"abbuono": float(abbuono)},
            timeout=15
        )
        r.raise_for_status()
        return r.json()

    def delete_many(self, ids: List[str]):
        """Cancella in batch via PATCH {id: null}."""
        if not ids:
            return
        token = self._get_token() if callable(self._get_token) else None
        params = {"auth": token} if token else {}
        payload = {iid: None for iid in ids}
        r = requests.patch(self._url(""), params=params, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def delete_one(self, iid: str):
        """Cancella un singolo record (equivale a delete_many con 1 id)."""
        return self.delete_many([iid])
