# -*- coding: utf-8 -*-
"""Preview server for the redesign: serves final-d.html at / and proxies
/api/* and /img/* to the real FastAPI backend on :8001.

No source file in app/ is touched.
"""
import http.server, socketserver, urllib.request, urllib.error, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "final-d.html")
BACKEND = "http://127.0.0.1:8001"
PORT = 8002


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        pass

    def _send(self, code, body, ctype="application/octet-stream", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _proxy(self):
        url = BACKEND + self.path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=self.command)
        for h in ("Content-Type", "X-Device-Id", "X-Student-Id", "Accept", "Accept-Language"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "application/octet-stream")
                self._send(r.status, data, ctype)
        except urllib.error.HTTPError as e:
            data = e.read()
            self._send(e.code, data, e.headers.get("Content-Type", "application/json"))
        except Exception as e:
            self._send(502, str(e).encode(), "text/plain; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html", "/preview"):
            with open(PAGE, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8",
                           {"Cache-Control": "no-store"})
        elif self.path.startswith("/api/") or self.path.startswith("/img/"):
            self._proxy()
        else:
            self._proxy()

    def do_POST(self):
        self._proxy()


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), H) as srv:
        print("preview on http://127.0.0.1:%d/  (backend %s)" % (PORT, BACKEND), flush=True)
        srv.serve_forever()
