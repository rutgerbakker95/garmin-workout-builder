"""Exercise the HTTP MCP boundary, OAuth verification and stateless downloads."""

import json
import logging
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt

from server import create_app, DOWNLOAD_TTL, OAuthVerifier

ROOT = Path(__file__).resolve().parents[1]


class McpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpx2").setLevel(logging.WARNING)
        self.settings = {
            "PUBLIC_BASE_URL": "https://workout.example",
            "DOWNLOAD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "OAUTH_ISSUER": "https://identity.example/",
            "OAUTH_JWKS_URL": "https://identity.example/jwks",
            "OAUTH_AUDIENCE": "https://workout.example/mcp",
            "OAUTH_ALLOWED_SUBJECT": "owner",
        }
        self.workout = json.loads((ROOT / "tests/fixtures/reference-3x10-workout.json").read_text())
        self.verifier = OAuthVerifier(self.settings)
        self.signing_key = patch.object(self.verifier.jwks, "get_signing_key_from_jwt", return_value=SimpleNamespace(key=self.key.public_key()))
        self.signing_key.start()
        self.addCleanup(self.signing_key.stop)
        self.client = self.enterContext(TestClient(create_app(self.settings, token_verifier=self.verifier), base_url=self.settings["PUBLIC_BASE_URL"]))

    def token(self, **overrides):
        claims = {"iss": self.settings["OAUTH_ISSUER"], "aud": self.settings["OAUTH_AUDIENCE"], "sub": "owner", "exp": int(time.time()) + 300, "scope": "workouts:export", "client_id": "chatgpt"}
        claims.update(overrides)
        return jwt.encode(claims, self.key, algorithm="RS256")

    def rpc(self, method, params=None, token=None):
        return self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}, headers={"Authorization": "Bearer " + (token or self.token()), "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"})

    def export(self):
        response = self.rpc("tools/call", {"name": "create_workout", "arguments": {"workout": self.workout}})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertFalse(result.get("isError"), result)
        return result["structuredContent"]

    def test_initialize_and_discover_tools(self):
        response = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("tools", response.json()["result"]["capabilities"])
        tools = self.rpc("tools/list").json()["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, {"get_workout_contract", "create_workout"})
        self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in tools))
        result = self.rpc("tools/call", {"name": "get_workout_contract", "arguments": {}}).json()["result"]
        self.assertIn("schema_version", result["content"][0]["text"])

    def test_export_download_survives_new_server_instance(self):
        result = self.export()
        self.assertEqual(result["duration_seconds"], 5400)
        with TestClient(create_app(self.settings), base_url=self.settings["PUBLIC_BASE_URL"]) as other:
            download = other.get(result["download_url"])
        self.assertEqual(download.status_code, 200, download.text)
        self.assertEqual(download.json()["workoutName"], "3x10 donderdag")
        self.assertEqual(download.json()["estimatedDurationInSecs"], 5400)
        self.assertEqual(download.json()["author"]["fullName"], "Reference")
        self.assertEqual(download.json()["ownerId"], 200000001)
        self.assertEqual(download.headers["cache-control"], "private, no-store")
        self.assertIn("attachment", download.headers["content-disposition"])

    def test_oauth_discovery_and_missing_token(self):
        response = self.client.post("/mcp", json={})
        self.assertEqual(response.status_code, 401)
        self.assertIn("resource_metadata", response.headers["www-authenticate"])
        metadata = self.client.get("/.well-known/oauth-protected-resource/mcp").json()
        self.assertEqual(metadata["resource"], self.settings["PUBLIC_BASE_URL"] + "/mcp")
        self.assertEqual(metadata["authorization_servers"], [self.settings["OAUTH_ISSUER"]])

    def test_rejects_wrong_owner_issuer_audience_expiry_and_scope(self):
        for overrides in ({"sub": "other"}, {"iss": "https://other.example"}, {"aud": "other"}, {"exp": 1}, {"scope": ""}):
            with self.subTest(overrides=overrides):
                self.assertIn(self.rpc("tools/list", token=self.token(**overrides)).status_code, (401, 403))

    def test_rejects_invalid_signature(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode({"sub": "owner"}, other, algorithm="RS256")
        self.assertEqual(self.rpc("tools/list", token=token).status_code, 401)

    def test_invalid_workout_returns_tool_error_without_download(self):
        response = self.rpc("tools/call", {"name": "create_workout", "arguments": {"workout": {}}})
        result = response.json()["result"]
        self.assertTrue(result["isError"])
        self.assertIn("schema_version", result["content"][0]["text"])
        self.assertNotIn("download_url", str(result))

    def test_expired_and_modified_downloads_are_rejected(self):
        cipher = Fernet(self.settings["DOWNLOAD_ENCRYPTION_KEY"].encode())
        token = cipher.encrypt_at_time(json.dumps(self.workout).encode(), int(time.time()) - DOWNLOAD_TTL - 1).decode()
        for value in (token, token[:20] + "X" + token[21:], "invalid"):
            self.assertEqual(self.client.get(f"/downloads/{value}/workout.json").status_code, 404)

    def test_missing_configuration_fails_closed(self):
        with TestClient(create_app({})) as client:
            self.assertEqual(client.post("/mcp", json={}).status_code, 503)
            self.assertEqual(client.get("/health").status_code, 503)


if __name__ == "__main__":
    unittest.main()
