from __future__ import annotations

import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bbt_bizdev.company_research import company_research  # noqa: E402


class FrontendHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/company-research":
            self.handle_company_research(parsed.query)
            return
        self.serve_static(parsed.path)

    def handle_company_research(self, query: str):
        params = parse_qs(query)
        company = unquote(params.get("company", [""])[0]).strip()
        website = unquote(params.get("website", [""])[0]).strip()
        if not company:
            self.send_json({"error": "Missing company"}, status=400)
            return
        payload = company_research(company=company, website=website)
        self.send_json(payload)

    def serve_static(self, request_path: str):
        if request_path in {"", "/"}:
            request_path = "/index.html"
        safe_path = Path(*[part for part in request_path.split("/") if part and part not in {".", ".."}])
        file_path = (ROOT / safe_path).resolve()
        if not file_path.is_file() or ROOT not in file_path.parents:
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        raw = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_json(self, payload: dict, status: int = 200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        print(format % args)


def main():
    server = None
    for port in range(8000, 8010):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), FrontendHandler)
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("No free local port found between 8000 and 8009")
    print(f"Serving BBT Lead Triage at http://127.0.0.1:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
