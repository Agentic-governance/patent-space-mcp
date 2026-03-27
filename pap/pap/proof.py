"""PAP proof object generation and verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from .chain import HashChain
from .config import PAPConfig, PAPLevel


@dataclass
class PAPProof:
    """Provenance attestation proof object."""
    # Core identifiers
    proof_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    task_id: str = ""
    pap_level: int = 0

    # Command binding
    cmd_hash: str = ""           # SHA-256 of the command/request

    # Log binding
    log_commitment: str = ""     # SHA-256 over concatenated event hashes
    log_event_count: int = 0
    log_size_bytes: int = 0

    # Artifact binding
    artifact_hash: str = ""      # SHA-256 of the final output artifact

    # Freshness (Level 1)
    nonce: str = ""              # Random nonce for replay prevention
    timestamp: float = field(default_factory=time.time)

    # Signatures (Level 1)
    generator_sig: str = ""      # HMAC-SHA256 by generator
    verifier_sig: str = ""       # HMAC-SHA256 by verifier (cmd authorization)

    # Metadata
    generator_id: str = ""
    tool_names: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    # Serialized log (optional, for audit)
    log_payload: str = ""        # JSON serialized log (or reference)

    def to_dict(self) -> dict:
        return asdict(self)

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, default=str)

    def size_bytes(self) -> int:
        return len(self.serialize().encode("utf-8"))


def compute_cmd_hash(tool_name: str, params: dict[str, Any]) -> str:
    """Compute SHA-256 hash of the command (tool name + parameters)."""
    canonical = json.dumps({"tool": tool_name, "params": params}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_artifact_hash(artifact: Any) -> str:
    """Compute SHA-256 hash of the output artifact."""
    canonical = json.dumps(artifact, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sign_hmac(data: str, key: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_proof(
    config: PAPConfig,
    task_id: str,
    chain: HashChain,
    cmd_hash: str,
    artifact_hash: str,
    tool_names: list[str],
    duration: float,
    nonce: str = "",
    verifier_sig: str = "",
) -> PAPProof:
    """Generate a PAP proof object from a completed task."""
    proof = PAPProof(
        task_id=task_id,
        pap_level=int(config.level),
        cmd_hash=cmd_hash,
        log_commitment=chain.commitment(),
        log_event_count=chain.length,
        log_size_bytes=chain.size_bytes(),
        artifact_hash=artifact_hash,
        generator_id=config.server_id,
        tool_names=tool_names,
        duration_seconds=duration,
    )

    if config.level >= PAPLevel.LEVEL1:
        proof.nonce = nonce or secrets.token_hex(16)
        proof.timestamp = time.time()
        # Sign: cmd_hash + log_commitment + artifact_hash + nonce + timestamp
        sign_data = f"{proof.cmd_hash}|{proof.log_commitment}|{proof.artifact_hash}|{proof.nonce}|{proof.timestamp}"
        proof.generator_sig = sign_hmac(sign_data, config.generator_key)
        proof.verifier_sig = verifier_sig or sign_hmac(proof.cmd_hash, config.verifier_key)

    # Attach serialized log
    proof.log_payload = chain.serialize()

    return proof


def verify_proof(config: PAPConfig, proof: PAPProof) -> tuple[bool, list[str]]:
    """Verify a PAP proof object.
    
    Returns:
        (is_valid, list_of_issues)
    """
    issues = []

    # Basic checks
    if not proof.cmd_hash:
        issues.append("Missing cmd_hash")
    if not proof.log_commitment:
        issues.append("Missing log_commitment")
    if not proof.artifact_hash:
        issues.append("Missing artifact_hash")

    # Verify log chain if payload is present
    if proof.log_payload:
        try:
            events_data = json.loads(proof.log_payload)
            concat = "".join(e.get("event_hash", "") for e in events_data)
            recomputed_commitment = hashlib.sha256(concat.encode("utf-8")).hexdigest()
            if recomputed_commitment != proof.log_commitment:
                issues.append(f"Log commitment mismatch: expected {proof.log_commitment[:16]}..., got {recomputed_commitment[:16]}...")
        except json.JSONDecodeError:
            issues.append("Log payload is not valid JSON")

    # Level 1 checks
    if proof.pap_level >= int(PAPLevel.LEVEL1):
        if not proof.nonce:
            issues.append("Missing nonce (required for Level 1)")
        if not proof.generator_sig:
            issues.append("Missing generator signature (required for Level 1)")

        # Verify generator signature
        if proof.generator_sig:
            sign_data = f"{proof.cmd_hash}|{proof.log_commitment}|{proof.artifact_hash}|{proof.nonce}|{proof.timestamp}"
            expected_sig = sign_hmac(sign_data, config.generator_key)
            if proof.generator_sig != expected_sig:
                issues.append("Generator signature verification FAILED")

        # Verify verifier signature
        if proof.verifier_sig:
            expected_vsig = sign_hmac(proof.cmd_hash, config.verifier_key)
            if proof.verifier_sig != expected_vsig:
                issues.append("Verifier signature verification FAILED")

        # Freshness check (configurable window, default 1 hour)
        age = time.time() - proof.timestamp
        if age > 3600:
            issues.append(f"Proof is {age:.0f}s old (>{3600}s freshness window)")

    return len(issues) == 0, issues
