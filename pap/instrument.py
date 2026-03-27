"""PAP instrumentation wrapper for _safe_call.

This module provides pap_safe_call() which wraps the existing _safe_call()
with PAP instrumentation. It extracts tool-specific events from the
function parameters and results.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from .config import PAPConfig
from .context import PAPContext


# Event extraction rules: map tool names to input/output event generators
_INPUT_EVENT_MAP = {
    "patent_search": lambda p: ("search.query_submit", {
        "query": p.get("query"), "jurisdiction": p.get("jurisdiction"),
        "cpc_codes": p.get("cpc_codes"), "applicant": p.get("applicant"),
        "date_from": p.get("date_from"), "date_to": p.get("date_to"),
    }),
    "fto_analysis": lambda p: ("analysis.fto_submit", {
        "text": (p.get("text") or "")[:200], "cpc_codes": p.get("cpc_codes"),
        "target_jurisdiction": p.get("target_jurisdiction"),
    }),
    "tech_landscape": lambda p: ("analysis.landscape_submit", {
        "cpc_prefix": p.get("cpc_prefix"), "query": p.get("query"),
        "date_from": p.get("date_from"), "date_to": p.get("date_to"),
    }),
    "firm_patent_portfolio": lambda p: ("analysis.portfolio_submit", {
        "firm": p.get("firm"), "date": p.get("date"),
    }),
    "patent_valuation": lambda p: ("valuation.submit", {
        "query": p.get("query"), "query_type": p.get("query_type"),
        "purpose": p.get("purpose"),
    }),
    "bayesian_scenario": lambda p: ("valuation.scenario_submit", {
        "query": p.get("query"), "scenario_type": p.get("scenario_type"),
    }),
    "patent_option_value": lambda p: ("valuation.option_submit", {
        "query": p.get("query"),
    }),
    "portfolio_var": lambda p: ("valuation.var_submit", {
        "query": p.get("query"), "confidence": p.get("confidence"),
    }),
    "adversarial_strategy": lambda p: ("analysis.adversarial_submit", {
        "firm_a": p.get("firm_a"), "firm_b": p.get("firm_b"),
    }),
    "startability": lambda p: ("analysis.startability_submit", {
        "firm_query": p.get("firm_query"),
        "tech_query_or_cluster_id": p.get("tech_query_or_cluster_id"),
    }),
    "cross_domain_discovery": lambda p: ("expansion.cross_domain_submit", {
        "query": p.get("query"),
    }),
    "citation_network": lambda p: ("expansion.citation_submit", {
        "query": p.get("query"),
    }),
    "tech_trend": lambda p: ("analysis.trend_submit", {
        "cpc_code": p.get("cpc_code"),
    }),
}

_OUTPUT_EVENT_MAP = {
    "patent_search": lambda r: ("search.results_returned", {
        "result_count": r.get("result_count", 0),
        "total_count": r.get("total_count", 0),
        "top_patent_ids": [p.get("publication_number", "") for p in (r.get("patents") or [])[:5]],
    }),
    "fto_analysis": lambda r: ("analysis.fto_result", {
        "risk_level": r.get("risk_assessment", {}).get("overall_risk"),
        "blocking_count": len(r.get("blocking_patents", [])),
    }),
    "tech_landscape": lambda r: ("analysis.landscape_result", {
        "total_patents": r.get("total_patents", 0),
        "top_applicant_count": len(r.get("top_applicants", [])),
    }),
    "patent_valuation": lambda r: ("valuation.result", {
        "value_tier": r.get("value_tier"),
        "overall_score": r.get("overall_score"),
    }),
    "bayesian_scenario": lambda r: ("valuation.scenario_result", {
        "scenarios_count": len(r.get("scenarios", [])),
    }),
}


def extract_input_params(tool_name: str, kwargs: dict) -> dict:
    """Extract relevant parameters from tool kwargs for logging."""
    # Remove internal params
    clean = {k: v for k, v in kwargs.items() if not k.startswith("_") and k != "store"}
    return clean


def pap_wrap_call(
    config: PAPConfig,
    original_safe_call: Callable,
    fn: Callable,
    *args,
    _tool_name: str | None = None,
    _timeout: int = 120,
    **kwargs,
) -> tuple[Any, PAPContext | None]:
    """Wrap a tool call with PAP instrumentation.
    
    Returns:
        (result, pap_context) — context is None if PAP is disabled
    """
    if not config.enabled or not _tool_name:
        result = original_safe_call(fn, *args, _tool_name=_tool_name, _timeout=_timeout, **kwargs)
        return result, None

    params = extract_input_params(_tool_name, kwargs)
    ctx = PAPContext(config, _tool_name, params)

    with ctx:
        # Log input event
        if _tool_name in _INPUT_EVENT_MAP:
            etype, epayload = _INPUT_EVENT_MAP[_tool_name](params)
            ctx.log_event(etype, _tool_name, epayload)
        else:
            ctx.log_event("tool.input", _tool_name, {"params_keys": list(params.keys())})

        # Execute the actual tool call
        t0 = time.time()
        result = original_safe_call(fn, *args, _tool_name=_tool_name, _timeout=_timeout, **kwargs)
        call_duration = time.time() - t0

        # Log execution timing
        ctx.log_event("tool.execution", _tool_name, {
            "duration_seconds": round(call_duration, 4),
            "has_error": isinstance(result, dict) and "error" in result,
        })

        # Log output event
        if isinstance(result, dict) and "error" not in result:
            if _tool_name in _OUTPUT_EVENT_MAP:
                etype, epayload = _OUTPUT_EVENT_MAP[_tool_name](result)
                ctx.log_event(etype, _tool_name, epayload)
            else:
                ctx.log_event("tool.output", _tool_name, {
                    "result_keys": list(result.keys()) if isinstance(result, dict) else ["non_dict"],
                })

        # Bind artifact
        ctx.bind_artifact(result)

    # Attach proof summary to result (non-invasive)
    if isinstance(result, dict) and ctx.proof:
        result["_pap_proof"] = {
            "proof_id": ctx.proof.proof_id,
            "task_id": ctx.proof.task_id,
            "pap_level": ctx.proof.pap_level,
            "cmd_hash": ctx.proof.cmd_hash[:16] + "...",
            "log_commitment": ctx.proof.log_commitment[:16] + "...",
            "artifact_hash": ctx.proof.artifact_hash[:16] + "...",
            "event_count": ctx.proof.log_event_count,
            "proof_size_bytes": ctx.proof.size_bytes(),
            "log_size_bytes": ctx.proof.log_size_bytes,
            "duration_seconds": ctx.proof.duration_seconds,
        }
        if ctx.proof.pap_level >= 2:  # Level 1
            result["_pap_proof"]["nonce"] = ctx.proof.nonce[:16] + "..."
            result["_pap_proof"]["generator_sig"] = ctx.proof.generator_sig[:16] + "..."

    return result, ctx
