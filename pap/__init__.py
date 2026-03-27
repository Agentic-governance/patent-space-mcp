"""PAP — Provenance Attestation Protocol for Patent Space MCP.

Minimal prototype implementing Level 0 and Level 1 provenance attestation.
Feature-flagged: zero overhead when PAP_ENABLED is not set.
"""
from .config import PAPConfig, PAPLevel
from .context import PAPContext

__all__ = ["PAPConfig", "PAPLevel", "PAPContext"]
