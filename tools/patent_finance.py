"""Patent finance tools — Black-Scholes option valuation, volatility,
VaR, and CAPM-style tech beta.

Uses pre-computed tables (tech_cluster_momentum, firm_tech_vectors,
startability_surface, citation_counts) to avoid full patents table scans.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.stats import norm

from db.sqlite_store import PatentStore
from entity.resolver import EntityResolver
from tools.cpc_labels_ja import CPC_CLASS_JA


# ─── helpers ─────────────────────────────────────────────────────────

def _resolve_firm(resolver: EntityResolver, name: str) -> str | None:
    res = resolver.resolve(name, country_hint="JP")
    return res.entity.canonical_id if res else None


def _cpc4(code: str) -> str:
    """Extract 4-char CPC class from a code like 'H01M10/052'."""
    return code[:4] if code else ""


def _get_yearly_counts_from_momentum(conn, cluster_ids: list[str],
                                      year_from: int, year_to: int) -> dict[int, int]:
    """Aggregate yearly patent counts from tech_cluster_momentum."""
    if not cluster_ids:
        return {}
    ph = ",".join("?" for _ in cluster_ids)
    rows = conn.execute(
        f"SELECT year, SUM(patent_count) as total "
        f"FROM tech_cluster_momentum "
        f"WHERE cluster_id IN ({ph}) AND year BETWEEN ? AND ? "
        f"GROUP BY year ORDER BY year",
        (*cluster_ids, year_from, year_to),
    ).fetchall()
    return {r["year"]: r["total"] for r in rows}


def _get_total_market_counts(conn, year_from: int, year_to: int) -> dict[int, int]:
    """Total patent filings across all clusters per year."""
    rows = conn.execute(
        "SELECT year, SUM(patent_count) as total "
        "FROM tech_cluster_momentum "
        "WHERE year BETWEEN ? AND ? "
        "GROUP BY year ORDER BY year",
        (year_from, year_to),
    ).fetchall()
    return {r["year"]: r["total"] for r in rows}


def _log_returns(counts: dict[int, int]) -> list[float]:
    """Compute log returns from year-to-year counts."""
    years = sorted(counts.keys())
    returns = []
    for i in range(1, len(years)):
        c0 = counts[years[i - 1]]
        c1 = counts[years[i]]
        if c0 > 0 and c1 > 0:
            returns.append(math.log(c1 / c0))
    return returns


def _find_clusters_for_cpc(conn, cpc_prefix: str, limit: int = 20) -> list[str]:
    """Find cluster_ids matching a CPC prefix."""
    rows = conn.execute(
        "SELECT cluster_id FROM tech_clusters "
        "WHERE cpc_class LIKE ? ORDER BY patent_count DESC LIMIT ?",
        (f"{cpc_prefix}%", limit),
    ).fetchall()
    return [r["cluster_id"] for r in rows]


def _find_best_year(conn, firm_id: str) -> int:
    row = conn.execute(
        "SELECT year, COUNT(*) as cnt FROM startability_surface "
        "WHERE firm_id = ? GROUP BY year ORDER BY cnt DESC LIMIT 1",
        (firm_id,),
    ).fetchone()
    return row["year"] if row else 2024


# ─── Black-Scholes helpers ──────────────────────────────────────────

def _black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> dict:
    """Compute Black-Scholes call option value and Greeks."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"value": 0, "delta": 0, "theta": 0, "vega": 0, "d1": 0, "d2": 0}

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    C = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    delta = norm.cdf(d1)
    theta = -(S * norm.pdf(d1) * sigma) / (2 * sqrt_T) - r * K * math.exp(-r * T) * norm.cdf(d2)
    vega = S * sqrt_T * norm.pdf(d1)

    return {
        "value": round(C, 4),
        "delta": round(delta, 4),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "d1": round(d1, 4),
        "d2": round(d2, 4),
    }


# ─── Tool 1: patent_option_value ────────────────────────────────────

def patent_option_value(
    store: PatentStore,
    resolver: EntityResolver,
    query: str,
    query_type: str | None = None,
    S: float | None = None,
    K: float | None = None,
    risk_free_rate: float = 0.02,
    year: int = 2024,
) -> dict[str, Any]:
    """Black-Scholes real option valuation for patents."""
    store._relax_timeout()
    conn = store._conn()

    # Auto-detect query_type
    if query_type is None:
        q = query.strip().upper()
        if q.startswith("JP-") or q.startswith("US-") or q.startswith("EP-"):
            query_type = "patent"
        elif len(q) <= 8 and q[:1].isalpha() and q[1:3].isdigit():
            query_type = "technology"
        else:
            query_type = "firm"

    if query_type == "patent":
        return _option_value_patent(conn, query, S, K, risk_free_rate, year)
    elif query_type == "technology":
        return _option_value_technology(conn, query, S, K, risk_free_rate, year)
    elif query_type == "firm":
        firm_id = _resolve_firm(resolver, query)
        if not firm_id:
            return {"error": f"Could not resolve firm: '{query}'"}
        return _option_value_firm(conn, firm_id, S, K, risk_free_rate, year)
    else:
        return {"error": f"Invalid query_type: '{query_type}'"}


def _get_cpc_volatility(conn, cpc_prefix: str) -> float:
    """Get volatility of a CPC area from tech_cluster_momentum."""
    cluster_ids = _find_clusters_for_cpc(conn, cpc_prefix)
    if not cluster_ids:
        return 0.3  # default
    counts = _get_yearly_counts_from_momentum(conn, cluster_ids, 2016, 2024)
    if len(counts) < 3:
        return 0.3
    returns = _log_returns(counts)
    if not returns:
        return 0.3
    return max(0.05, float(np.std(returns)))


def _estimate_S_K(conn, cpc_prefix: str, S_user: float | None, K_user: float | None) -> tuple[float, float, bool]:
    """Estimate or use user-provided S, K."""
    user_provided = S_user is not None and K_user is not None
    if user_provided:
        return S_user, K_user, True

    # Estimate from CPC filing density × royalty benchmark
    cluster_ids = _find_clusters_for_cpc(conn, cpc_prefix)
    total_patents = 0
    if cluster_ids:
        ph = ",".join("?" for _ in cluster_ids)
        row = conn.execute(
            f"SELECT SUM(patent_count) as total FROM tech_cluster_momentum "
            f"WHERE cluster_id IN ({ph}) AND year = (SELECT MAX(year) FROM tech_cluster_momentum)",
            cluster_ids,
        ).fetchone()
        total_patents = (row["total"] or 0) if row else 0

    # Royalty rates by CPC section
    _ROYALTY_RATES = {
        "H": 0.04, "G": 0.05, "B": 0.03, "C": 0.04,
        "A": 0.03, "F": 0.03, "E": 0.02, "D": 0.02,
    }
    section = cpc_prefix[0] if cpc_prefix else "H"
    royalty = _ROYALTY_RATES.get(section, 0.03)

    S_est = max(10.0, total_patents * royalty * 100 / max(total_patents, 1) * 100)
    K_est = S_est * 0.7

    return (
        S_user if S_user is not None else round(S_est, 2),
        K_user if K_user is not None else round(K_est, 2),
        user_provided,
    )


def _option_value_patent(conn, pub_num: str, S_user, K_user, r, year) -> dict:
    """Option value for a single patent."""
    pat = conn.execute(
        "SELECT publication_number, filing_date, title_ja, title_en, "
        "citation_count_forward FROM patents WHERE publication_number = ?",
        (pub_num,),
    ).fetchone()
    if not pat:
        return {"error": f"Patent not found: '{pub_num}'"}

    filing_date = pat["filing_date"]
    filing_year = int(str(filing_date)[:4]) if filing_date else year - 10
    T = max(0, 20 - (year - filing_year))
    if T <= 0:
        return {
            "endpoint": "patent_option_value",
            "patent": pub_num,
            "status": "expired",
            "remaining_years": 0,
            "option_value": 0,
            "interpretation": "この特許は既に満了しています。",
        }

    # Get primary CPC
    cpc_row = conn.execute(
        "SELECT cpc_code FROM patent_cpc WHERE publication_number = ? LIMIT 1",
        (pub_num,),
    ).fetchone()
    cpc = cpc_row["cpc_code"] if cpc_row else "H01M"
    cpc4 = _cpc4(cpc)

    sigma = _get_cpc_volatility(conn, cpc4)
    S, K, user_specified = _estimate_S_K(conn, cpc4, S_user, K_user)

    bs = _black_scholes_call(S, K, T, r, sigma)

    # Citation multiplier
    cited_by = pat["citation_count_forward"] or 0
    citation_mult = 1 + math.log(1 + cited_by) / 5
    adjusted_value = round(bs["value"] * citation_mult, 4)

    title = pat["title_ja"] or pat["title_en"] or ""

    result = {
        "endpoint": "patent_option_value",
        "query_type": "patent",
        "patent": pub_num,
        "title": title,
        "filing_year": filing_year,
        "remaining_years": T,
        "cpc": cpc,
        "cpc_label": CPC_CLASS_JA.get(cpc4, ""),
        "parameters": {
            "S": S, "K": K, "T": T, "r": r, "sigma": round(sigma, 4),
            "user_specified_S_K": user_specified,
        },
        "black_scholes": bs,
        "citation_multiplier": round(citation_mult, 4),
        "cited_by_count": cited_by,
        "adjusted_option_value": adjusted_value,
        "greeks": {
            "delta": bs["delta"],
            "theta": bs["theta"],
            "vega": bs["vega"],
        },
    }
    if not user_specified:
        result["note"] = (
            "S, Kは推定値を使用。実際の市場データがある場合はS, Kパラメータで指定可能。"
        )
    return result


def _option_value_firm(conn, firm_id: str, S_user, K_user, r, year) -> dict:
    """Portfolio option value for a firm."""
    actual_year = _find_best_year(conn, firm_id)

    # Get firm's top-cited patents (limit 1000 via citation_counts + patent_assignees)
    rows = conn.execute(
        "SELECT pa.publication_number, cc.forward_citations, p.filing_date "
        "FROM patent_assignees pa "
        "JOIN citation_counts cc ON pa.publication_number = cc.publication_number "
        "JOIN patents p ON pa.publication_number = p.publication_number "
        "WHERE pa.firm_id = ? "
        "ORDER BY cc.forward_citations DESC LIMIT 1000",
        (firm_id,),
    ).fetchall()

    if not rows:
        # Fallback: try without citation_counts
        rows = conn.execute(
            "SELECT pa.publication_number, p.citation_count_forward as forward_citations, p.filing_date "
            "FROM patent_assignees pa "
            "JOIN patents p ON pa.publication_number = p.publication_number "
            "WHERE pa.firm_id = ? "
            "ORDER BY p.citation_count_forward DESC LIMIT 500",
            (firm_id,),
        ).fetchall()

    if not rows:
        return {"error": f"No patents found for firm: '{firm_id}'"}

    # Get firm's dominant CPC from firm_tech_vectors
    ftv = conn.execute(
        "SELECT dominant_cpc, patent_count, tech_diversity FROM firm_tech_vectors "
        "WHERE firm_id = ? AND year = ?",
        (firm_id, actual_year),
    ).fetchone()
    dominant_cpc = (ftv["dominant_cpc"] or "H01M") if ftv else "H01M"
    total_patents = (ftv["patent_count"] or len(rows)) if ftv else len(rows)
    cpc4 = _cpc4(dominant_cpc)

    sigma = _get_cpc_volatility(conn, cpc4)
    S, K, user_specified = _estimate_S_K(conn, cpc4, S_user, K_user)

    # Calculate option value for each patent
    values = []
    cpc_breakdown = {}
    remaining_dist = {}
    top_patents = []

    for row in rows:
        fd = row["filing_date"]
        fy = int(str(fd)[:4]) if fd else year - 10
        T = max(0, 20 - (year - fy))
        cited_by = row["forward_citations"] or 0

        if T > 0:
            bs = _black_scholes_call(S, K, T, r, sigma)
            mult = 1 + math.log(1 + cited_by) / 5
            adj_val = bs["value"] * mult
        else:
            adj_val = 0
            bs = {"value": 0, "delta": 0}
            mult = 1

        values.append(adj_val)

        # Track remaining years distribution
        bucket = f"{max(0, T)}"
        remaining_dist[bucket] = remaining_dist.get(bucket, 0) + 1

        if len(top_patents) < 10 and adj_val > 0:
            top_patents.append({
                "patent": row["publication_number"],
                "option_value": round(adj_val, 2),
                "cited_by": cited_by,
                "remaining_years": T,
                "delta": bs["delta"],
            })

    # Extrapolate for remaining patents not in sample
    sample_avg = sum(values) / len(values) if values else 0
    extrapolated_total = sample_avg * total_patents

    # Get CPC distribution from startability_surface
    cpc_data = conn.execute(
        "SELECT cluster_id, score FROM startability_surface "
        "WHERE firm_id = ? AND year = ? ORDER BY score DESC LIMIT 20",
        (firm_id, actual_year),
    ).fetchall()
    cpc_dist = []
    for c in cpc_data:
        cid = c["cluster_id"]
        cp = _cpc4(cid)
        cpc_dist.append({
            "cpc": cp, "label": CPC_CLASS_JA.get(cp, ""),
            "score": round(c["score"], 3),
        })

    top_patents.sort(key=lambda x: x["option_value"], reverse=True)

    result = {
        "endpoint": "patent_option_value",
        "query_type": "firm",
        "firm_id": firm_id,
        "year": actual_year,
        "parameters": {
            "S": S, "K": K, "r": r, "sigma": round(sigma, 4),
            "user_specified_S_K": user_specified,
        },
        "portfolio_summary": {
            "total_patents": total_patents,
            "sample_size": len(rows),
            "sample_avg_option_value": round(sample_avg, 2),
            "portfolio_option_value": round(extrapolated_total, 2),
            "active_patents_in_sample": sum(1 for v in values if v > 0),
        },
        "top_value_patents": top_patents,
        "cpc_distribution": cpc_dist[:10],
        "remaining_years_distribution": {
            k: remaining_dist[k]
            for k in sorted(remaining_dist.keys(), key=lambda x: int(x))
        },
        "greeks_portfolio": {
            "avg_delta": round(np.mean([t["delta"] for t in top_patents]) if top_patents else 0, 4),
        },
    }
    if not user_specified:
        result["note"] = (
            "S, Kは推定値を使用。実際の市場データがある場合はS, Kパラメータで指定可能。"
        )
    return result


def _option_value_technology(conn, cpc_prefix: str, S_user, K_user, r, year) -> dict:
    """Option value for a technology area."""
    cpc_prefix = cpc_prefix.strip().upper()
    cluster_ids = _find_clusters_for_cpc(conn, cpc_prefix)
    cpc4 = _cpc4(cpc_prefix)

    sigma = _get_cpc_volatility(conn, cpc_prefix)
    S, K, user_specified = _estimate_S_K(conn, cpc_prefix, S_user, K_user)

    # Average T from filing trend
    counts = _get_yearly_counts_from_momentum(conn, cluster_ids, 2016, year)
    if counts:
        weighted_year = sum(y * c for y, c in counts.items()) / max(sum(counts.values()), 1)
        avg_T = max(1, 20 - (year - int(weighted_year)))
    else:
        avg_T = 10

    bs = _black_scholes_call(S, K, avg_T, r, sigma)

    # Top players
    top_firms = []
    if cluster_ids:
        for cid in cluster_ids[:3]:
            frows = conn.execute(
                "SELECT firm_id, score FROM startability_surface "
                "WHERE cluster_id = ? AND year = (SELECT MAX(year) FROM startability_surface WHERE cluster_id = ?) "
                "ORDER BY score DESC LIMIT 5",
                (cid, cid),
            ).fetchall()
            for fr in frows:
                top_firms.append({
                    "firm_id": fr["firm_id"],
                    "score": round(fr["score"], 3),
                })

    # Deduplicate
    seen = set()
    unique_firms = []
    for f in top_firms:
        if f["firm_id"] not in seen:
            seen.add(f["firm_id"])
            unique_firms.append(f)
    top_firms = unique_firms[:10]

    result = {
        "endpoint": "patent_option_value",
        "query_type": "technology",
        "cpc_prefix": cpc_prefix,
        "cpc_label": CPC_CLASS_JA.get(cpc4, ""),
        "parameters": {
            "S": S, "K": K, "T_avg": avg_T, "r": r, "sigma": round(sigma, 4),
            "user_specified_S_K": user_specified,
        },
        "technology_option_value": bs,
        "volatility": round(sigma, 4),
        "top_players": top_firms,
        "matched_clusters": len(cluster_ids),
    }
    if not user_specified:
        result["note"] = (
            "S, Kは推定値を使用。実際の市場データがある場合はS, Kパラメータで指定可能。"
        )
    return result


# ─── Tool 2: tech_volatility ────────────────────────────────────────

def tech_volatility(
    store: PatentStore,
    resolver: EntityResolver | None = None,
    query: str = "",
    query_type: str | None = None,
    date_from: str = "2015-01-01",
    date_to: str = "2024-12-31",
) -> dict[str, Any]:
    """Technology volatility + decay curve + half-life."""
    store._relax_timeout()
    conn = store._conn()

    year_from = int(date_from[:4])
    year_to = int(date_to[:4])
    q = query.strip()

    # Resolve query to CPC prefix
    if query_type == "firm" and resolver:
        firm_id = _resolve_firm(resolver, q)
        if not firm_id:
            return {"error": f"Could not resolve firm: '{q}'"}
        ftv = conn.execute(
            "SELECT dominant_cpc FROM firm_tech_vectors WHERE firm_id = ? ORDER BY year DESC LIMIT 1",
            (firm_id,),
        ).fetchone()
        cpc_prefix = (ftv["dominant_cpc"] or "H01M") if ftv else "H01M"
    else:
        cpc_prefix = q.upper().replace("-", "").replace(" ", "")
        if not cpc_prefix:
            return {"error": "query is required (CPC code or keyword)"}

    # Map keywords to CPC
    _KW_CPC = {
        "電池": "H01M", "バッテリー": "H01M", "battery": "H01M",
        "半導体": "H01L", "semiconductor": "H01L",
        "AI": "G06N", "人工知能": "G06N", "機械学習": "G06N",
        "自動運転": "B60W", "autonomous": "B60W",
        "EV": "B60L", "電気自動車": "B60L",
        "ロボット": "B25J", "robot": "B25J",
        "水素": "C01B", "hydrogen": "C01B",
        "医薬": "A61K", "pharmaceutical": "A61K",
        "5G": "H04W", "通信": "H04W",
    }
    for kw, cpc in _KW_CPC.items():
        if kw.lower() in q.lower():
            cpc_prefix = cpc
            break

    cpc4 = _cpc4(cpc_prefix)
    cluster_ids = _find_clusters_for_cpc(conn, cpc_prefix)

    # Get yearly counts
    counts = _get_yearly_counts_from_momentum(
        conn, cluster_ids if cluster_ids else [f"{cpc_prefix}_0"], year_from, year_to
    )
    if len(counts) < 3:
        return {
            "error": f"Insufficient data for '{cpc_prefix}' (need >=3 years)",
            "years_found": len(counts),
        }

    # Log returns
    returns = _log_returns(counts)
    sigma = float(np.std(returns)) if returns else 0
    drift = float(np.mean(returns)) if returns else 0
    tech_sharpe = drift / sigma if sigma > 1e-6 else 0

    if drift > 0.05:
        regime = "growth"
    elif drift > -0.05:
        regime = "mature"
    else:
        regime = "declining"

    # Decay curve from citation lag (sampled)
    decay_curve = []
    half_life = None
    if cluster_ids:
        # Sample citations for patents in this CPC area
        sample_rows = conn.execute(
            """SELECT
                CAST(SUBSTR(p2.filing_date, 1, 4) AS INTEGER) -
                CAST(SUBSTR(p1.filing_date, 1, 4) AS INTEGER) as lag
            FROM patent_citations pc
            JOIN patents p1 ON pc.cited_publication = p1.publication_number
            JOIN patents p2 ON pc.citing_publication = p2.publication_number
            JOIN patent_cpc cpc ON pc.cited_publication = cpc.publication_number
            WHERE cpc.cpc_code LIKE ?
            AND p1.filing_date IS NOT NULL AND p2.filing_date IS NOT NULL
            AND p1.filing_date > 0 AND p2.filing_date > 0
            LIMIT 10000""",
            (f"{cpc_prefix}%",),
        ).fetchall()

        if sample_rows:
            lags = [r["lag"] for r in sample_rows if r["lag"] is not None and 0 <= r["lag"] <= 30]
            if lags:
                # Build histogram
                from collections import Counter
                lag_counts = Counter(lags)
                max_lag = max(lag_counts.keys())
                total = sum(lag_counts.values())
                cumulative = 0
                for lag_yr in range(0, min(max_lag + 1, 25)):
                    c = lag_counts.get(lag_yr, 0)
                    cumulative += c
                    decay_curve.append({
                        "lag_years": lag_yr,
                        "citation_count": c,
                        "cumulative_pct": round(cumulative / total, 4),
                    })
                    if half_life is None and cumulative >= total * 0.5:
                        half_life = lag_yr

    # Timeline
    timeline = []
    years = sorted(counts.keys())
    for i, y in enumerate(years):
        entry = {"year": y, "patent_count": counts[y]}
        if i > 0 and counts[years[i - 1]] > 0:
            entry["log_return"] = round(math.log(counts[y] / counts[years[i - 1]]), 4)
        timeline.append(entry)

    # Percentile vs all technologies
    all_clusters = conn.execute(
        "SELECT cluster_id FROM tech_clusters LIMIT 500"
    ).fetchall()
    all_sigmas = []
    for ac in all_clusters:
        cid = ac["cluster_id"]
        ac_counts = _get_yearly_counts_from_momentum(conn, [cid], year_from, year_to)
        ac_returns = _log_returns(ac_counts)
        if ac_returns:
            all_sigmas.append(float(np.std(ac_returns)))

    percentile = 50
    if all_sigmas and sigma > 0:
        percentile = round(sum(1 for s in all_sigmas if s < sigma) / len(all_sigmas) * 100)

    return {
        "endpoint": "tech_volatility",
        "cpc_prefix": cpc_prefix,
        "cpc_label": CPC_CLASS_JA.get(cpc4, ""),
        "date_range": {"from": year_from, "to": year_to},
        "volatility": {
            "sigma": round(sigma, 4),
            "drift": round(drift, 4),
            "tech_sharpe": round(tech_sharpe, 4),
            "regime": regime,
            "percentile_vs_all": percentile,
        },
        "timeline": timeline,
        "decay_curve": decay_curve[:20],
        "half_life_years": half_life,
        "interpretation": (
            f"{CPC_CLASS_JA.get(cpc4, cpc_prefix)}のボラティリティσ={sigma:.3f}, "
            f"ドリフト={drift:.3f}。{regime}段階。"
            f"{'半減期' + str(half_life) + '年。' if half_life else ''}"
            f"全技術中{percentile}パーセンタイル。"
        ),
        "visualization_hint": {
            "recommended_chart": "dual_axis",
            "title": f"技術ボラティリティ: {cpc_prefix}",
            "axes": {
                "x": "timeline[].year",
                "y_left": "timeline[].patent_count",
                "y_right": "timeline[].log_return",
            },
        },
    }


# ─── Tool 3: portfolio_var ──────────────────────────────────────────

def portfolio_var(
    store: PatentStore,
    resolver: EntityResolver,
    firm: str,
    horizon_years: int = 5,
    confidence: float = 0.95,
    year: int = 2024,
) -> dict[str, Any]:
    """Portfolio VaR — patent expiration risk analysis."""
    store._relax_timeout()
    conn = store._conn()

    firm_id = _resolve_firm(resolver, firm)
    if not firm_id:
        return {"error": f"Could not resolve firm: '{firm}'"}

    actual_year = _find_best_year(conn, firm_id)

    # Get firm's patents with filing dates (limited sample)
    rows = conn.execute(
        "SELECT pa.publication_number, p.filing_date, p.citation_count_forward, "
        "       (SELECT cpc_code FROM patent_cpc WHERE publication_number = pa.publication_number LIMIT 1) as cpc "
        "FROM patent_assignees pa "
        "JOIN patents p ON pa.publication_number = p.publication_number "
        "WHERE pa.firm_id = ? AND p.filing_date IS NOT NULL AND p.filing_date > 0 "
        "ORDER BY p.citation_count_forward DESC "
        "LIMIT 2000",
        (firm_id,),
    ).fetchall()

    if not rows:
        return {"error": f"No patent data for firm: '{firm_id}'"}

    # Calculate remaining years for each patent
    expiring = []
    active_count = 0
    cpc_expiring: dict[str, int] = {}
    cpc_total: dict[str, int] = {}
    remaining_dist: dict[int, int] = {}

    for row in rows:
        fd = row["filing_date"]
        fy = int(str(fd)[:4]) if fd else year - 10
        remaining = max(0, 20 - (year - fy))
        cpc4 = _cpc4(row["cpc"] or "")

        bucket = min(remaining, 20)
        remaining_dist[bucket] = remaining_dist.get(bucket, 0) + 1

        if cpc4:
            cpc_total[cpc4] = cpc_total.get(cpc4, 0) + 1

        if remaining > 0:
            active_count += 1
            if remaining <= horizon_years:
                expiring.append({
                    "patent": row["publication_number"],
                    "remaining_years": remaining,
                    "cpc": cpc4,
                    "citations": row["citation_count_forward"] or 0,
                })
                if cpc4:
                    cpc_expiring[cpc4] = cpc_expiring.get(cpc4, 0) + 1

    # Get total patent count from firm_tech_vectors
    ftv = conn.execute(
        "SELECT patent_count FROM firm_tech_vectors WHERE firm_id = ? AND year = ?",
        (firm_id, actual_year),
    ).fetchone()
    total_count = (ftv["patent_count"] or len(rows)) if ftv else len(rows)
    expiring_count = len(expiring)
    expiring_pct = round(expiring_count / max(active_count, 1), 4)

    # CPC risk analysis
    var_at_risk_cpc = []
    for cpc4, exp_count in sorted(cpc_expiring.items(), key=lambda x: x[1], reverse=True)[:5]:
        total_in_cpc = cpc_total.get(cpc4, 1)
        loss_rate = round(exp_count / total_in_cpc, 3)

        # Check competitor threat from startability_surface
        competitors = []
        # Find matching cluster
        cluster_row = conn.execute(
            "SELECT cluster_id FROM tech_clusters WHERE cpc_class = ? LIMIT 1",
            (cpc4,),
        ).fetchone()
        if cluster_row:
            cid = cluster_row["cluster_id"]
            comp_rows = conn.execute(
                "SELECT firm_id, score FROM startability_surface "
                "WHERE cluster_id = ? AND year = ? AND firm_id != ? AND gate_open = 1 "
                "ORDER BY score DESC LIMIT 3",
                (cid, actual_year, firm_id),
            ).fetchall()
            competitors = [{"firm_id": r["firm_id"], "score": round(r["score"], 3)} for r in comp_rows]

        var_at_risk_cpc.append({
            "cpc": cpc4,
            "label": CPC_CLASS_JA.get(cpc4, ""),
            "expiring_count": exp_count,
            "total_in_cpc": total_in_cpc,
            "loss_rate": loss_rate,
            "competitors": competitors,
            "risk_level": "high" if loss_rate > 0.3 else ("medium" if loss_rate > 0.15 else "low"),
        })

    # VaR calculation using option values
    total_option_value_at_risk = 0
    dominant_cpc_prefix = var_at_risk_cpc[0]["cpc"] if var_at_risk_cpc else "H01M"
    sigma = _get_cpc_volatility(conn, dominant_cpc_prefix)

    for exp in expiring[:500]:
        T = exp["remaining_years"]
        S, K, _ = _estimate_S_K(conn, exp["cpc"] or "H01M", None, None)
        bs = _black_scholes_call(S, K, T, 0.02, sigma)
        mult = 1 + math.log(1 + exp["citations"]) / 5
        total_option_value_at_risk += bs["value"] * mult

    # Confidence interval
    z = norm.ppf(confidence)
    var_estimate = round(total_option_value_at_risk * z * sigma, 2)

    return {
        "endpoint": "portfolio_var",
        "firm_id": firm_id,
        "year": actual_year,
        "horizon_years": horizon_years,
        "confidence": confidence,
        "portfolio_stats": {
            "total_patents_estimated": total_count,
            "sample_analyzed": len(rows),
            "active_in_sample": active_count,
        },
        "expiration_risk": {
            "expiring_count": expiring_count,
            "expiring_pct": expiring_pct,
            "var_option_value": var_estimate,
        },
        "var_at_risk_cpc": var_at_risk_cpc,
        "remaining_years_distribution": {
            str(k): remaining_dist.get(k, 0)
            for k in range(0, 21)
        },
        "high_value_expiring": sorted(
            [e for e in expiring if e["citations"] > 0],
            key=lambda x: x["citations"], reverse=True,
        )[:10],
        "interpretation": (
            f"{firm_id}の特許ポートフォリオ: {horizon_years}年以内に"
            f"サンプル{active_count}件中{expiring_count}件({expiring_pct*100:.1f}%)が満了予定。"
            f"最もリスクが高い領域は{var_at_risk_cpc[0]['cpc']}({var_at_risk_cpc[0]['label']})。"
            if var_at_risk_cpc else f"{firm_id}: 満了リスク分析データなし"
        ),
    }


# ─── Tool 4: tech_beta ──────────────────────────────────────────────

def tech_beta(
    store: PatentStore,
    resolver: EntityResolver | None = None,
    query: str = "",
    query_type: str | None = None,
    benchmark: str = "all",
    date_from: str = "2015-01-01",
    date_to: str = "2024-12-31",
) -> dict[str, Any]:
    """CAPM-style technology beta analysis."""
    store._relax_timeout()
    conn = store._conn()

    year_from = int(date_from[:4])
    year_to = int(date_to[:4])
    q = query.strip()

    # Resolve to CPC prefix(es)
    if query_type == "firm" or (resolver and not q[:1].isalpha()):
        firm_id = _resolve_firm(resolver, q) if resolver else None
        if firm_id:
            # Get firm's dominant CPCs
            ftv = conn.execute(
                "SELECT dominant_cpc FROM firm_tech_vectors WHERE firm_id = ? ORDER BY year DESC LIMIT 1",
                (firm_id,),
            ).fetchone()
            cpc_prefix = (ftv["dominant_cpc"] or "H01M") if ftv else "H01M"
            cpc_prefix = _cpc4(cpc_prefix)
            query_type = "firm"
        else:
            cpc_prefix = q.upper()[:4]
            query_type = "technology"
    else:
        cpc_prefix = q.upper().replace("-", "").replace(" ", "")[:4]
        query_type = query_type or "technology"

    cpc4 = _cpc4(cpc_prefix) if cpc_prefix else ""
    cluster_ids = _find_clusters_for_cpc(conn, cpc_prefix)

    # Get tech-specific yearly counts
    tech_counts = _get_yearly_counts_from_momentum(
        conn, cluster_ids if cluster_ids else [f"{cpc_prefix}_0"], year_from, year_to
    )

    # Get market benchmark counts
    if benchmark == "section":
        section = cpc_prefix[0] if cpc_prefix else ""
        section_clusters = conn.execute(
            "SELECT cluster_id FROM tech_clusters WHERE cpc_class LIKE ? LIMIT 200",
            (f"{section}%",),
        ).fetchall()
        section_ids = [r["cluster_id"] for r in section_clusters]
        market_counts = _get_yearly_counts_from_momentum(conn, section_ids, year_from, year_to)
        benchmark_label = f"CPC Section {section}"
    else:
        market_counts = _get_total_market_counts(conn, year_from, year_to)
        benchmark_label = "全技術市場"

    # Compute returns
    tech_returns = _log_returns(tech_counts)
    market_returns = _log_returns(market_counts)

    # Align lengths
    min_len = min(len(tech_returns), len(market_returns))
    if min_len < 3:
        return {
            "error": f"Insufficient data for beta calculation (need >=3 years of returns, got {min_len})",
        }

    tr = np.array(tech_returns[:min_len])
    mr = np.array(market_returns[:min_len])

    # Beta calculation
    cov_matrix = np.cov(tr, mr)
    beta = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix[1, 1] > 1e-12 else 1.0
    alpha = float(np.mean(tr) - beta * np.mean(mr))
    r_squared = float(np.corrcoef(tr, mr)[0, 1] ** 2) if len(tr) > 1 else 0

    # Classification
    if beta > 1.2 and alpha > 0.02:
        classification = "high_beta_high_alpha"
        class_label = "成長技術（市場超過リターン）"
    elif beta > 1.2:
        classification = "high_beta_low_alpha"
        class_label = "景気敏感技術"
    elif alpha > 0.02:
        classification = "low_beta_high_alpha"
        class_label = "独自成長技術（ニッチ）"
    else:
        classification = "low_beta_low_alpha"
        class_label = "成熟技術"

    # Peer comparison (same section)
    section = cpc_prefix[0] if cpc_prefix else ""
    peer_clusters = conn.execute(
        "SELECT DISTINCT cpc_class FROM tech_clusters WHERE cpc_class LIKE ? AND cpc_class != ? LIMIT 10",
        (f"{section}%", cpc4),
    ).fetchall()
    peers = []
    for pc in peer_clusters[:5]:
        peer_cpc = pc["cpc_class"]
        p_clusters = _find_clusters_for_cpc(conn, peer_cpc)
        p_counts = _get_yearly_counts_from_momentum(conn, p_clusters, year_from, year_to)
        p_returns = _log_returns(p_counts)
        if len(p_returns) >= min_len:
            pr = np.array(p_returns[:min_len])
            p_cov = np.cov(pr, mr)
            p_beta = float(p_cov[0, 1] / p_cov[1, 1]) if p_cov[1, 1] > 1e-12 else 1.0
            p_alpha = float(np.mean(pr) - p_beta * np.mean(mr))
            peers.append({
                "cpc": peer_cpc,
                "label": CPC_CLASS_JA.get(peer_cpc, ""),
                "beta": round(p_beta, 4),
                "alpha": round(p_alpha, 4),
            })

    return {
        "endpoint": "tech_beta",
        "query": q,
        "query_type": query_type,
        "cpc_prefix": cpc_prefix,
        "cpc_label": CPC_CLASS_JA.get(cpc4, ""),
        "benchmark": benchmark_label,
        "date_range": {"from": year_from, "to": year_to},
        "beta": round(beta, 4),
        "alpha": round(alpha, 4),
        "r_squared": round(r_squared, 4),
        "classification": classification,
        "classification_label": class_label,
        "tech_stats": {
            "mean_return": round(float(np.mean(tr)), 4),
            "std_return": round(float(np.std(tr)), 4),
            "num_years": min_len + 1,
        },
        "market_stats": {
            "mean_return": round(float(np.mean(mr)), 4),
            "std_return": round(float(np.std(mr)), 4),
        },
        "peer_comparison": peers,
        "interpretation": (
            f"{CPC_CLASS_JA.get(cpc4, cpc_prefix)}のβ={beta:.3f}, α={alpha:.3f}, "
            f"R²={r_squared:.3f}。分類: {class_label}。"
            f"{'市場平均より高いボラティリティ。' if beta > 1 else '市場平均より安定的。'}"
        ),
        "visualization_hint": {
            "recommended_chart": "scatter",
            "title": f"技術ベータ: {cpc_prefix} vs {benchmark_label}",
            "axes": {
                "x": "market_return",
                "y": "tech_return",
                "annotation": "beta regression line",
            },
        },
    }
