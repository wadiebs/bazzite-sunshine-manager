import io
import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from common.sunshine_api import SunshineAPI, SunshineAPIError


class SunshineAPITests(unittest.TestCase):
    def setUp(self):
        self.api = SunshineAPI("user", "secret")
        self.api.opener = Mock()

    def respond(self, payload):
        return io.BytesIO(json.dumps(payload).encode())

    def test_authenticated_create_normalizes_fields(self):
        self.api.opener.open.side_effect = [
            self.respond({"apps": []}), self.respond({"status": True}),
        ]
        self.assertEqual(self.api.upsert_app({"name": "Desktop", "cmd": [], "detached": False}), "Created")
        request = self.api.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://localhost:47990/api/apps")
        self.assertEqual(request.get_header("Authorization"), "Basic dXNlcjpzZWNyZXQ=")
        self.assertEqual(json.loads(request.data), {"name": "Desktop", "cmd": "", "detached": [], "index": -1})

    def test_refreshes_indexes_and_preserves_custom_fields(self):
        self.api.opener.open.side_effect = [
            self.respond({"apps": [{"name": "Z", "prep-cmd": [{"do": "setup"}]}]}),
            self.respond({"status": True}),
            self.respond({"apps": [{"name": "A"}, {"name": "Z", "prep-cmd": [{"do": "setup"}]}]}),
            self.respond({"status": True}),
        ]
        self.api.upsert_app({"name": "A"})
        self.assertEqual(self.api.upsert_app({"name": "Z", "cmd": "game"}), "Updated")
        payload = json.loads(self.api.opener.open.call_args.args[0].data)
        self.assertEqual(payload["index"], 1)
        self.assertEqual(payload["prep-cmd"], [{"do": "setup"}])

    def test_rejects_ambiguous_names_without_saving(self):
        self.api.opener.open.return_value = self.respond({"apps": [{"name": "A"}, {"name": "A"}]})
        with self.assertRaises(SunshineAPIError):
            self.api.upsert_app({"name": "A"})
        self.assertEqual(self.api.opener.open.call_count, 1)

    def test_failures(self):
        for error in [HTTPError(self.api.url, 401, "Unauthorized", {}, None), URLError("offline")]:
            with self.subTest(error=error):
                self.api.opener.open.side_effect = error
                with self.assertRaises(SunshineAPIError):
                    self.api.list_apps()

    def test_invalid_responses(self):
        for payload in [{"status": False}, {}, {"apps": [None]}, {"apps": "invalid"}]:
            with self.subTest(payload=payload):
                self.api.opener.open.return_value = self.respond(payload)
                with self.assertRaises(SunshineAPIError):
                    self.api.list_apps()

    def test_save_requires_success(self):
        self.api.opener.open.side_effect = [self.respond({"apps": []}), self.respond({})]
        with self.assertRaises(SunshineAPIError):
            self.api.upsert_app({"name": "A"})


if __name__ == "__main__":
    unittest.main()
