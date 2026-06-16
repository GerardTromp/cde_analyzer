"""DEPRECATED shim — the CDE Pydantic schema now lives in ``cde_lib.schema``.

Relocated under ADR-E004 (2026-06). These re-exports keep existing
``from CDE_Schema import ...`` and ``from CDE_Schema.<module> import ...``
call sites working unchanged. Import from ``cde_lib.schema`` in new code.

This shim will be removed at cde_analyzer 2.0.0.
"""

from cde_lib.schema import *  # noqa: F401,F403
from cde_lib.schema import __all__  # noqa: F401
