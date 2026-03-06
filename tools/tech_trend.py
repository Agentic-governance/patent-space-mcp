"""tech_trend tool — time-series technology trend analysis.

Given a technology query (text, CPC code, or cluster_id), returns
year-by-year filing trends, growth rates, new entrant detection,
and emerging sub-areas. Uses tech_cluster_momentum + startability_surface.
"""
from __future__ import annotations

import json
from typing import Any

from db.sqlite_store import PatentStore
from entity.resolver import EntityResolver
from tools.cpc_labels_ja import CPC_CLASS_JA


def _match_clusters(conn, query: str, top_n: int = 10) -> list[dict]:
    """Match query to relevant tech clusters by CPC or label."""
    q = (query or "").strip()
    if not q:
        return []

    results = []

    # Try exact cluster_id match
    if "_" in q and len(q) <= 40:
        row = conn.execute(
            "SELECT cluster_id, label, cpc_class, patent_count "
            "FROM tech_clusters WHERE cluster_id = ?", (q,)
        ).fetchone()
        if row:
            results.append(dict(row))
            return results

    # Try CPC prefix match (e.g., "H01M" → H01M_0)
    q_upper = q.upper().replace("-", "").replace(" ", "")
    if len(q_upper) <= 8 and q_upper[:1].isalpha():
        rows = conn.execute(
            "SELECT cluster_id, label, cpc_class, patent_count "
            "FROM tech_clusters WHERE cpc_class LIKE ? ORDER BY patent_count DESC LIMIT ?",
            (f"{q_upper}%", top_n),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

    # Keyword → CPC mapping for common Japanese/English terms
    _KEYWORD_CPC = {
        "電池": "H01M", "バッテリー": "H01M", "battery": "H01M",
        "全固体電池": "H01M", "solid-state battery": "H01M", "固体電解質": "H01M",
        "リチウム": "H01M", "lithium": "H01M",
        "半導体": "H01L", "semiconductor": "H01L",
        "AI": "G06N", "人工知能": "G06N", "機械学習": "G06N", "machine learning": "G06N",
        "深層学習": "G06N", "deep learning": "G06N", "ニューラル": "G06N",
        "自動運転": "B60W", "autonomous": "B60W", "ADAS": "B60W",
        "ロボット": "B25J", "robot": "B25J",
        "5G": "H04W", "通信": "H04W", "wireless": "H04W",
        "量子": "G06N", "quantum": "G06N",
        "水素": "C01B", "hydrogen": "C01B", "燃料電池": "H01M",
        "有機EL": "H10K", "OLED": "H10K",
        "太陽電池": "H02S", "solar": "H02S",
        "医薬": "A61K", "pharmaceutical": "A61K", "drug": "A61K",
        "遺伝子": "C12N", "gene": "C12N", "CRISPR": "C12N",
        "ブロックチェーン": "G06Q", "blockchain": "G06Q",
        "3Dプリンタ": "B33Y", "additive manufacturing": "B33Y",
        "EV": "B60L", "電気自動車": "B60L", "electric vehicle": "B60L",
        "ドローン": "B64U", "drone": "B64U", "UAV": "B64U",
    }
    for keyword, cpc in _KEYWORD_CPC.items():
        if keyword.lower() in q.lower():
            rows = conn.execute(
                "SELECT cluster_id, label, cpc_class, patent_count "
                "FROM tech_clusters WHERE cpc_class = ? ORDER BY patent_count DESC LIMIT ?",
                (cpc, top_n),
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]

    # Fallback: LIKE search on label and top_terms
    like = f"%{q}%"
    rows = conn.execute(
        "SELECT cluster_id, label, cpc_class, patent_count "
        "FROM tech_clusters WHERE label LIKE ? OR cpc_class LIKE ? "
        "ORDER BY patent_count DESC LIMIT ?",
        (like, like, top_n),
    ).fetchall()
    return [dict(r) for r in rows]


def tech_trend(
    store: PatentStore,
    resolver: EntityResolver | None = None,
    query: str = "",
    cpc_prefix: str | None = None,
    year_from: int = 2016,
    year_to: int = 2024,
    top_n: int = 20,
) -> dict[str, Any]:
    """Analyze time-series trend for a technology area.

    Args:
        store: PatentStore instance.
        resolver: EntityResolver (optional).
        query: Technology query (text, CPC code, or cluster_id).
        cpc_prefix: Optional CPC prefix filter (e.g., "H01M").
        year_from: Start year (default: 2016).
        year_to: End year (default: 2024).
        top_n: Maximum clusters/firms to return (default: 20).

    Returns:
        Year-by-year filing trends, growth rates, new entrants, sub-area breakdown.
    """
    store._relax_timeout()
    conn = store._conn()

    # Resolve query to clusters
    effective_query = cpc_prefix or query
    if not effective_query:
        return {
            "error": "Either query or cpc_prefix is required.",
            "suggestion": "例: query='全固体電池' or cpc_prefix='H01M'",
        }

    clusters = _match_clusters(conn, effective_query, top_n=top_n)
    if not clusters:
        return {
            "error": f"No matching technology clusters for: '{effective_query}'",
            "suggestion": "Try a CPC code (e.g., 'H01M'), technology keyword, or cluster_id.",
        }

    cluster_ids = [c["cluster_id"] for c in clusters]

    # Auto-detect best year range
    best_row = conn.execute(
        "SELECT MIN(year) as y_min, MAX(year) as y_max FROM tech_cluster_momentum"
    ).fetchone()
    if best_row and best_row["y_max"]:
        actual_year_to = min(year_to, best_row["y_max"])
        actual_year_from = max(year_from, best_row["y_min"] or year_from)
    else:
        actual_year_to = year_to
        actual_year_from = year_from

    # Get year-by-year trend for matched clusters
    yearly_data: dict[int, dict] = {}
    placeholders = ",".join("?" for _ in cluster_ids)

    momentum_rows = conn.execute(
        f"SELECT cluster_id, year, growth_rate, acceleration, patent_count "
        f"FROM tech_cluster_momentum "
        f"WHERE cluster_id IN ({placeholders}) "
        f"AND year BETWEEN ? AND ? "
        f"ORDER BY year",
        (*cluster_ids, actual_year_from, actual_year_to),
    ).fetchall()

    for r in momentum_rows:
        y = r["year"]
        if y not in yearly_data:
            yearly_data[y] = {
                "year": y,
                "total_growth": 0.0,
                "total_acceleration": 0.0,
                "total_patent_count": 0,
                "cluster_count": 0,
            }
        yd = yearly_data[y]
        yd["total_growth"] += r["growth_rate"] or 0
        yd["total_acceleration"] += r["acceleration"] or 0
        yd["total_patent_count"] += r["patent_count"] or 0
        yd["cluster_count"] += 1

    # Compute averages
    timeline = []
    for y in sorted(yearly_data.keys()):
        yd = yearly_data[y]
        n = max(yd["cluster_count"], 1)
        timeline.append({
            "year": y,
            "avg_growth_rate": round(yd["total_growth"] / n, 4),
            "avg_acceleration": round(yd["total_acceleration"] / n, 4),
            "total_patent_count": yd["total_patent_count"],
            "clusters_measured": n,
        })

    # Get new entrants: firms with large startability delta
    new_entrants = []
    for cid in cluster_ids[:5]:  # Check top 5 clusters
        end_rows = conn.execute(
            "SELECT firm_id, score FROM startability_surface "
            "WHERE cluster_id = ? AND year = ? ORDER BY score DESC LIMIT 20",
            (cid, actual_year_to),
        ).fetchall()

        if end_rows:
            start_rows = conn.execute(
                "SELECT firm_id, score FROM startability_surface "
                "WHERE cluster_id = ? AND year = ?",
                (cid, actual_year_from),
            ).fetchall()
            start_map = {r["firm_id"]: r["score"] for r in start_rows}

            for e in end_rows:
                old_score = start_map.get(e["firm_id"], 0)
                delta = e["score"] - old_score
                if delta > 0.1:  # Significant entry
                    new_entrants.append({
                        "firm_id": e["firm_id"],
                        "cluster_id": cid,
                        "score_now": round(e["score"], 3),
                        "score_before": round(old_score, 3),
                        "delta": round(delta, 3),
                    })

    # Deduplicate by firm_id (keep highest delta)
    firm_best: dict[str, dict] = {}
    for ne in new_entrants:
        fid = ne["firm_id"]
        if fid not in firm_best or ne["delta"] > firm_best[fid]["delta"]:
            firm_best[fid] = ne
    new_entrants = sorted(firm_best.values(), key=lambda x: x["delta"], reverse=True)[:top_n]

    # Sub-area breakdown (by CPC class)
    sub_areas = []
    for c in clusters[:top_n]:
        cid = c["cluster_id"]
        cpc = c.get("cpc_class", cid[:4])
        # Get latest momentum
        mom = conn.execute(
            "SELECT growth_rate, acceleration FROM tech_cluster_momentum "
            "WHERE cluster_id = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()
        growth = (mom["growth_rate"] or 0) if mom else 0
        accel = (mom["acceleration"] or 0) if mom else 0

        sub_areas.append({
            "cluster_id": cid,
            "label": c.get("label", cid),
            "label_ja": CPC_CLASS_JA.get(cpc, ""),
            "cpc_class": cpc,
            "patent_count": c.get("patent_count", 0),
            "growth_rate": round(growth, 4),
            "acceleration": round(accel, 4),
            "status": "hot" if growth > 0.3 else ("growing" if growth > 0 else "declining"),
        })

    # Top firms in this technology
    top_firms = []
    for cid in cluster_ids[:3]:
        rows = conn.execute(
            "SELECT firm_id, score FROM startability_surface "
            "WHERE cluster_id = ? AND year = ? AND gate_open = 1 "
            "ORDER BY score DESC LIMIT 10",
            (cid, actual_year_to if actual_year_to <= (best_row["y_max"] if best_row and best_row["y_max"] else 2023) else 2023),
        ).fetchall()
        for r in rows:
            top_firms.append({
                "firm_id": r["firm_id"],
                "cluster_id": cid,
                "score": round(r["score"], 3),
            })

    # Deduplicate top_firms by firm_id (keep highest score)
    firm_score: dict[str, dict] = {}
    for tf in top_firms:
        fid = tf["firm_id"]
        if fid not in firm_score or tf["score"] > firm_score[fid]["score"]:
            firm_score[fid] = tf
    top_firms = sorted(firm_score.values(), key=lambda x: x["score"], reverse=True)[:top_n]

    # Compute overall trend summary
    if len(timeline) >= 2:
        first_growth = timeline[0]["avg_growth_rate"]
        last_growth = timeline[-1]["avg_growth_rate"]
        overall_trend = "accelerating" if last_growth > first_growth + 0.05 else (
            "decelerating" if last_growth < first_growth - 0.05 else "stable"
        )
    else:
        last_growth = timeline[0]["avg_growth_rate"] if timeline else 0
        overall_trend = "insufficient_data"

    primary_cpc = clusters[0].get("cpc_class", "") if clusters else ""

    return {
        "endpoint": "tech_trend",
        "query": effective_query,
        "matched_clusters": len(clusters),
        "primary_cpc": primary_cpc,
        "primary_label": clusters[0].get("label", "") if clusters else "",
        "label_ja": CPC_CLASS_JA.get(primary_cpc, ""),
        "year_range": {"from": actual_year_from, "to": actual_year_to},
        "timeline": timeline,
        "overall_trend": overall_trend,
        "latest_growth_rate": round(last_growth, 4) if timeline else None,
        "sub_areas": sub_areas,
        "top_firms": top_firms,
        "new_entrants": new_entrants,
        "summary": {
            "total_clusters": len(clusters),
            "hot_sub_areas": sum(1 for s in sub_areas if s["status"] == "hot"),
            "growing_sub_areas": sum(1 for s in sub_areas if s["status"] == "growing"),
            "declining_sub_areas": sum(1 for s in sub_areas if s["status"] == "declining"),
            "new_entrant_count": len(new_entrants),
            "top_firm_count": len(top_firms),
        },
        "visualization_hint": {
            "recommended_chart": "line_with_bar",
            "title": f"技術トレンド: {effective_query}",
            "axes": {
                "x": "timeline[].year",
                "y_line": "timeline[].avg_growth_rate",
                "y_bar": "timeline[].total_patent_count",
            },
        },
    }
