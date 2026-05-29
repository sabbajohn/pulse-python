import io
import json
import pathlib
import sys
import unittest
from urllib import error
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from vorapulse import (
    PulseAuthenticationError,
    PulseClient,
    PulseValidationError,
)


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def getcode(self):
        return self.status


class PulseClientTest(unittest.TestCase):
    def test_send_sync_builds_authorized_request(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["headers"] = dict(req.header_items())
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(200, {"success": True})

        with patch("urllib.request.urlopen", fake_urlopen):
            result = PulseClient("https://pulse.test", "token", timeout=12).emails.send_sync({
                "to": [{"email": "user@example.com"}],
                "subject": "Hello",
                "html": "<p>Hello</p>",
            })

        self.assertTrue(result["success"])
        self.assertEqual(captured["url"], "https://pulse.test/api/v2/emails/send-sync")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer token")
        self.assertEqual(captured["headers"]["User-agent"], "vorapulse/0.1.0")
        self.assertEqual(captured["body"]["subject"], "Hello")
        self.assertEqual(captured["timeout"], 12)

    def test_normalizes_base_url_when_api_v2_is_already_present(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            return FakeResponse(200, {"status": "ok"})

        with patch("urllib.request.urlopen", fake_urlopen):
            result = PulseClient("https://pulse.test/api/v2", "token").get("health")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(captured["url"], "https://pulse.test/api/v2/health")

    def test_builds_query_string_for_collection_requests(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return FakeResponse(200, {"data": []})

        with patch("urllib.request.urlopen", fake_urlopen):
            PulseClient("https://pulse.test", "token").audiences.channels({
                "page": 2,
                "tags": ["vip", "trial"],
            })

        self.assertEqual(captured["method"], "GET")
        self.assertEqual(captured["url"], "https://pulse.test/api/v2/audience/channels?page=2&tags=vip&tags=trial")

    def test_supports_member_transition_and_flask_legacy_aliases(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["headers"] = dict(req.header_items())
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse(200, {"success": True})

        try:
            from flask import Flask
        except ModuleNotFoundError:
            self.skipTest("Flask is not installed in the current test environment.")

        from vorapulse.flask import PulseFlask

        app = Flask(__name__)
        app.config["PULSE_VORA_BASE_URL"] = "https://pulse.test"
        app.config["PULSE_VORA_TOKEN"] = "legacy-token"
        app.config["PULSE_VORA_TIMEOUT"] = 45

        pulse = PulseFlask(app)

        with app.app_context(), patch("urllib.request.urlopen", fake_urlopen):
            pulse.client.audiences.transition_member(42, {"status": "qualified"})

        self.assertEqual(captured["url"], "https://pulse.test/api/v2/audience/members/42/transition")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer legacy-token")
        self.assertEqual(captured["body"], {"status": "qualified"})

    def test_maps_validation_errors(self):
        def fake_urlopen(req, timeout):
            body = json.dumps({"message": "Invalid", "errors": {"email": ["required"]}}).encode("utf-8")
            raise error.HTTPError(req.full_url, 422, "Invalid", {}, io.BytesIO(body))

        with patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(PulseValidationError) as raised:
                PulseClient("https://pulse.test", "token").templates.create({"name": ""})

        self.assertEqual(raised.exception.errors, {"email": ["required"]})

    def test_requires_configuration(self):
        with self.assertRaises(PulseAuthenticationError):
            PulseClient("", "").get("health")


if __name__ == "__main__":
    unittest.main()
