"""PAP task context — wraps a single tool call or multi-step workflow."""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .chain import HashChain
from .config import PAPConfig, PAPLevel
from .proof import PAPProof, compute_artifact_hash, compute_cmd_hash, generate_proof


class PAPContext:
    """Context manager for a PAP-instrumented task.
    
    Usage:
        config = PAPConfig()
        with PAPContext(config, "patent_search", {"query": "電池"}) as ctx:
            result = do_tool_call(...)
            ctx.log_event("search.query_submit", "patent_search", {"query": "電池"})
            ctx.log_event("search.results_returned", "patent_search", {"count": 42})
            ctx.bind_artifact(result)
        proof = ctx.proof  # PAPProof object
    """

    def __init__(self, config: PAPConfig, tool_name: str, params: dict[str, Any]) -> None:
        self.config = config
        self.task_id = uuid.uuid4().hex[:16]
        self.tool_name = tool_name
        self.params = params
        self.chain = HashChain(self.task_id)
        self.cmd_hash = compute_cmd_hash(tool_name, params)
        self.artifact_hash = ""
        self.proof: PAPProof | None = None
        self._start_time = 0.0
        self._end_time = 0.0
        self._tool_names: list[str] = [tool_name]
        self._nonce = ""
        self._verifier_sig = ""

        if config.level >= PAPLevel.LEVEL1:
            import secrets
            self._nonce = secrets.token_hex(16)
            from .proof import sign_hmac
            self._verifier_sig = sign_hmac(self.cmd_hash, config.verifier_key)

    def __enter__(self) -> PAPContext:
        self._start_time = time.time()
        # Log task start event
        if self.config.enabled:
            start_payload = {
                "tool": self.tool_name,
                "params_hash": self.cmd_hash,
                "pap_level": int(self.config.level),
            }
            if self.config.level >= PAPLevel.LEVEL1:
                start_payload["nonce"] = self._nonce
                start_payload["verifier_sig"] = self._verifier_sig[:32] + "..."
            if self.config.hash_chain:
                self.chain.append("task.start", self.tool_name, start_payload)
            # For ADHOC level, still record but without chain
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._end_time = time.time()
        duration = self._end_time - self._start_time

        if not self.config.enabled:
            return

        # Log task end
        end_payload = {
            "duration_seconds": round(duration, 4),
            "artifact_hash": self.artifact_hash,
            "event_count": self.chain.length,
            "error": str(exc_val) if exc_val else None,
        }
        if self.config.hash_chain:
            self.chain.append("task.end", self.tool_name, end_payload)

        # Generate proof
        self.proof = generate_proof(
            config=self.config,
            task_id=self.task_id,
            chain=self.chain,
            cmd_hash=self.cmd_hash,
            artifact_hash=self.artifact_hash,
            tool_names=self._tool_names,
            duration=duration,
            nonce=self._nonce,
            verifier_sig=self._verifier_sig,
        )

        # Persist log to disk
        self._persist_log()

    def log_event(self, event_type: str, tool_name: str, payload: dict[str, Any]) -> None:
        """Log a structured event."""
        if not self.config.enabled:
            return
        if tool_name not in self._tool_names:
            self._tool_names.append(tool_name)
        if self.config.hash_chain:
            self.chain.append(event_type, tool_name, payload)

    def bind_artifact(self, artifact: Any) -> str:
        """Compute and bind artifact hash."""
        self.artifact_hash = compute_artifact_hash(artifact)
        if self.config.enabled and self.config.hash_chain:
            self.chain.append("artifact.bind", self.tool_name, {
                "artifact_hash": self.artifact_hash,
            })
        return self.artifact_hash

    def _persist_log(self) -> None:
        """Write log and proof to disk."""
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Write event log
        log_path = log_dir / f"{self.task_id}_log.jsonl"
        with open(log_path, "w") as f:
            for ev in self.chain.events:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False, default=str) + "\n")

        # Write proof
        if self.proof:
            proof_path = log_dir / f"{self.task_id}_proof.json"
            with open(proof_path, "w") as f:
                json.dump(self.proof.to_dict(), f, ensure_ascii=False, indent=2, default=str)
