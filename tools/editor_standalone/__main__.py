#!/usr/bin/env python3
"""
Standalone CDE TSV Editor — zero external dependencies.

Launch a browser-based TSV editor backed by a local HTTP server.
Requires only Python 3.8+; no pip install needed.

Usage:
    python cde_editor.pyz [FILE] [--port N] [--no-browser]
    python cde_editor.pyz --version

When FILE is provided the editor pre-loads it and saves back to disk.
Without FILE the editor opens blank for drag-and-drop loading.
Press Ctrl-C to stop the server.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

_FALLBACK_VERSION = "1.5.0"  # updated by build_editor_zipapp.py

def _resolve_version() -> str:
    """Return the cde_analyzer version if importable, else the fallback."""
    try:
        # Works when running from the full cde_analyzer installation
        from cde_analyzer.__version__ import __version__ as ver
        return ver
    except ImportError:
        return _FALLBACK_VERSION

__version__ = _resolve_version()


def _load_html() -> bytes:
    """Load tsv_editor.html from filesystem or zipapp archive."""
    # 1. Filesystem (running from source directory)
    here = Path(__file__).parent
    html_fs = here / "tsv_editor.html"
    if html_fs.is_file():
        return html_fs.read_bytes()
    # 2. Zipapp archive (running as .pyz)
    archive = Path(sys.argv[0])
    if archive.is_file() and zipfile.is_zipfile(str(archive)):
        with zipfile.ZipFile(str(archive)) as zf:
            return zf.read("tsv_editor.html")
    print("Error: tsv_editor.html not found", file=sys.stderr)
    raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cde_editor",
        description="Standalone CDE TSV Editor — browser-based, no dependencies.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="TSV file to edit (omit for blank editor with drag-drop)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Server port (default: auto-assign)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start server without opening browser",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    # --- Resolve input file ---------------------------------------------------
    tsv_path: Path | None = None
    tsv_content = ""
    if args.file:
        tsv_path = Path(args.file).resolve()
        if not tsv_path.exists():
            print(f"Error: file not found: {tsv_path}", file=sys.stderr)
            return 1
        tsv_content = tsv_path.read_text(encoding="utf-8")

    # --- Load editor HTML -----------------------------------------------------
    html_content = _load_html()

    # --- HTTP handler (closure captures tsv_path, tsv_content, html_content) --
    class EditorHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._serve(html_content, "text/html; charset=utf-8")
            elif path == "/data":
                payload = json.dumps({
                    "content": tsv_content,
                    "filename": tsv_path.name if tsv_path else "",
                }).encode("utf-8")
                self._serve(payload, "application/json")
            elif path == "/info":
                info = {
                    "path": str(tsv_path) if tsv_path else "",
                    "filename": tsv_path.name if tsv_path else "",
                    "server_mode": True,
                }
                self._serve(json.dumps(info).encode("utf-8"), "application/json")
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/save":
                self._handle_save()
            else:
                self.send_error(404)

        def _serve(self, data: bytes, content_type: str):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_save(self):
            nonlocal tsv_content
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                new_content = data["content"]
                if tsv_path:
                    tsv_path.write_text(new_content, encoding="utf-8")
                    tsv_content = new_content
                    resp = json.dumps({
                        "status": "ok",
                        "path": str(tsv_path),
                    }).encode("utf-8")
                else:
                    resp = json.dumps({
                        "status": "error",
                        "message": "No file path — use Save As (download) instead",
                    }).encode("utf-8")
                self._serve(resp, "application/json")
            except Exception as exc:
                self.send_error(500, str(exc))

        def log_message(self, format, *log_args):
            pass  # suppress per-request logging

    # --- Start server ---------------------------------------------------------
    server = HTTPServer(("127.0.0.1", args.port), EditorHandler)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"

    file_desc = f" ({tsv_path.name})" if tsv_path else ""
    print(f"\nCDE TSV Editor{file_desc}")
    print(f"  URL:    {url}")
    if tsv_path:
        print(f"  File:   {tsv_path}")
    print("  Press Ctrl-C to stop.\n")

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("\nEditor stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
