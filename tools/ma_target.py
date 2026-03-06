"""ma_target tool — M&A target recommendation engine.

Three strategies:
- tech_gap: Find firms strong where acquirer is weak (complementary)
- consolidation: Find firms with highest overlap (market power)
- diversification: Find firms in unrelated CPC sections (new markets)

Uses startability_surface, firm_tech_vectors, and tech_clusters.
"""
from __future__ import annotations

import math
import struct
from typing import Any

from db.sqlite_store import PatentStore
from entity.resolver import EntityResolver
from tools.cpc_labels_ja import CPC_CLASS_JA


def _unpack_vec(blob: bytes | None) -> list[float] | None:
    """Unpack tech_vector BLOB to list of floats (64 doubles)."""
    if not blob or len(blob) < 8:
        return None
    n = len(blob) // 8
    if n > 0 and len(blob) % 8 == 0:
        try:
            return list(struct.unpack(f"{n}d", blob))
        except struct.error:
            pass
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return dot / (na * nb)


def _get_firm_clusters(conn, firm_id: str, year: int, limit: int = 50) -> list[dict]:
    """Get firm's top clusters from startability_surface."""
    rows = conn.execute(
        "SELECT cluster_id, score, gate_open, phi_tech_cos "
        "FROM startability_surface "
        "WHERE firm_id = ? AND year = ? "
        "ORDER BY score DESC LIMIT ?",
        (firm_id, year, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _find_best_year(conn, firm_id: str) -> int:
    """Find the year with most data for this firm."""
    row = conn.execute(
        "SELECT year, COUNT(*) as cnt FROM startability_surface "
        "WHERE firm_id = ? GROUP BY year ORDER BY cnt DESC LIMIT 1",
        (firm_id,),
    ).fetchone()
    return row["year"] if row else 2023


def _get_firm_sections(conn, firm_id: str, year: int) -> set[str]:
    """Get CPC sections (1-letter) where firm has strong presence."""
    rows = conn.execute(
        "SELECT cluster_id, score FROM startability_surface "
        "WHERE firm_id = ? AND year = ? AND gate_open = 1 "
        "ORDER BY score DESC LIMIT 30",
        (firm_id, year),
    ).fetchall()
    section_scores: dict[str, float] = {}
    for r in rows:
        section = r["cluster_id"][0] if r["cluster_id"] else ""
        if section:
            section_scores[section] = section_scores.get(section, 0) + r["score"]
    if not section_scores:
        return set()
    max_score = max(section_scores.values())
    return {s for s, v in section_scores.items() if v >= max_score * 0.15}


def _score_tech_gap_target(
    acquirer_clusters: dict[str, float],
    target_clusters: list[dict],
    acquirer_weak: set[str],
) -> float:
    """Score a target for tech_gap strategy: how well it fills acquirer's gaps."""
    fill_score = 0.0
    for tc in target_clusters:
        cid = tc["cluster_id"]
        target_score = tc["score"]
        if cid in acquirer_weak:
            # Target is strong where acquirer is weak
            fill_score += target_score * (1.0 - acquirer_clusters.get(cid, 0))
        elif cid not in acquirer_clusters:
            # Target has capability acquirer completely lacks
            fill_score += target_score * 0.5
    return fill_score


def _score_consolidation_target(
    acquirer_clusters: dict[str, float],
    target_clusters: list[dict],
) -> float:
    """Score a target for consolidation: maximize overlap (market power)."""
    overlap_score = 0.0
    for tc in target_clusters:
        cid = tc["cluster_id"]
        if cid in acquirer_clusters:
            # Both firms have this cluster — combined strength
            overlap_score += tc["score"] * acquirer_clusters[cid]
    return overlap_score


def _score_diversification_target(
    acquirer_sections: set[str],
    target_clusters: list[dict],
) -> float:
    """Score a target for diversification: different CPC sections."""
    div_score = 0.0
    for tc in target_clusters:
        section = tc["cluster_id"][0] if tc["cluster_id"] else ""
        if section and section not in acquirer_sections:
            div_score += tc["score"]
    return div_score


def ma_target(
    store: PatentStore,
    resolver: EntityResolver,
    acquirer: str,
    strategy: str = "tech_gap",
    top_n: int = 10,
    year: int = 2024,
) -> dict[str, Any]:
    """Recommend M&A targets based on patent portfolio analysis.

    Args:
        store: PatentStore instance.
        resolver: EntityResolver.
        acquirer: Acquiring company name or ticker.
        strategy: "tech_gap" (complementary), "consolidation" (overlap),
                  or "diversification" (new markets).
        top_n: Number of targets to return (default: 10).
        year: Analysis year (default: 2024).

    Returns:
        Ranked list of acquisition targets with synergy scores and rationale.
    """
    store._relax_timeout()

    if strategy not in {"tech_gap", "consolidation", "diversification"}:
        return {
            "error": f"Invalid strategy: '{strategy}'. Use 'tech_gap', 'consolidation', or 'diversification'.",
        }

    resolved = resolver.resolve(acquirer, country_hint="JP")
    if resolved is None:
        return {
            "error": f"Could not resolve acquirer: '{acquirer}'",
            "suggestion": "Try the exact company name, Japanese name, or stock ticker.",
        }

    acquirer_id = resolved.entity.canonical_id
    conn = store._conn()

    # Find best year for acquirer
    actual_year = _find_best_year(conn, acquirer_id)

    # Get acquirer's cluster profile
    acq_clusters_list = _get_firm_clusters(conn, acquirer_id, actual_year, limit=100)
    if not acq_clusters_list:
        return {
            "error": f"No patent portfolio data for '{acquirer_id}'",
            "suggestion": "This firm may not have enough patents for analysis.",
        }

    acquirer_map = {c["cluster_id"]: c["score"] for c in acq_clusters_list}
    acquirer_sections = _get_firm_sections(conn, acquirer_id, actual_year)

    # Identify acquirer's weak areas (clusters with low score)
    avg_score = sum(c["score"] for c in acq_clusters_list) / len(acq_clusters_list)
    weak_clusters = {c["cluster_id"] for c in acq_clusters_list if c["score"] < avg_score * 0.5}

    # Get tech vector for cosine similarity
    acq_vec_row = conn.execute(
        "SELECT tech_vector FROM firm_tech_vectors WHERE firm_id = ? AND year = ?",
        (acquirer_id, actual_year),
    ).fetchone()
    acq_vec = _unpack_vec(acq_vec_row["tech_vector"]) if acq_vec_row else None

    # Get all candidate firms
    candidate_rows = conn.execute(
        "SELECT DISTINCT firm_id FROM firm_tech_vectors WHERE year = ? AND firm_id != ?",
        (actual_year, acquirer_id),
    ).fetchall()
    candidate_ids = [r["firm_id"] for r in candidate_rows]

    # Score each candidate
    scored_targets = []
    for cand_id in candidate_ids:
        cand_clusters = _get_firm_clusters(conn, cand_id, actual_year, limit=50)
        if not cand_clusters:
            continue

        if strategy == "tech_gap":
            strat_score = _score_tech_gap_target(acquirer_map, cand_clusters, weak_clusters)
        elif strategy == "consolidation":
            strat_score = _score_consolidation_target(acquirer_map, cand_clusters)
        elif strategy == "diversification":
            strat_score = _score_diversification_target(acquirer_sections, cand_clusters)
        else:
            strat_score = 0.0

        if strat_score <= 0:
            continue

        # Tech vector similarity (useful for all strategies)
        cos_sim = 0.0
        cand_vec_row = conn.execute(
            "SELECT tech_vector, patent_count, dominant_cpc, tech_diversity "
            "FROM firm_tech_vectors WHERE firm_id = ? AND year = ?",
            (cand_id, actual_year),
        ).fetchone()
        if cand_vec_row:
            if acq_vec:
                cand_vec = _unpack_vec(cand_vec_row["tech_vector"])
                if cand_vec:
                    cos_sim = _cosine(acq_vec, cand_vec)

            scored_targets.append({
                "firm_id": cand_id,
                "strategy_score": round(strat_score, 4),
                "tech_similarity": round(cos_sim, 4),
                "patent_count": cand_vec_row["patent_count"] or 0,
                "dominant_cpc": cand_vec_row["dominant_cpc"] or "",
                "tech_diversity": round((cand_vec_row["tech_diversity"] or 0) / 5.0, 3),
            })

    # Sort by strategy score and normalize
    scored_targets.sort(key=lambda x: x["strategy_score"], reverse=True)
    top_targets = scored_targets[:top_n]

    # Normalize strategy_score to [0, 1] range based on max
    max_strat = max((t["strategy_score"] for t in top_targets), default=1.0) or 1.0
    for t in top_targets:
        t["strategy_score_raw"] = t["strategy_score"]
        t["strategy_score"] = round(t["strategy_score"] / max_strat, 4)

    # Enrich top targets with overlap/complementary analysis
    for target in top_targets:
        cand_id = target["firm_id"]
        cand_clusters = _get_firm_clusters(conn, cand_id, actual_year, limit=30)
        cand_cluster_ids = {c["cluster_id"] for c in cand_clusters}
        acq_cluster_ids = set(acquirer_map.keys())

        shared = acq_cluster_ids & cand_cluster_ids
        complementary = cand_cluster_ids - acq_cluster_ids
        acq_unique = acq_cluster_ids - cand_cluster_ids

        # Get labels for key clusters
        target["overlap_clusters"] = len(shared)
        target["complementary_clusters"] = len(complementary)
        target["acquirer_unique_clusters"] = len(acq_unique)

        # Top complementary areas (most valuable for acquirer)
        comp_details = []
        for cc in cand_clusters:
            if cc["cluster_id"] in complementary:
                cpc = cc["cluster_id"][:4]
                comp_details.append({
                    "cluster_id": cc["cluster_id"],
                    "label_ja": CPC_CLASS_JA.get(cpc, ""),
                    "score": round(cc["score"], 3),
                })
        comp_details.sort(key=lambda x: x["score"], reverse=True)
        target["top_complementary"] = comp_details[:5]

        # Synergy score: weighted combination
        if strategy == "tech_gap":
            synergy = 0.6 * target["strategy_score"] + 0.2 * len(complementary) / max(len(cand_cluster_ids), 1) + 0.2 * (1 - cos_sim)
        elif strategy == "consolidation":
            synergy = 0.5 * target["strategy_score"] + 0.3 * len(shared) / max(len(cand_cluster_ids), 1) + 0.2 * cos_sim
        else:  # diversification
            synergy = 0.5 * target["strategy_score"] + 0.3 * len(complementary) / max(len(cand_cluster_ids), 1) + 0.2 * target["tech_diversity"]

        target["synergy_score"] = round(min(synergy, 1.0), 4)

        # Generate rationale
        dom_cpc = target["dominant_cpc"]
        dom_label = CPC_CLASS_JA.get(dom_cpc[:4] if dom_cpc else "", "")
        if strategy == "tech_gap":
            target["rationale"] = (
                f"{dom_label}({dom_cpc})を中心に{len(complementary)}クラスタの"
                f"補完的技術を保有。買収により技術ギャップを埋める。"
            )
        elif strategy == "consolidation":
            target["rationale"] = (
                f"{len(shared)}クラスタで技術重複。統合により"
                f"市場支配力を強化。特に{dom_label}({dom_cpc})分野。"
            )
        else:
            target["rationale"] = (
                f"{dom_label}({dom_cpc})中心の異分野ポートフォリオ。"
                f"{len(complementary)}クラスタの新規事業領域を獲得可能。"
            )

    # Re-sort by synergy_score
    top_targets.sort(key=lambda x: x["synergy_score"], reverse=True)

    strategy_labels = {
        "tech_gap": "技術補完型 (Tech Gap Fill)",
        "consolidation": "統合強化型 (Market Consolidation)",
        "diversification": "多角化型 (Diversification)",
    }

    return {
        "endpoint": "ma_target",
        "acquirer": acquirer_id,
        "strategy": strategy,
        "strategy_label": strategy_labels.get(strategy, strategy),
        "year": actual_year,
        "acquirer_profile": {
            "total_clusters": len(acq_clusters_list),
            "dominant_sections": sorted(acquirer_sections),
            "weak_cluster_count": len(weak_clusters),
            "avg_score": round(avg_score, 4),
        },
        "total_candidates_screened": len(candidate_ids),
        "results": top_targets,
        "result_count": len(top_targets),
        "summary": {
            "avg_synergy": round(
                sum(t["synergy_score"] for t in top_targets) / len(top_targets), 4
            ) if top_targets else 0,
            "avg_complementary": round(
                sum(t["complementary_clusters"] for t in top_targets) / len(top_targets), 1
            ) if top_targets else 0,
            "top_target": top_targets[0]["firm_id"] if top_targets else None,
        },
        "disclaimer": (
            "本分析は特許ポートフォリオデータに基づく参考情報です。"
            "実際のM&A判断には財務・法務・市場分析等の総合的デューデリジェンスが必要です。"
        ),
        "visualization_hint": {
            "recommended_chart": "scatter",
            "title": f"M&Aターゲット分析: {acquirer_id} ({strategy_labels.get(strategy, '')})",
            "axes": {
                "x": "results[].tech_similarity",
                "y": "results[].synergy_score",
                "size": "results[].patent_count",
                "label": "results[].firm_id",
            },
        },
    }
