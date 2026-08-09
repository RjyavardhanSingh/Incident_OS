import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from incident_os_cli.emit import PROFILES, emit

_UI = (Path(__file__).parent / "lab_ui.html").read_text(encoding="utf-8")


class LabHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, api_url="", **kwargs):
        self.api_url = api_url
        super().__init__(*args, **kwargs)

    def log_message(self, *args):
        pass

    def _send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method, path):
        url = self.api_url.rstrip("/") + path
        body = None
        if self.headers.get("Content-Length"):
            body = self.rfile.read(int(self.headers["Content-Length"]))
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                detail = json.loads(raw) if raw else {"detail": exc.reason}
            except Exception:
                detail = {"detail": str(exc.reason)}
            self._send_json(exc.code, detail)
        except Exception as exc:
            self._send_json(502, {"detail": str(exc)})

    def _serve_ui(self):
        body = _UI.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _emit(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            payload = {}
        profile = payload.get("profile", "all")
        if profile not in PROFILES:
            self._send_json(400, {"detail": f"unknown profile {profile!r}"})
            return
        try:
            emit(self.api_url.rstrip("/") + "/api/v1/otlp", profile)
            self._send_json(200, {"ok": True, "profile": profile})
        except Exception as exc:
            self._send_json(500, {"detail": str(exc)})

    def do_GET(self):
        if self.path in ("/", "/index.html", "/lab"):
            return self._serve_ui()
        if self.path.startswith("/api/"):
            return self._proxy("GET", self.path)
        self._send_json(404, {"detail": "not found"})

    def do_POST(self):
        if self.path == "/chaos/emit":
            return self._emit()
        if self.path.startswith("/api/"):
            return self._proxy("POST", self.path)
        self._send_json(404, {"detail": "not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


def serve(api_url: str, port: int = 8080) -> None:
    handler = lambda *args, **kwargs: LabHandler(*args, api_url=api_url, **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Incident OS chaos lab -> http://127.0.0.1:{port}")
    print(f"API: {api_url}   (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
