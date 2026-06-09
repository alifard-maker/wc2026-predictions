#!/usr/bin/env python3
"""Serve a static maintenance page on a port while the app restarts."""
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "static" / "maintenance.html").read_text(
    encoding="utf-8"
)


class MaintenanceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Retry-After", "300")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    port = int(sys.argv[1])
    HTTPServer(("", port), MaintenanceHandler).serve_forever()


if __name__ == "__main__":
    main()
