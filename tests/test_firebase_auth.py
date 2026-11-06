"""Test autenticazione Firebase: scadenza, concorrenza, retry HTTP 401 e privacy.

Non effettua richieste di rete e non richiede credenziali reali.
"""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest
from unittest.mock import patch

import requests

from app_frantoio.core.auth import AuthClient, AuthenticationError
from app_frantoio.core.fb_client import FirebaseRestClient, FirebaseRequestError


class FakeResponse:
    def __init__(self, code, payload=None):
        self.status_code = code
        self._payload = {} if payload is None else payload

    def json(self):
        return self._payload


def login_response(expires="3600"):
    return FakeResponse(200, {
        "idToken": "test-initial-token",
        "refreshToken": "test-refresh-secret",
        "localId": "test-user",
        "expiresIn": expires,
    })


def refresh_response():
    return FakeResponse(200, {
        "id_token": "test-renewed-token",
        "refresh_token": "test-new-refresh-secret",
        "user_id": "test-user",
        "expires_in": "3600",
    })


class AuthTokenTests(unittest.TestCase):
    def setUp(self):
        self.auth = AuthClient("test-api-key")

    @patch("app_frantoio.core.auth.requests.post")
    def test_uses_existing_token_before_expiry(self, post):
        post.return_value = login_response()
        self.auth.sign_in_password("example@example.org", "password")
        self.assertEqual(self.auth.get_valid_token(), "test-initial-token")
        self.assertEqual(post.call_count, 1)

    @patch("app_frantoio.core.auth.requests.post")
    def test_renews_automatically_before_expiry(self, post):
        post.side_effect = [login_response(expires="30"), refresh_response()]
        self.auth.sign_in_password("example@example.org", "password")
        self.assertEqual(self.auth.get_valid_token(), "test-renewed-token")
        self.assertEqual(self.auth.refresh_token, "test-new-refresh-secret")
        self.assertEqual(post.call_count, 2)
        self.assertIn("securetoken.googleapis.com", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["data"]["grant_type"], "refresh_token")

    @patch("app_frantoio.core.auth.requests.post")
    def test_refresh_is_thread_safe(self, post):
        post.side_effect = [login_response(), refresh_response()]
        self.auth.sign_in_password("example@example.org", "password")
        self.auth._expires_at = time.monotonic() - 1

        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens = list(pool.map(lambda _: self.auth.get_valid_token(), range(16)))

        self.assertEqual(tokens, ["test-renewed-token"] * 16)
        self.assertEqual(post.call_count, 2)

    @patch("app_frantoio.core.auth.requests.post")
    def test_stale_401_does_not_force_second_refresh(self, post):
        post.side_effect = [login_response(), refresh_response()]
        self.auth.sign_in_password("example@example.org", "password")
        self.assertEqual(
            self.auth.refresh_access_token("test-initial-token"),
            "test-renewed-token",
        )
        self.assertEqual(
            self.auth.refresh_access_token("test-initial-token"),
            "test-renewed-token",
        )
        self.assertEqual(post.call_count, 2)

    @patch("app_frantoio.core.auth.requests.post")
    def test_invalid_refresh_requires_new_login_without_leaking_secret(self, post):
        post.side_effect = [login_response(expires="5"), FakeResponse(400, {})]
        self.auth.sign_in_password("example@example.org", "password")
        with self.assertRaises(AuthenticationError) as caught:
            self.auth.get_valid_token()
        message = str(caught.exception)
        self.assertIn("Riavvia", message)
        self.assertNotIn("test-refresh-secret", message)
        self.assertNotIn("securetoken.googleapis.com", message)

    @patch("app_frantoio.core.auth.requests.post")
    def test_network_failure_has_no_credential_in_error(self, post):
        post.side_effect = requests.ConnectionError(
            "https://securetoken.googleapis.com/v1/token?key=test-api-key"
        )
        with self.assertRaises(AuthenticationError) as caught:
            self.auth.sign_in_password("example@example.org", "test-password")
        message = str(caught.exception)
        self.assertNotIn("test-password", message)
        self.assertNotIn("test-api-key", message)


class FirebaseRetryTests(unittest.TestCase):
    def make_client(self, token_getter=None, refresh=None):
        return FirebaseRestClient(
            "https://sample-default-rtdb.firebaseio.com", "molitura",
            get_token_callable=token_getter or (lambda: "test-initial-token"),
            refresh_token_callable=refresh,
        )

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_indexed_range_request_fetches_only_dates(self, request):
        start = 1793894400000
        end = start + 86400000
        request.return_value = FakeResponse(200, {
            "wanted": {"dataOra": start + 1000, "name": "Mario"},
        })
        client = self.make_client()
        result = client.fetch_range(start, end)
        self.assertEqual([r["id"] for r in result], ["wanted"])
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["params"]["orderBy"], '"dataOra"')
        self.assertEqual(request.call_args.kwargs["params"]["startAt"], start)
        self.assertEqual(request.call_args.kwargs["params"]["endAt"], end - 1)

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_unindexed_database_fallback_is_remembered(self, request):
        start = 1793894400000
        end = start + 86400000
        payload = {"wanted": {"dataOra": start + 1000, "name": "Mario"},
                   "outside": {"dataOra": end + 1000, "name": "Luigi"}}
        request.side_effect = [
            FakeResponse(400, {"error": "Index not defined"}),
            FakeResponse(200, payload),
            FakeResponse(200, payload)
        ]
        client = self.make_client()
        self.assertEqual(
            [r["id"] for r in client.fetch_range(start, end)], ["wanted"]
        )
        self.assertFalse(client._range_support)
        self.assertEqual(
            [r["id"] for r in client.fetch_range(start, end)], ["wanted"]
        )
        self.assertEqual(request.call_count, 3)
        self.assertNotIn("orderBy", request.call_args.kwargs["params"])

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_get_retries_once_after_401(self, request):
        request.side_effect = [
            FakeResponse(401, {"error": "unauthorized"}),
            FakeResponse(200, {"id-one": {"name": "Mario", "weight": 110}}),
        ]
        history = []
        def refresh(previous):
            history.append(previous)
            return "test-renewed-token"

        client = self.make_client(refresh=refresh)
        rows = client.fetch()
        self.assertEqual(history, ["test-initial-token"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "id-one")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            request.call_args_list[0].kwargs["params"]["auth"], "test-initial-token"
        )
        self.assertEqual(
            request.call_args_list[1].kwargs["params"]["auth"], "test-renewed-token"
        )

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_patch_and_delete_use_same_renewable_transport(self, request):
        request.side_effect = [
            FakeResponse(401), FakeResponse(200, {"pagamento": "POS"}),
            FakeResponse(401), FakeResponse(200, {"id-one": None}),
        ]
        refresh_calls = []
        def refresh(previous):
            refresh_calls.append(previous)
            return "test-renewed-token"

        client = self.make_client(refresh=refresh)
        client.update_pagamento("id-one", "POS")
        client.delete_one("id-one")
        self.assertEqual(request.call_count, 4)
        self.assertEqual(len(refresh_calls), 2)
        self.assertEqual(request.call_args_list[1].kwargs["json"], {"pagamento": "POS"})
        self.assertEqual(request.call_args_list[3].kwargs["json"], {"id-one": None})

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_permission_denied_even_after_refresh_is_reported_without_token(self, request):
        request.side_effect = [FakeResponse(401), FakeResponse(401)]
        client = self.make_client(refresh=lambda old: "test-renewed-token")
        with self.assertRaises(FirebaseRequestError) as caught:
            client.fetch()
        self.assertEqual(request.call_count, 2)
        message = str(caught.exception)
        self.assertIn("regole", message)
        self.assertNotIn("test-renewed-token", message)
        self.assertNotIn("auth=", message)

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_denied_403_does_not_refresh(self, request):
        request.return_value = FakeResponse(403)
        refreshed = []
        client = self.make_client(refresh=lambda old: refreshed.append(old))
        with self.assertRaises(FirebaseRequestError):
            client.fetch()
        self.assertEqual(refreshed, [])
        self.assertEqual(request.call_count, 1)

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_request_exception_does_not_expose_authenticated_url(self, request):
        request.side_effect = requests.ConnectionError(
            "https://sample.firebaseio.com/molitura.json?auth=test-initial-token"
        )
        client = self.make_client()
        with self.assertRaises(FirebaseRequestError) as caught:
            client.fetch()
        self.assertNotIn("test-initial-token", str(caught.exception))
        self.assertNotIn("auth=", str(caught.exception))

    @patch("app_frantoio.core.fb_client.requests.request")
    def test_ordinary_success_needs_no_refresh(self, request):
        request.return_value = FakeResponse(200, {})
        refresh_calls = []
        client = self.make_client(refresh=lambda old: refresh_calls.append(old))
        self.assertEqual(client.fetch(), [])
        self.assertEqual(request.call_count, 1)
        self.assertEqual(refresh_calls, [])


if __name__ == "__main__":
    unittest.main()
