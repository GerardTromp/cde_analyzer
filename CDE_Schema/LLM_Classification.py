"""DEPRECATED shim — relocated to ``cde_lib.schema.LLM_Classification`` (ADR-E004).

Re-exports preserved for existing ``from CDE_Schema.LLM_Classification import ...``
call sites (enums, dataclasses, and pydantic models). Removed at cde_analyzer 2.0.0.
"""

from cde_lib.schema.LLM_Classification import *  # noqa: F401,F403
