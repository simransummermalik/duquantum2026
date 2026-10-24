"""Tiny local server for the Watchcat dashboard."""

from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "watchcat_report.json"


class WatchcatHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path == "/api/report":
            if not REPORT_PATH.exists():
                self.send_error(404, "watchcat_report.json does not exist; run the demo first")
                return
            payload = REPORT_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path in {"/", "/index.html"}:
            self.path = "/ui/watchcat_dashboard.html"
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local Watchcat dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    handler = partial(WatchcatHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Watchcat dashboard: http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Watchcat dashboard")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
