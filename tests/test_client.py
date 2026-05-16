import io
import json
import unittest
from urllib import error
from unittest.mock import patch

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
        self.assertEqual(captured["body"]["subject"], "Hello")
        self.assertEqual(captured["timeout"], 12)

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
