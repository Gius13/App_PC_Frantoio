"""Client REST Firebase con rinnovo sessione e gestione sicura degli errori.

Tutte le operazioni usano lo stesso flusso:
- token valido prima della richiesta;
- su 401 rinnovo forzato e UN SOLO tentativo aggiuntivo;
- errori sanitizzati senza URL contenenti il parametro auth=.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List
import json

import requests
import threading


class FirebaseRequestError(RuntimeError):
    """Errore Firebase che non rivela ID token o URL autenticati."""


class FirebaseRestClient:
    def __init__(
        self, database_url: str, collection: str,
        get_token_callable: Callable[[], str],
        refresh_token_callable: Callable[[str], str] | None = None,
    ):
        self.db_url = database_url.rstrip("/")
        self.collection = collection.strip("/")
        self._get_token = get_token_callable
        self._refresh_token = refresh_token_callable
        self._range_support = None  # None=non verificato; False=fallback legacy
        self._range_lock = threading.RLock()

    def _url(self, path: str = "") -> str:
        return f"{self.db_url}/{self.collection}{path}.json"

    def _request(
        self, method: str, path: str = "",
        payload: Any = None, timeout: int = 30,
        query: Dict[str, Any] | None = None,
    ) -> Any:
        token = self._get_token() if callable(self._get_token) else None

        def call(token_for_request):
            params = dict(query or {})
            if token_for_request:
                params["auth"] = token_for_request
            try:
                return requests.request(
                    method, self._url(path), params=params,
                    json=payload if method in ("PATCH", "POST", "PUT") else None,
                    timeout=timeout,
                )
            except requests.RequestException:
                # Le eccezioni requests possono contenere l'URL con auth=<token>.
                raise FirebaseRequestError(
                    "Connessione a Firebase non riuscita. Controlla la rete e riprova."
                ) from None

        response = call(token)
        if response.status_code == 401 and callable(self._refresh_token):
            # Il token potrebbe essere scaduto durante l'invio, oppure un
            # altro thread potrebbe aver già eseguito il refresh.
            token = self._refresh_token(token)
            if not token:
                raise FirebaseRequestError(
                    "Sessione Firebase non disponibile. Esegui di nuovo l'accesso."
                )
            response = call(token)

        if response.status_code == 401:
            raise FirebaseRequestError(
                "Firebase non autorizza l'operazione (HTTP 401). "
                "Se la sessione è valida, verifica le regole di accesso al database."
            )
        if response.status_code == 403:
            raise FirebaseRequestError(
                "Accesso negato da Firebase (HTTP 403). "
                "Verifica le autorizzazioni dell'account."
            )
        if response.status_code >= 400:
            raise FirebaseRequestError(
                f"Firebase ha restituito HTTP {response.status_code}. "
                "Riprova o verifica la connessione e le impostazioni del servizio."
            )
        try:
            return response.json()
        except (ValueError, TypeError):
            raise FirebaseRequestError("Risposta non valida ricevuta da Firebase.") from None

    @staticmethod
    def _rows_from_payload(data: Any) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict):
                    row = val.copy()
                    row["id"] = key
                    try:
                        row["abbuono"] = float(val.get("abbuono") or 0.0)
                    except (ValueError, TypeError):
                        row["abbuono"] = 0.0
                    rows.append(row)
        return rows

    def fetch(self) -> List[Dict[str, Any]]:
        """Mirror completo; non usato nel polling del giorno."""
        return self._rows_from_payload(self._request("GET", timeout=30))

    def fetch_range(self, start_ms: int, end_exclusive_ms: int) -> List[Dict[str, Any]]:
        """Scarica solo il periodo richiesto, se l'indice Firebase è abilitato.

        Per attivare la query rapida sulle Realtime Database Rules:
        "molitura": { ".indexOn": ["dataOra"] }
        Se l'indice manca (HTTP 400), mantiene il comportamento precedente
        con filtraggio locale, senza bloccare la visualizzazione.
        """
        if self._range_support is False:
            return self._legacy_range(start_ms, end_exclusive_ms)

        query = {
            "orderBy": json.dumps("dataOra"),
            "startAt": int(start_ms),
            "endAt": int(end_exclusive_ms) - 1,
        }
        try:
            data = self._request("GET", query=query, timeout=15)
        except FirebaseRequestError as exc:
            if "HTTP 400" not in str(exc):
                raise
            with self._range_lock:
                self._range_support = False
            return self._legacy_range(start_ms, end_exclusive_ms)

        self._range_support = True
        return [
            r for r in self._rows_from_payload(data)
            if start_ms <= self._timestamp_ms(r) < end_exclusive_ms
        ]

    @staticmethod
    def _timestamp_ms(row: Dict[str, Any]) -> int:
        try:
            return int(float(row.get("dataOra") or 0))
        except (ValueError, OverflowError, TypeError):
            return -1

    def _legacy_range(self, start_ms: int, end_exclusive_ms: int) -> List[Dict[str, Any]]:
        return [
            r for r in self.fetch()
            if start_ms <= self._timestamp_ms(r) < end_exclusive_ms
        ]

    def update_fields(self, push_id: str, changes: Dict[str, Any]):
        """PATCH parziale: mantiene gli altri campi del record."""
        if not push_id or not changes:
            raise ValueError("ID o modifiche mancanti.")
        return self._request("PATCH", f"/{push_id}", changes, timeout=15)

    def update_pagamento(self, push_id: str, pagamento: str):
        return self.update_fields(push_id, {"pagamento": pagamento})

    def update_abbuono(self, push_id: str, abbuono: float):
        return self.update_fields(push_id, {"abbuono": float(abbuono)})

    def delete_many(self, ids: List[str]):
        """Cancellazione mediante PATCH {id: null}."""
        if not ids:
            return None
        return self._request(
            "PATCH", payload={iid: None for iid in ids}, timeout=30
        )

    def delete_one(self, iid: str):
        return self.delete_many([iid])
