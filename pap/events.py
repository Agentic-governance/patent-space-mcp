"""Structured PAP event definitions and creation."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PAPEvent:
    """A single structured event in a PAP log."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_id: str = ""
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""          # e.g. "search.query_submit"
    event_category: str = ""      # search | expansion | analysis | valuation | artifact
    tool_name: str = ""
    payload: dict = field(default_factory=dict)
    prev_hash: str = ""           # Hash of previous event (for chain)
    event_hash: str = ""          # Hash of this event

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this event (excluding event_hash field)."""
        d = asdict(self)
        d.pop("event_hash", None)
        canonical = json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)
        self.event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.event_hash

    def to_dict(self) -> dict:
        return asdict(self)


def make_event(
    task_id: str,
    event_type: str,
    tool_name: str,
    payload: dict[str, Any],
    prev_hash: str = "",
    category: str | None = None,
) -> PAPEvent:
    """Create a structured PAP event."""
    if category is None:
        category = event_type.split(".")[0] if "." in event_type else "general"
    ev = PAPEvent(
        task_id=task_id,
        event_type=event_type,
        event_category=category,
        tool_name=tool_name,
        payload=payload,
        prev_hash=prev_hash,
    )
    ev.compute_hash()
    return ev
