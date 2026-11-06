"""Autenticazione Firebase con rinnovo sicuro e automatico dell'ID token.

I token non sono mai scritti su disco né inclusi nei messaggi d'errore.
Le chiamate al refresh sono serializzate per i worker Qt concorrenti.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import requests


class AuthenticationError(RuntimeError):
    """Errore di autenticazione senza credenziali o token nei dettagli."""


class AuthClient:
    # Rinnova prima che il token scada, evitando che il polling perda accesso.
    REFRESH_MARGIN_SECONDS = 60

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.id_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.local_id: Optional[str] = None
        self._expires_at = 0.0  # monotonic seconds
        self._lock = threading.RLock()

    def sign_in_password(self, email: str, password: str):
        """Accede senza salvare la password o propagare URL con credenziali."""
        url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        try:
            response = requests.post(
                url, params={"key": self.api_key}, json=payload, timeout=15,
            )
            if response.status_code >= 400:
                raise AuthenticationError(
                    "Accesso Firebase non riuscito. Controlla email, password e permessi."
                )
            data = response.json()
        except requests.RequestException:
            raise AuthenticationError(
                "Impossibile collegarsi a Firebase Authentication. Controlla la connessione."
            ) from None
        except (ValueError, TypeError):
            raise AuthenticationError("Risposta inattesa dal servizio di autenticazione.") from None

        if not isinstance(data, dict) or not data.get("idToken") or not data.get("refreshToken"):
            raise AuthenticationError("Firebase non ha restituito una sessione valida.")

        with self._lock:
            self.id_token = data["idToken"]
            self.refresh_token = data["refreshToken"]
            self.local_id = data.get("localId")
            try:
                lifetime = max(0, int(data.get("expiresIn", 3600)))
            except (ValueError, TypeError):
                lifetime = 3600
            self._expires_at = time.monotonic() + lifetime
        return data

    def _refresh_locked(self) -> str:
        """Da chiamare soltanto con self._lock acquisito."""
        if not self.refresh_token:
            raise AuthenticationError(
                "Sessione Firebase non disponibile. Riavvia l'app ed esegui l'accesso."
            )

        try:
            response = requests.post(
                "https://securetoken.googleapis.com/v1/token",
                params={"key": self.api_key},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                timeout=15,
            )
            if response.status_code >= 400:
                raise AuthenticationError(
                    "Sessione Firebase scaduta o revocata. "
                    "Riavvia l'app ed esegui nuovamente l'accesso."
                )
            data = response.json()
        except requests.RequestException:
            raise AuthenticationError(
                "Impossibile rinnovare la sessione Firebase. "
                "Controlla la connessione e riprova."
            ) from None
        except (ValueError, TypeError):
            raise AuthenticationError("Risposta inattesa durante il rinnovo della sessione.") from None

        if not isinstance(data, dict) or not data.get("id_token") or not data.get("refresh_token"):
            raise AuthenticationError(
                "Sessione Firebase non rinnovabile. Riavvia l'app ed esegui l'accesso."
            )

        self.id_token = data["id_token"]
        self.refresh_token = data["refresh_token"]
        self.local_id = data.get("user_id") or self.local_id
        try:
            lifetime = max(0, int(data.get("expires_in", 3600)))
        except (ValueError, TypeError):
            lifetime = 3600
        self._expires_at = time.monotonic() + lifetime
        return self.id_token

    def get_valid_token(self) -> str:
        """Rinnova prima della scadenza, anche con più richieste concorrenti."""
        with self._lock:
            if (
                self.id_token
                and time.monotonic() < self._expires_at - self.REFRESH_MARGIN_SECONDS
            ):
                return self.id_token
            return self._refresh_locked()

    def refresh_access_token(self, previous_token: str | None = None) -> str:
        """Forza un rinnovo dopo HTTP 401, evitando refresh duplicati.

        Un altro worker può aver già aggiornato la sessione nel frattempo.
        """
        with self._lock:
            if (
                previous_token
                and self.id_token
                and self.id_token != previous_token
                and time.monotonic() < self._expires_at - self.REFRESH_MARGIN_SECONDS
            ):
                return self.id_token
            return self._refresh_locked()
