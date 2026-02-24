"""
Security utilities for the centralized curation editor.

Token generation/verification (HMAC-based segmented tokens),
rate limiting with progressive lockout, and TLS certificate setup.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import ssl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Token generation and verification
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a curator name to a URL-safe slug.

    >>> _slugify("Alice Smith")
    'alice_smith'
    >>> _slugify("bob")
    'bob'
    """
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def generate_secret_key() -> str:
    """Generate a cryptographically random 32-byte hex secret."""
    return secrets.token_hex(32)


def generate_token(
    curator_name: str,
    curator_email: str,
    expires_at: int,
    secret_key: str,
) -> str:
    """Create a segmented HMAC token.

    Format: ``{slug}_{expiry_hex}_{hmac_hex[:16]}``

    The slug and expiry are extractable from the token string;
    the HMAC suffix proves authenticity.

    Parameters
    ----------
    curator_name : str
        Human-readable curator name (e.g. "Alice Smith").
    curator_email : str
        Curator email address used in HMAC input.
    expires_at : int
        Unix timestamp when the token expires.
    secret_key : str
        Server secret for HMAC computation.

    Returns
    -------
    str
        Segmented token string.
    """
    slug = _slugify(curator_name)
    expiry_hex = f"{expires_at:08X}"
    payload = f"{slug}|{curator_email}|{expiry_hex}"
    mac = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"{slug}_{expiry_hex}_{mac}"


def parse_token(token: str) -> tuple[str, int, str]:
    """Extract slug, expiry, and HMAC from a segmented token.

    Returns
    -------
    tuple[str, int, str]
        (curator_slug, expiry_unix, hmac_hex)

    Raises
    ------
    ValueError
        If the token does not have the expected structure.
    """
    parts = token.rsplit("_", 2)
    if len(parts) < 3:
        raise ValueError("malformed token: expected {slug}_{expiry}_{hmac}")
    hmac_hex = parts[-1]
    expiry_hex = parts[-2]
    slug = "_".join(parts[:-2])
    try:
        expiry_unix = int(expiry_hex, 16)
    except ValueError:
        raise ValueError(f"malformed expiry segment: {expiry_hex!r}")
    return slug, expiry_unix, hmac_hex


def verify_token(
    token: str,
    curator_email: str,
    secret_key: str,
    *,
    grace_seconds: int = 300,
) -> tuple[bool, str]:
    """Verify a segmented HMAC token.

    Parameters
    ----------
    token : str
        The token string to verify.
    curator_email : str
        Expected curator email (looked up by slug from config).
    secret_key : str
        Server secret for HMAC recomputation.
    grace_seconds : int
        Grace period (seconds) after expiry during which the token
        is still accepted (for final save).  Default 300 (5 min).

    Returns
    -------
    tuple[bool, str]
        (is_valid, reason).  ``reason`` is empty on success.
    """
    try:
        slug, expiry_unix, token_hmac = parse_token(token)
    except ValueError as exc:
        return False, str(exc)

    # Recompute HMAC
    expiry_hex = f"{expiry_unix:08X}"
    payload = f"{slug}|{curator_email}|{expiry_hex}"
    expected = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]

    if not hmac.compare_digest(expected, token_hmac):
        return False, "invalid token signature"

    # Check expiry
    now = int(time.time())
    if now > expiry_unix + grace_seconds:
        return False, "token expired"

    return True, ""


# ---------------------------------------------------------------------------
# Rate limiting with progressive lockout
# ---------------------------------------------------------------------------

@dataclass
class _IPRecord:
    """Tracks failed authentication attempts for a single IP."""
    attempts: int = 0
    last_failure: float = 0.0
    lockout_until: float = 0.0
    lockout_count: int = 0


@dataclass
class RateLimiter:
    """Per-IP rate limiter with exponential backoff lockout.

    Parameters
    ----------
    max_attempts : int
        Number of failed attempts before lockout triggers.
    lockout_base : float
        Base lockout duration in seconds.
    lockout_multiplier : float
        Each subsequent lockout is ``base * multiplier^n``.
    """
    max_attempts: int = 5
    lockout_base: float = 60.0
    lockout_multiplier: float = 2.0
    _records: dict[str, _IPRecord] = field(default_factory=dict, repr=False)

    def check(self, ip: str) -> tuple[bool, float]:
        """Check whether *ip* is currently allowed.

        Returns
        -------
        tuple[bool, float]
            (allowed, retry_after_seconds).
        """
        rec = self._records.get(ip)
        if rec is None:
            return True, 0.0
        now = time.time()
        if now < rec.lockout_until:
            return False, rec.lockout_until - now
        return True, 0.0

    def record_failure(self, ip: str) -> float:
        """Record a failed attempt for *ip*.

        Returns the lockout duration (0 if threshold not yet reached).
        """
        rec = self._records.setdefault(ip, _IPRecord())
        rec.attempts += 1
        rec.last_failure = time.time()
        if rec.attempts >= self.max_attempts:
            duration = self.lockout_base * (
                self.lockout_multiplier ** rec.lockout_count
            )
            rec.lockout_until = time.time() + duration
            rec.lockout_count += 1
            rec.attempts = 0  # reset counter for next cycle
            return duration
        return 0.0

    def record_success(self, ip: str) -> None:
        """Reset the failure counter for *ip* after a successful request."""
        self._records.pop(ip, None)


# ---------------------------------------------------------------------------
# TLS certificate setup
# ---------------------------------------------------------------------------

def setup_tls_context(
    *,
    mode: str = "auto",
    cert_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Optional[ssl.SSLContext]:
    """Create an SSL context based on the configured TLS mode.

    Parameters
    ----------
    mode : str
        ``"auto"`` — generate self-signed cert in *output_dir*/.tls/.
        ``"custom"`` — use provided *cert_path* and *key_path*.
        ``"proxy"`` — return None (plain HTTP behind reverse proxy).
    cert_path, key_path : Path, optional
        Required when ``mode="custom"``.
    output_dir : Path, optional
        Base directory for auto-generated certs.

    Returns
    -------
    ssl.SSLContext or None
        Context for wrapping the server socket, or None for proxy mode.
    """
    if mode == "proxy":
        return None

    if mode == "custom":
        if not cert_path or not key_path:
            raise ValueError("TLS custom mode requires cert and key paths")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert_path), str(key_path))
        return ctx

    if mode == "auto":
        if not output_dir:
            raise ValueError("TLS auto mode requires output_dir")
        tls_dir = output_dir / ".tls"
        tls_dir.mkdir(parents=True, exist_ok=True)
        cert_file = tls_dir / "server.pem"
        key_file = tls_dir / "server.key"

        if not cert_file.exists() or not key_file.exists():
            _generate_self_signed_cert(cert_file, key_file)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert_file), str(key_file))
        return ctx

    raise ValueError(f"unknown TLS mode: {mode!r}")


def _generate_self_signed_cert(cert_path: Path, key_path: Path) -> None:
    """Generate a self-signed certificate using OpenSSL subprocess.

    Falls back to a warning if OpenSSL is unavailable.
    """
    import subprocess
    import sys

    subject = "/CN=cde-curation-server/O=CDE Analyzer"
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", str(key_path),
        "-out", str(cert_path),
        "-days", "365",
        "-nodes",
        "-subj", subject,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(
            f"Warning: could not generate self-signed cert: {exc}\n"
            f"  Install OpenSSL or use --tls-mode custom/proxy.",
            file=sys.stderr,
        )
        raise
