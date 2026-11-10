"""Local Sunshine Web UI API client (HTTP Basic authentication)."""

import base64
import json
import ssl
import urllib.error
import urllib.request


class SunshineAPIError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SunshineAPI:
    def __init__(self, username, password, port=47990, verify_tls=False):
        if not username or not password or ":" in username:
            raise SunshineAPIError("Provide a Sunshine username (without ':') and password.")
        if not 1 <= port <= 65535:
            raise SunshineAPIError("Sunshine API port must be between 1 and 65535.")
        self.url = f"https://localhost:{port}"
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
        context = ssl.create_default_context()
        if not verify_tls:
            # Sunshine ships a self-signed certificate; this client is localhost-only.
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect(),
            urllib.request.HTTPSHandler(context=context),
        )

    def _request(self, method, payload=None):
        request = urllib.request.Request(
            self.url + "/api/apps", headers=self.headers, method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise SunshineAPIError("Sunshine authentication/access denied; check username and password.") from None
            raise SunshineAPIError(f"Sunshine API returned HTTP {exc.code}.") from None
        except (urllib.error.URLError, OSError) as exc:
            raise SunshineAPIError(f"Cannot reach Sunshine API at {self.url}; check that Sunshine is running.") from exc
        except (ValueError, UnicodeError):
            raise SunshineAPIError("Sunshine API returned invalid JSON.") from None
        if not isinstance(result, dict) or result.get("status") is False:
            raise SunshineAPIError("Sunshine API reported a failed request.")
        return result

    def list_apps(self):
        apps = self._request("GET").get("apps")
        if not isinstance(apps, list) or any(
            not isinstance(app, dict) or not isinstance(app.get("name"), str)
            for app in apps
        ):
            raise SunshineAPIError("Sunshine API returned an invalid application list.")
        return apps

    def upsert_app(self, app):
        # Saves can reorder the list, so indexes must never be cached across saves.
        existing = self.list_apps()
        matches = [i for i, item in enumerate(existing) if item["name"] == app["name"]]
        if len(matches) > 1:
            raise SunshineAPIError(f"Multiple Sunshine applications named {app['name']!r}; resolve duplicates first.")
        index = matches[0] if matches else -1
        payload = dict(existing[index]) if index >= 0 else {}
        payload.update(app)
        payload["index"] = index
        # Older importers emit config-compatible placeholders, not API field types.
        if payload.get("detached") is False:
            payload["detached"] = []
        if payload.get("cmd") == []:
            payload["cmd"] = ""
        if self._request("POST", payload).get("status") is not True:
            raise SunshineAPIError("Sunshine API did not confirm the application was saved.")
        return "Updated" if index >= 0 else "Created"
