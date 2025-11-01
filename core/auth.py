from typing import Optional
import requests

class AuthClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.id_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.local_id: Optional[str] = None

    def sign_in_password(self, email: str, password: str):
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.api_key}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        self.id_token = data["idToken"]
        self.refresh_token = data.get("refreshToken")
        self.local_id = data.get("localId")
        return data
