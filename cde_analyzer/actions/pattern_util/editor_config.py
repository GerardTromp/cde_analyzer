"""
Configuration parsing and validation for the centralized curation editor.

Reads a YAML config file specifying curators, server settings, TLS mode,
and security parameters.  Provides sensible defaults for all optional fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CuratorConfig:
    """A single curator entry."""
    name: str
    email: str


@dataclass
class ServerConfig:
    """Server-level settings."""
    host: str = "0.0.0.0"
    port: int = 8443
    output_dir: Path = field(default_factory=lambda: Path("./curation_output"))
    timespan: str = "24h"

    @property
    def timespan_seconds(self) -> int:
        """Parse the timespan string into seconds.

        Supports suffixes: ``h`` (hours), ``m`` (minutes), ``d`` (days).
        Plain integer is treated as hours.
        """
        s = self.timespan.strip().lower()
        if s.endswith("d"):
            return int(s[:-1]) * 86400
        if s.endswith("h"):
            return int(s[:-1]) * 3600
        if s.endswith("m"):
            return int(s[:-1]) * 60
        if s.endswith("s"):
            return int(s[:-1])
        # bare number → hours
        return int(s) * 3600


@dataclass
class TLSConfig:
    """TLS configuration."""
    mode: str = "auto"  # auto | custom | proxy
    cert: Optional[Path] = None
    key: Optional[Path] = None


@dataclass
class SecurityConfig:
    """Security / rate-limiting parameters."""
    secret_key: str = "auto"
    max_attempts: int = 5
    lockout_base: int = 60
    lockout_multiplier: int = 2


@dataclass
class CurationServerConfig:
    """Top-level configuration for the centralized curation server."""
    curators: list[CuratorConfig] = field(default_factory=list)
    server: ServerConfig = field(default_factory=ServerConfig)
    tls: TLSConfig = field(default_factory=TLSConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)


def load_config(path: Path) -> CurationServerConfig:
    """Load and validate a curation server config from YAML.

    Parameters
    ----------
    path : Path
        Path to the YAML configuration file.

    Returns
    -------
    CurationServerConfig
        Validated configuration dataclass.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    ValueError
        If required fields are missing or invalid.
    """
    import yaml  # lazy — only needed when centralized server is used

    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    # --- Curators -----------------------------------------------------------
    raw_curators = raw.get("curators", [])
    if not raw_curators:
        raise ValueError("config must define at least one curator")
    curators = []
    for i, entry in enumerate(raw_curators):
        if isinstance(entry, str):
            raise ValueError(
                f"curator #{i + 1}: must be a mapping with 'name' and 'email', "
                f"got plain string {entry!r}"
            )
        name = entry.get("name")
        email = entry.get("email")
        if not name or not email:
            raise ValueError(
                f"curator #{i + 1}: both 'name' and 'email' are required"
            )
        curators.append(CuratorConfig(name=name, email=email))

    # --- Server -------------------------------------------------------------
    raw_server = raw.get("server", {})
    server = ServerConfig(
        host=raw_server.get("host", "0.0.0.0"),
        port=int(raw_server.get("port", 8443)),
        output_dir=Path(raw_server.get("output_dir", "./curation_output")),
        timespan=str(raw_server.get("timespan", "24h")),
    )

    # --- TLS ----------------------------------------------------------------
    raw_tls = raw.get("tls", {})
    tls = TLSConfig(
        mode=raw_tls.get("mode", "auto"),
        cert=Path(raw_tls["cert"]) if raw_tls.get("cert") else None,
        key=Path(raw_tls["key"]) if raw_tls.get("key") else None,
    )
    if tls.mode not in ("auto", "custom", "proxy"):
        raise ValueError(f"tls.mode must be auto|custom|proxy, got {tls.mode!r}")
    if tls.mode == "custom" and (not tls.cert or not tls.key):
        raise ValueError("tls.mode=custom requires cert and key paths")

    # --- Security -----------------------------------------------------------
    raw_sec = raw.get("security", {})
    security = SecurityConfig(
        secret_key=str(raw_sec.get("secret_key", "auto")),
        max_attempts=int(raw_sec.get("max_attempts", 5)),
        lockout_base=int(raw_sec.get("lockout_base", 60)),
        lockout_multiplier=int(raw_sec.get("lockout_multiplier", 2)),
    )

    return CurationServerConfig(
        curators=curators,
        server=server,
        tls=tls,
        security=security,
    )
