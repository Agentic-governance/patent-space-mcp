"""Hash-chained event log for PAP Level 0+."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .events import PAPEvent, make_event


class HashChain:
    """Append-only hash-chained event log.
    
    Each event's prev_hash points to the hash of the previous event,
    forming a tamper-evident chain. Any modification to an intermediate
    event invalidates all subsequent hashes.
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.events: list[PAPEvent] = []
        self._head_hash = hashlib.sha256(b"PAP_GENESIS").hexdigest()

    def append(
        self,
        event_type: str,
        tool_name: str,
        payload: dict[str, Any],
        category: str | None = None,
    ) -> PAPEvent:
        """Append an event to the chain."""
        ev = make_event(
            task_id=self.task_id,
            event_type=event_type,
            tool_name=tool_name,
            payload=payload,
            prev_hash=self._head_hash,
            category=category,
        )
        self.events.append(ev)
        self._head_hash = ev.event_hash
        return ev

    @property
    def head_hash(self) -> str:
        return self._head_hash

    @property
    def length(self) -> int:
        return len(self.events)

    def commitment(self) -> str:
        """Compute log commitment: SHA-256 over concatenated event hashes."""
        concat = "".join(ev.event_hash for ev in self.events)
        return hashlib.sha256(concat.encode("utf-8")).hexdigest()

    def verify_chain(self) -> tuple[bool, str]:
        """Verify the integrity of the hash chain.
        
        Returns:
            (is_valid, error_message)
        """
        expected_prev = hashlib.sha256(b"PAP_GENESIS").hexdigest()
        for i, ev in enumerate(self.events):
            if ev.prev_hash != expected_prev:
                return False, f"Chain break at event {i}: expected prev_hash={expected_prev[:16]}..., got {ev.prev_hash[:16]}..."
            # Recompute event hash
            recomputed = ev.compute_hash()
            if recomputed != ev.event_hash:
                return False, f"Hash mismatch at event {i}: stored={ev.event_hash[:16]}..., recomputed={recomputed[:16]}..."
            expected_prev = ev.event_hash
        return True, "Chain integrity verified"

    def to_list(self) -> list[dict]:
        return [ev.to_dict() for ev in self.events]

    def serialize(self) -> str:
        return json.dumps(self.to_list(), ensure_ascii=False, default=str)

    def size_bytes(self) -> int:
        return len(self.serialize().encode("utf-8"))
