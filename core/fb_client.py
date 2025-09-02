from typing import Any, Dict, List
import requests

class FirebaseRestClient:
    def __init__(self, database_url: str, collection: str, get_token_callable):
        self.db_url = database_url.rstrip("/")
        self.collection = collection.strip("/")
        self._get_token = get_token_callable

    def _url(self, path=""):
        return f"{self.db_url}/{self.collection}{path}.json"

    def fetch(self) -> List[Dict[str, Any]]:
        """Legge TUTTI i record della collection."""
        params = {"auth": self._get_token()}
        r = requests.get(self._url(""), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        rows: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict):
                    row = val.copy()
                    row["id"] = key
                    rows.append(row)
        return rows

    def update_pagamento(self, push_id: str, pagamento: str):
        params = {"auth": self._get_token()}
        r = requests.patch(self._url(f"/{push_id}"), params=params,
                           json={"pagamento": pagamento}, timeout=15)
        r.raise_for_status()
        return r.json()

    def delete_many(self, ids: List[str]):
        """Cancella in batch via PATCH {id: null}."""
        if not ids:
            return
        params = {"auth": self._get_token()}
        payload = {iid: None for iid in ids}
        r = requests.patch(self._url(""), params=params, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def delete_one(self, iid: str):
        """Cancella un singolo record (equivale a delete_many con 1 id)."""
        return self.delete_many([iid])
