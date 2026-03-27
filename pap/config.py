"""PAP configuration and feature flags."""
from __future__ import annotations

import os
from enum import IntEnum


class PAPLevel(IntEnum):
    """PAP assurance levels."""
    DISABLED = -1   # B0: No PAP
    ADHOC = 0       # B1: Ad-hoc logging (no hash chain, no artifact binding)
    LEVEL0 = 1      # B2: Hash-chained log + artifact binding
    LEVEL1 = 2      # B3: Level 0 + signatures + nonce + freshness


class PAPConfig:
    """Runtime PAP configuration from environment variables."""

    def __init__(self) -> None:
        self.level = PAPLevel(int(os.environ.get("PAP_LEVEL", "-1")))
        self.generator_key = os.environ.get("PAP_GENERATOR_KEY", "patent-space-mcp-dev-key")
        self.verifier_key = os.environ.get("PAP_VERIFIER_KEY", "verifier-dev-key")
        self.log_dir = os.environ.get("PAP_LOG_DIR", "/tmp/pap_logs")
        self.server_id = "patent-space-mcp-v0.3.0"

    @property
    def enabled(self) -> bool:
        return self.level >= PAPLevel.ADHOC

    @property
    def hash_chain(self) -> bool:
        return self.level >= PAPLevel.LEVEL0

    @property
    def signatures(self) -> bool:
        return self.level >= PAPLevel.LEVEL1
