"""
Centralized multi-curator curation editor server.

Hosts a single HTTPS (or HTTP) server that serves per-curator TSV editor
sessions.  Each curator accesses their session via a unique token URL.
The server enforces directory isolation, HMAC authentication, TLS,
rate limiting, and session expiration with pipeline integration.

Usage (via CLI):
    cde-analyzer pattern_util --serve-curation CONFIG.yaml \\
        --source coalesced_fields.tsv

Or programmatically:
    from actions.pattern_util.centralized_server import serve_curation
    serve_curation(config_path, source_path)
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Lazy imports for cde_analyzer modules are done inside functions.


# ---------------------------------------------------------------------------
# Curation state management
# ---------------------------------------------------------------------------

class CurationState:
    """Manages the ``.curation_state.yaml`` file tracking curator sessions."""

    def __init__(self, output_dir: Path, source_file: str, expires_at: int):
        self.state_path = output_dir / ".curation_state.yaml"
        self._lock = threading.Lock()
        self.data: dict = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(
                expires_at, tz=timezone.utc
            ).isoformat(),
            "expires_at_unix": expires_at,
            "source_file": source_file,
            "curators": {},
        }

    def add_curator(
        self,
        slug: str,
        token: str,
        email: str,
        output_file: str,
    ) -> None:
        with self._lock:
            self.data["curators"][slug] = {
                "token": token,
                "email": email,
                "status": "pending",
                "last_access": None,
                "output_file": output_file,
            }
            self._write()

    def update_status(self, slug: str, status: str) -> None:
        with self._lock:
            if slug in self.data["curators"]:
                self.data["curators"][slug]["status"] = status
                self.data["curators"][slug]["last_access"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                self._write()

    def get_status_summary(self) -> dict:
        """Return a snapshot of all curator statuses."""
        with self._lock:
            return {
                slug: info["status"]
                for slug, info in self.data["curators"].items()
            }

    def all_submitted(self) -> bool:
        with self._lock:
            return all(
                info["status"] == "submitted"
                for info in self.data["curators"].values()
            )

    def _write(self) -> None:
        """Write state to YAML (called under lock)."""
        import yaml

        with open(self.state_path, "w", encoding="utf-8") as fh:
            yaml.dump(self.data, fh, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Per-curator session data
# ---------------------------------------------------------------------------

class CuratorSession:
    """Holds in-memory TSV content and output path for one curator."""

    def __init__(
        self,
        slug: str,
        name: str,
        email: str,
        token: str,
        output_path: Path,
        content: str,
        filename: str,
    ):
        self.slug = slug
        self.name = name
        self.email = email
        self.token = token
        self.output_path = output_path
        self.content = content
        self.filename = filename
        self._lock = threading.Lock()

    def save(self, new_content: str) -> None:
        with self._lock:
            self.content = new_content
            self.output_path.write_text(new_content, encoding="utf-8")

    def get_content(self) -> str:
        with self._lock:
            return self.content


# ---------------------------------------------------------------------------
# Admin dashboard HTML
# ---------------------------------------------------------------------------

_ADMIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CDE Curation Server — Admin</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
  h1 { color: #1a365d; }
  table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
  th, td { padding: 0.5rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
  th { background: #edf2f7; font-weight: 600; }
  .status-pending { color: #744210; }
  .status-in_progress { color: #2b6cb0; }
  .status-submitted { color: #276749; font-weight: 600; }
  .status-expired { color: #9b2c2c; }
  .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }
  .badge-pending { background: #fefcbf; }
  .badge-in_progress { background: #bee3f8; }
  .badge-submitted { background: #c6f6d5; }
  .badge-expired { background: #fed7d7; }
  #countdown { font-size: 1.1rem; color: #4a5568; margin: 0.5rem 0; }
  .refresh-btn { background: #4299e1; color: white; border: none; padding: 0.5rem 1rem;
                 border-radius: 4px; cursor: pointer; font-size: 0.9rem; }
  .refresh-btn:hover { background: #3182ce; }
</style>
</head>
<body>
<h1>CDE Curation Server</h1>
<p>Source: <strong>__SOURCE__</strong></p>
<p id="countdown">Expires: __EXPIRES__</p>
<table>
  <thead><tr><th>Curator</th><th>Email</th><th>Status</th><th>Last Access</th><th>URL</th></tr></thead>
  <tbody id="curators"></tbody>
</table>
<button class="refresh-btn" onclick="refresh()">Refresh</button>
<script>
function refresh() {
  fetch('/admin/status').then(r => r.json()).then(data => {
    const tbody = document.getElementById('curators');
    tbody.innerHTML = '';
    for (const [slug, info] of Object.entries(data.curators)) {
      const tr = document.createElement('tr');
      const statusCls = 'status-' + info.status;
      const badgeCls = 'badge badge-' + info.status;
      tr.innerHTML =
        '<td>' + info.name + '</td>' +
        '<td>' + info.email + '</td>' +
        '<td><span class="' + badgeCls + '">' + info.status + '</span></td>' +
        '<td>' + (info.last_access || '—') + '</td>' +
        '<td><a href="' + info.url + '" target="_blank">open</a></td>';
      tbody.appendChild(tr);
    }
  });
}
refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main server function
# ---------------------------------------------------------------------------

def serve_curation(
    config_path: Path,
    source_path: Path,
    *,
    no_browser: bool = False,
) -> int:
    """Start the centralized curation server.

    Parameters
    ----------
    config_path : Path
        Path to the curation_server.yaml configuration file.
    source_path : Path
        Path to the source TSV (e.g. coalesced_fields.tsv).
    no_browser : bool
        If True, don't open the admin dashboard in a browser.

    Returns
    -------
    int
        Exit code (0 on clean shutdown).
    """
    from .editor_config import load_config, CuratorConfig
    from .editor_security import (
        generate_secret_key,
        generate_token,
        parse_token,
        verify_token,
        RateLimiter,
        setup_tls_context,
        _slugify,
    )

    # --- Load config ----------------------------------------------------------
    config = load_config(config_path)
    output_dir = config.server.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Validate source file -------------------------------------------------
    source_path = source_path.resolve()
    if not source_path.is_file():
        print(f"Error: source file not found: {source_path}", file=sys.stderr)
        return 1

    source_content = source_path.read_text(encoding="utf-8")
    source_name = source_path.name

    # --- Secret key -----------------------------------------------------------
    if config.security.secret_key == "auto":
        secret_key = generate_secret_key()
    else:
        secret_key = config.security.secret_key

    # --- Compute expiry -------------------------------------------------------
    expires_at = int(time.time()) + config.server.timespan_seconds

    # --- Initialize state -----------------------------------------------------
    state = CurationState(output_dir, str(source_path), expires_at)

    # --- Load editor HTML -----------------------------------------------------
    html_path = Path(__file__).parent / "tsv_editor.html"
    if not html_path.is_file():
        print(f"Error: tsv_editor.html not found at {html_path}", file=sys.stderr)
        return 1
    html_bytes = html_path.read_bytes()

    # --- Initialize per-curator sessions and curation columns -----------------
    sessions: dict[str, CuratorSession] = {}
    token_to_slug: dict[str, str] = {}
    slug_to_email: dict[str, str] = {}

    # Parse source TSV to add curation columns
    source_rows, original_fields = _parse_source_tsv(source_content)

    curation_cols = ["decision", "modification", "notes", "curator"]
    new_cols = [c for c in curation_cols if c not in original_fields]
    output_fields = original_fields + new_cols

    for curator_cfg in config.curators:
        slug = _slugify(curator_cfg.name)
        token = generate_token(
            curator_cfg.name, curator_cfg.email, expires_at, secret_key
        )
        out_file = output_dir / f"{token}.tsv"

        # Write initial curator TSV with curation columns
        curator_content = _write_curator_tsv(
            source_rows, output_fields, curator_cfg.name, out_file
        )

        session = CuratorSession(
            slug=slug,
            name=curator_cfg.name,
            email=curator_cfg.email,
            token=token,
            output_path=out_file,
            content=curator_content,
            filename=f"{source_path.stem}.{slug}.tsv",
        )
        sessions[token] = session
        token_to_slug[token] = slug
        slug_to_email[slug] = curator_cfg.email

        state.add_curator(slug, token, curator_cfg.email, str(out_file))

    # --- Rate limiter ---------------------------------------------------------
    rate_limiter = RateLimiter(
        max_attempts=config.security.max_attempts,
        lockout_base=float(config.security.lockout_base),
        lockout_multiplier=float(config.security.lockout_multiplier),
    )

    # --- Build admin HTML -----------------------------------------------------
    expires_str = datetime.fromtimestamp(
        expires_at, tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")
    admin_html = _ADMIN_HTML.replace("__SOURCE__", source_name)
    admin_html = admin_html.replace("__EXPIRES__", expires_str)
    admin_html_bytes = admin_html.encode("utf-8")

    # --- Prepare HTML with token injection ------------------------------------
    # The editor HTML will be served with a small script injection that sets
    # the base path for fetch calls.
    def _make_editor_html(token: str, curator_name: str) -> bytes:
        """Inject token-aware configuration into the editor HTML."""
        injection = (
            f'<script>'
            f'window.__CDE_TOKEN__ = "{token}";'
            f'window.__CDE_CURATOR__ = "{curator_name}";'
            f'window.__CDE_EXPIRES__ = {expires_at};'
            f'window.__CDE_CENTRALIZED__ = true;'
            f'</script>\n'
        )
        # Insert just before </head>
        html_str = html_bytes.decode("utf-8")
        html_str = html_str.replace("</head>", injection + "</head>", 1)
        return html_str.encode("utf-8")

    # Pre-build per-token HTML
    editor_html_cache: dict[str, bytes] = {}
    for token, session in sessions.items():
        editor_html_cache[token] = _make_editor_html(token, session.name)

    # --- HTTP Handler ---------------------------------------------------------
    # Token route pattern: /c/{token}/...
    TOKEN_ROUTE_RE = re.compile(r"^/c/([^/]+)(/.*)?$")
    ADMIN_ROUTE_RE = re.compile(r"^/admin(/.*)?$")
    # Mutable container for base_url (set after server binds to actual port)
    _server_info: dict = {"base_url": ""}

    class CurationHandler(BaseHTTPRequestHandler):

        def do_GET(self):
            path = urlparse(self.path).path

            # --- Admin routes (localhost only) --------------------------------
            admin_match = ADMIN_ROUTE_RE.match(path)
            if admin_match:
                if not self._is_localhost():
                    self._json_error(403, "Admin access restricted to localhost")
                    return
                sub = admin_match.group(1) or "/"
                if sub in ("/", "/index.html"):
                    self._serve(admin_html_bytes, "text/html; charset=utf-8")
                elif sub == "/status":
                    self._serve_admin_status()
                else:
                    self.send_error(404)
                return

            # --- Token routes -------------------------------------------------
            token_match = TOKEN_ROUTE_RE.match(path)
            if not token_match:
                self.send_error(404)
                return

            token = token_match.group(1)
            sub = token_match.group(2) or "/"
            ip = self._client_ip()

            # Rate limit check
            allowed, retry_after = rate_limiter.check(ip)
            if not allowed:
                self._json_error(
                    429,
                    f"Too many failed attempts. Retry after {retry_after:.0f}s",
                )
                return

            # Token validation
            session = sessions.get(token)
            if not session:
                rate_limiter.record_failure(ip)
                self._json_error(403, "Invalid token")
                return

            valid, reason = verify_token(
                token, session.email, secret_key, grace_seconds=300
            )
            if not valid:
                if "expired" in reason:
                    self._json_error(403, "Curation period expired")
                else:
                    rate_limiter.record_failure(ip)
                    self._json_error(403, "Invalid token")
                return

            rate_limiter.record_success(ip)

            # Update status on first access
            slug = token_to_slug[token]
            current_status = state.get_status_summary().get(slug)
            if current_status == "pending":
                state.update_status(slug, "in_progress")

            # Serve requested resource
            if sub in ("/", "/index.html"):
                html = editor_html_cache.get(token, html_bytes)
                self._serve(html, "text/html; charset=utf-8")
            elif sub == "/data":
                payload = json.dumps({
                    "content": session.get_content(),
                    "filename": session.filename,
                }).encode("utf-8")
                self._serve(payload, "application/json")
            elif sub == "/info":
                info = {
                    "path": str(session.output_path),
                    "filename": session.filename,
                    "server_mode": True,
                    "curator": session.name,
                    "expires_at": expires_at,
                }
                self._serve(json.dumps(info).encode("utf-8"), "application/json")
            else:
                self.send_error(404)

        def do_POST(self):
            path = urlparse(self.path).path
            token_match = TOKEN_ROUTE_RE.match(path)
            if not token_match:
                self.send_error(404)
                return

            token = token_match.group(1)
            sub = token_match.group(2) or "/"
            ip = self._client_ip()

            # Rate limit
            allowed, retry_after = rate_limiter.check(ip)
            if not allowed:
                self._json_error(
                    429,
                    f"Too many failed attempts. Retry after {retry_after:.0f}s",
                )
                return

            session = sessions.get(token)
            if not session:
                rate_limiter.record_failure(ip)
                self._json_error(403, "Invalid token")
                return

            valid, reason = verify_token(
                token, session.email, secret_key, grace_seconds=300
            )
            if not valid:
                self._json_error(403, reason)
                return

            rate_limiter.record_success(ip)

            if sub == "/save":
                self._handle_save(session)
            else:
                self.send_error(404)

        def _handle_save(self, session: CuratorSession):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                new_content = data["content"]
                # Validate: content must not be empty
                if not new_content.strip():
                    self._json_error(400, "Cannot save empty content")
                    return
                session.save(new_content)
                state.update_status(session.slug, "submitted")
                resp = json.dumps({
                    "status": "ok",
                    "path": str(session.output_path),
                }).encode("utf-8")
                self._serve(resp, "application/json")

                # Check if all curators have submitted
                if state.all_submitted():
                    print("\n  All curators have submitted. Ready for merge.")

            except (json.JSONDecodeError, KeyError) as exc:
                self._json_error(400, f"Invalid save payload: {exc}")
            except Exception as exc:
                self._json_error(500, str(exc))

        def _serve_admin_status(self):
            """Return JSON status for the admin dashboard."""
            curator_info = {}
            for token, session in sessions.items():
                slug = token_to_slug[token]
                status_map = state.get_status_summary()
                curator_data = state.data["curators"].get(slug, {})
                curator_info[slug] = {
                    "name": session.name,
                    "email": session.email,
                    "status": status_map.get(slug, "unknown"),
                    "last_access": curator_data.get("last_access"),
                    "url": f"{_server_info['base_url']}/c/{token}/",
                }

            payload = json.dumps({
                "source": state.data["source_file"],
                "started_at": state.data["started_at"],
                "expires_at": state.data["expires_at"],
                "curators": curator_info,
            }).encode("utf-8")
            self._serve(payload, "application/json")

        def _serve(self, data: bytes, content_type: str):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            # Security headers
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def _json_error(self, code: int, message: str):
            body = json.dumps({"status": "error", "message": message})
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def _is_localhost(self) -> bool:
            ip = self._client_ip()
            return ip in ("127.0.0.1", "::1", "localhost")

        def _client_ip(self) -> str:
            # Respect X-Forwarded-For for reverse proxy setups
            forwarded = self.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
            return self.client_address[0]

        def log_message(self, format, *log_args):
            # Minimal logging: just method and path
            pass

    # --- TLS setup ------------------------------------------------------------
    ssl_context = setup_tls_context(
        mode=config.tls.mode,
        cert_path=config.tls.cert,
        key_path=config.tls.key,
        output_dir=output_dir,
    )

    # --- Start server ---------------------------------------------------------
    server = HTTPServer((config.server.host, config.server.port), CurationHandler)
    actual_port = server.server_address[1]
    if ssl_context:
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)

    protocol = "https" if ssl_context else "http"
    host_display = config.server.host
    if host_display == "0.0.0.0":
        host_display = "127.0.0.1"
    base_url = f"{protocol}://{host_display}:{actual_port}"
    _server_info["base_url"] = base_url

    print(f"\nCDE Centralized Curation Server")
    print(f"  Admin:    {base_url}/admin/")
    print(f"  Source:   {source_path}")
    print(f"  Output:   {output_dir}")
    print(f"  Expires:  {expires_str}")
    print(f"  TLS:      {config.tls.mode}")
    print()
    print("  Curator URLs:")
    for token, session in sessions.items():
        print(f"    {session.name}: {base_url}/c/{token}/")
    print()
    print("  Press Ctrl-C to stop.\n")

    # Browser launch: prefer cde_lib.browser.open_browser_quietly when
    # available (suppresses GCM/dbus noise on headless WSL).  Falls back
    # to stdlib webbrowser if cde_lib not installed.  See cde_analyzer
    # pyproject.toml [project.optional-dependencies].quiet-browser.
    if not no_browser:
        try:
            from cde_lib.browser import open_browser_quietly
        except ImportError:
            import webbrowser
            def open_browser_quietly(u):  # type: ignore
                return webbrowser.open(u)
        threading.Timer(0.5, lambda: open_browser_quietly(f"{base_url}/admin/")).start()

    # --- Expiry watchdog ------------------------------------------------------
    def _expiry_watchdog():
        while True:
            time.sleep(30)
            now = int(time.time())
            if now > expires_at:
                summary = state.get_status_summary()
                pending = [s for s, st in summary.items() if st != "submitted"]
                if pending:
                    print(f"\n  Curation period expired. "
                          f"Pending curators: {', '.join(pending)}")
                    for slug in pending:
                        state.update_status(slug, "expired")
                break

    watchdog = threading.Thread(target=_expiry_watchdog, daemon=True)
    watchdog.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("\nServer stopped.")

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_source_tsv(content: str) -> tuple[list[dict], list[str]]:
    """Parse TSV content into rows and field names."""
    import io
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    fields = list(reader.fieldnames or [])
    rows = list(reader)
    return rows, fields


def _write_curator_tsv(
    rows: list[dict],
    output_fields: list[str],
    curator_name: str,
    output_path: Path,
) -> str:
    """Write a curator TSV with curation columns and return its content."""
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=output_fields, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        out_row = {k: row.get(k, "") for k in output_fields}
        out_row.setdefault("decision", "")
        out_row.setdefault("modification", "")
        out_row.setdefault("notes", "")
        out_row["curator"] = curator_name
        writer.writerow(out_row)

    content = buf.getvalue()
    output_path.write_text(content, encoding="utf-8")
    return content
