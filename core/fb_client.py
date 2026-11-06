"""Client REST Firebase con rinnovo sessione e gestione sicura degli errori.

Tutte le operazioni usano lo stesso flusso:
- token valido prima della richiesta;
- su 401 rinnovo forzato e UN SOLO tentativo aggiuntivo;
- errori sanitizzati senza URL contenenti il parametro auth=.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

import requests


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

    def _url(self, path: str = "") -> str:
        return f"{self.db_url}/{self.collection}{path}.json"

    def _request(
        self, method: str, path: str = "",
        payload: Any = None, timeout: int = 30,
    ) -> Any:
        token = self._get_token() if callable(self._get_token) else None

        def call(token_for_request):
            params = {"auth": token_for_request} if token_for_request else {}
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

    def fetch(self) -> List[Dict[str, Any]]:
        """Legge i record della collection, senza duplicazioni."""
        data = self._request("GET", timeout=30)
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
