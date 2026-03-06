"""citation_network tool — build patent citation graph.

Constructs a citation network around a patent or firm's top patents.
Uses BFS traversal through patent_citations table. Returns nodes,
edges, and centrality metrics for identifying hub patents.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from db.sqlite_store import PatentStore
from entity.resolver import EntityResolver


def citation_network(
    store: PatentStore,
    resolver: EntityResolver | None = None,
    publication_number: str | None = None,
    firm_query: str | None = None,
    depth: int = 1,
    direction: str = "both",
    max_nodes: int = 50,
) -> dict[str, Any]:
    """Build citation network around a patent or firm's top patents.

    Two modes:
    - Patent mode: BFS from a single patent through citations
    - Firm mode: Find firm's top-cited patents, build network from those

    Args:
        store: PatentStore instance.
        resolver: EntityResolver (required for firm mode).
        publication_number: Seed patent (patent mode).
        firm_query: Company name/ticker (firm mode).
        depth: BFS traversal depth (1 or 2). Default: 1.
        direction: "forward" (who cites this), "backward" (what this cites), or "both".
        max_nodes: Maximum nodes in the network. Default: 50.

    Returns:
        Dict with nodes, edges, metrics (hub patents, total counts).
    """
    if not publication_number and not firm_query:
        return {
            "error": "Either publication_number or firm_query is required.",
            "suggestion": "Provide a patent number (e.g., 'JP-7637366-B1') or firm name.",
        }

    depth = max(1, min(depth, 2))  # Cap at 2 to prevent explosion
    max_nodes = max(10, min(max_nodes, 200))
    conn = store._conn()

    # Determine seed patents
    if publication_number:
        seeds = [publication_number.strip()]
        mode_label = "patent"
    else:
        # Firm mode: find top-cited patents
        if resolver is None:
            return {"error": "resolver required for firm mode"}
        resolved = resolver.resolve(firm_query, country_hint="JP")
        if resolved is None:
            return {
                "error": f"Could not resolve firm: '{firm_query}'",
                "suggestion": "Try the exact company name, Japanese name, or stock ticker",
            }
        firm_id = resolved.entity.canonical_id

        # Get firm's top-cited patents via citation_counts + patent_assignees
        seed_rows = conn.execute(
            """
            SELECT cc.publication_number, cc.forward_citations
            FROM citation_counts cc
            JOIN patent_assignees pa ON cc.publication_number = pa.publication_number
            WHERE pa.firm_id = ?
            ORDER BY cc.forward_citations DESC
            LIMIT 5
            """,
            (firm_id,),
        ).fetchall()

        if not seed_rows:
            # Fallback: try harmonized_name match
            seed_rows = conn.execute(
                """
                SELECT cc.publication_number, cc.forward_citations
                FROM citation_counts cc
                JOIN patent_assignees pa ON cc.publication_number = pa.publication_number
                WHERE pa.harmonized_name LIKE ?
                ORDER BY cc.forward_citations DESC
                LIMIT 5
                """,
                (f"%{firm_query}%",),
            ).fetchall()

        if not seed_rows:
            return {
                "error": f"No cited patents found for firm '{firm_query}'",
                "suggestion": "This firm may not have patents with citations in the database.",
            }

        seeds = [r["publication_number"] for r in seed_rows]
        mode_label = "firm"

    # BFS traversal
    visited: set[str] = set()
    edges: list[dict] = []
    node_in_degree: dict[str, int] = defaultdict(int)  # cited count within network
    node_out_degree: dict[str, int] = defaultdict(int)  # citing count within network

    frontier = set(seeds)
    visited.update(frontier)

    for d in range(depth):
        if len(visited) >= max_nodes:
            break
        next_frontier: set[str] = set()

        frontier_list = list(frontier)
        chunk_size = 100

        for i in range(0, len(frontier_list), chunk_size):
            chunk = frontier_list[i:i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)

            if direction in ("forward", "both"):
                # Who cites these patents? (forward citations)
                rows = conn.execute(
                    f"""
                    SELECT citing_publication, cited_publication
                    FROM patent_citations
                    WHERE cited_publication IN ({placeholders})
                    """,
                    chunk,
                ).fetchall()
                for r in rows:
                    citing = r["citing_publication"]
                    cited = r["cited_publication"]
                    edges.append({"source": citing, "target": cited, "type": "cites"})
                    node_in_degree[cited] += 1
                    node_out_degree[citing] += 1
                    if citing not in visited and len(visited) + len(next_frontier) < max_nodes:
                        next_frontier.add(citing)

            if direction in ("backward", "both"):
                # What do these patents cite? (backward citations)
                rows = conn.execute(
                    f"""
                    SELECT citing_publication, cited_publication
                    FROM patent_citations
                    WHERE citing_publication IN ({placeholders})
                    """,
                    chunk,
                ).fetchall()
                for r in rows:
                    citing = r["citing_publication"]
                    cited = r["cited_publication"]
                    edges.append({"source": citing, "target": cited, "type": "cites"})
                    node_in_degree[cited] += 1
                    node_out_degree[citing] += 1
                    if cited not in visited and len(visited) + len(next_frontier) < max_nodes:
                        next_frontier.add(cited)

        visited.update(next_frontier)
        frontier = next_frontier

    # Deduplicate edges
    edge_set: set[tuple[str, str]] = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"])
        if key not in edge_set:
            edge_set.add(key)
            unique_edges.append(e)

    # Build node list with metadata
    all_node_ids = list(visited)[:max_nodes]

    # Batch fetch patent metadata for nodes
    node_metadata = _batch_fetch_metadata(conn, all_node_ids)

    # Batch fetch forward citation counts
    citation_counts = _batch_fetch_citations(conn, all_node_ids)

    nodes = []
    for nid in all_node_ids:
        meta = node_metadata.get(nid, {})
        nodes.append({
            "id": nid,
            "title": meta.get("title_ja") or meta.get("title_en", ""),
            "assignee": meta.get("assignee", ""),
            "filing_date": meta.get("filing_date", ""),
            "forward_citations": citation_counts.get(nid, 0),
            "network_in_degree": node_in_degree.get(nid, 0),
            "network_out_degree": node_out_degree.get(nid, 0),
            "is_seed": nid in seeds,
        })

    # Identify hub patents (highest in-degree within network)
    hubs = sorted(nodes, key=lambda n: n["network_in_degree"], reverse=True)[:5]

    return {
        "endpoint": "citation_network",
        "mode": mode_label,
        "seed_patents": seeds,
        "depth": depth,
        "direction": direction,
        "total_nodes": len(nodes),
        "total_edges": len(unique_edges),
        "nodes": nodes,
        "edges": unique_edges[:200],  # Cap edges for response size
        "metrics": {
            "hub_patents": [
                {
                    "id": h["id"],
                    "title": h["title"],
                    "network_in_degree": h["network_in_degree"],
                    "forward_citations": h["forward_citations"],
                }
                for h in hubs
                if h["network_in_degree"] > 0
            ],
            "avg_in_degree": round(
                sum(n["network_in_degree"] for n in nodes) / len(nodes), 2
            ) if nodes else 0,
            "max_in_degree": max((n["network_in_degree"] for n in nodes), default=0),
            "density": round(
                len(unique_edges) / (len(nodes) * (len(nodes) - 1) + 1e-9), 4
            ) if len(nodes) > 1 else 0,
        },
    }


def _batch_fetch_metadata(conn, pub_numbers: list[str]) -> dict[str, dict]:
    """Batch fetch patent title and assignee for display."""
    if not pub_numbers:
        return {}

    result: dict[str, dict] = {}
    chunk_size = 100
    for i in range(0, len(pub_numbers), chunk_size):
        chunk = pub_numbers[i:i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)

        # Get titles
        rows = conn.execute(
            f"""
            SELECT publication_number, title_ja, title_en, filing_date
            FROM patents
            WHERE publication_number IN ({placeholders})
            """,
            chunk,
        ).fetchall()
        for r in rows:
            result[r["publication_number"]] = {
                "title_ja": r["title_ja"],
                "title_en": r["title_en"],
                "filing_date": r["filing_date"],
            }

        # Get primary assignee
        rows2 = conn.execute(
            f"""
            SELECT publication_number, harmonized_name
            FROM patent_assignees
            WHERE publication_number IN ({placeholders})
            """,
            chunk,
        ).fetchall()
        # Keep first assignee per patent
        for r in rows2:
            pn = r["publication_number"]
            if pn in result and "assignee" not in result[pn]:
                result[pn]["assignee"] = r["harmonized_name"]

    return result


def _batch_fetch_citations(conn, pub_numbers: list[str]) -> dict[str, int]:
    """Batch fetch forward citation counts."""
    if not pub_numbers:
        return {}

    result: dict[str, int] = {}
    chunk_size = 100
    for i in range(0, len(pub_numbers), chunk_size):
        chunk = pub_numbers[i:i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""
            SELECT publication_number, forward_citations
            FROM citation_counts
            WHERE publication_number IN ({placeholders})
            """,
            chunk,
        ).fetchall()
        for r in rows:
            result[r["publication_number"]] = r["forward_citations"]

    return result
