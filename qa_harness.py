"""MCP Quality Assurance Harness — 5 Personas × 300 Iterations.

Simulates 5 real-world user personas calling MCP tools,
evaluates response quality, and logs issues for fixing.

Personas:
  P1: Patent Attorney (FTO, claim analysis, litigation risk)
  P2: R&D Manager (tech landscape, cross-domain, invention intelligence)
  P3: Investment Analyst (valuation, option value, VaR, bayesian)
  P4: Competitive Intelligence (adversarial, similar firms, tech gap)
  P5: IP Strategy (startability, portfolio evolution, SEP)

Usage:
    python qa_harness.py [n_iterations] [output_dir]
"""
from __future__ import annotations
import json, os, sys, time, traceback, random, hashlib
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("PATENT_DB_PATH", "/app/data/patents.db")

from db.sqlite_store import PatentStore
from entity.registry import EntityRegistry
from entity.resolver import EntityResolver
from entity.data.tse_prime_seed import TSE_PRIME_ENTITIES
from entity.data.tse_expanded_seed import TSE_EXPANDED_ENTITIES
from entity.data.tse_auto_seed import TSE_AUTO_ENTITIES
try:
    from entity.data.sp500_seed import SP500_ENTITIES
except ImportError:
    SP500_ENTITIES = []
try:
    from entity.data.global_seed import GLOBAL_ENTITIES
except ImportError:
    GLOBAL_ENTITIES = []

# ── Setup ──
def setup():
    store = PatentStore(os.environ["PATENT_DB_PATH"])
    reg = EntityRegistry()
    for lst in [TSE_PRIME_ENTITIES, TSE_EXPANDED_ENTITIES, TSE_AUTO_ENTITIES, SP500_ENTITIES, GLOBAL_ENTITIES]:
        for e in lst:
            reg.register(e)
    resolver = EntityResolver(reg)
    return store, resolver

# ── Import all tools ──
from tools.search import patent_search
from tools.landscape import tech_landscape
from tools.portfolio import firm_patent_portfolio
from tools.patent_valuation import patent_valuation
from tools.similar_firms import similar_firms
from tools.adversarial import adversarial_strategy
from tools.tech_gap import tech_gap
from tools.startability_tool import startability, startability_ranking
from tools.startability_delta import startability_delta
from tools.tech_fit import tech_fit
from tools.tech_trend import tech_trend
from tools.cross_domain import cross_domain_discovery
from tools.invention_intel import invention_intelligence
from tools.market_fusion import patent_market_fusion
from tools.bayesian_scenario import bayesian_scenario
from tools.patent_finance import patent_option_value, tech_volatility, portfolio_var, tech_beta
from tools.claim_analysis import claim_analysis, claim_comparison, fto_analysis
from tools.citation_network import citation_network
from tools.portfolio_evolution import portfolio_evolution
from tools.sep_analysis import sep_search, sep_landscape, sep_portfolio, frand_analysis
from tools.corporate_hierarchy import corporate_hierarchy, group_portfolio, group_startability
from tools.network_analysis import network_topology, knowledge_flow, network_resilience, tech_fusion_detector, tech_entropy
from tools.ptab import ptab_search, ptab_risk, litigation_search, litigation_risk
from tools.sales_prospect import sales_prospect
from tools.ma_target import ma_target
from tools.patent_summary import patent_summary, technology_brief
from tools.visualization import tech_map, citation_graph_viz, firm_landscape, startability_heatmap
from tools.monitoring import create_watch, list_watches, check_alerts, run_monitoring
from tools.ai_classifier import create_category, classify_patents, category_landscape, portfolio_benchmark
from tools.compare import patent_compare
from tools.clusters import tech_clusters_list
from tools.gdelt_tool import gdelt_company_events
from tools.network import applicant_network
from tools.vectors import firm_tech_vector
from tools.cross_border import cross_border_similarity
from tools.tech_trend_alert import tech_trend_alert
from tools.ip_due_diligence import ip_due_diligence

# ── Firms and tech clusters for testing ──
JP_FIRMS = ["トヨタ", "ホンダ", "ソニー", "パナソニック", "日立", "キヤノン", "東芝",
            "三菱電機", "デンソー", "日産", "NEC", "富士通", "シャープ", "京セラ",
            "オムロン", "ファナック", "村田製作所", "TDK", "ブリヂストン", "旭化成"]
CPC_CODES = ["H01M", "H01L", "G06N", "B60W", "H04W", "A61K", "B25J", "G01N",
             "H02S", "C08L", "G06F", "H04N", "B01J", "F02D", "G02B", "C07K",
             "H01S", "B60L", "G06T", "A61B"]
CLUSTER_IDS = [f"{cpc}_0" for cpc in CPC_CODES]

# ── Persona definitions ──
def persona_patent_attorney(store, resolver, rng):
    """P1: Patent Attorney — FTO, claims, litigation"""
    tasks = [
        lambda: fto_analysis(store=store, resolver=resolver,
            text=rng.choice(["全固体電池の正極材料", "自動運転用LiDAR", "mRNA医薬品の送達技術",
                "量子コンピュータの誤り訂正", "有機ELディスプレイの封止技術"]),
            cpc_codes=[rng.choice(CPC_CODES)], target_jurisdiction="JP"),
        lambda: claim_analysis(store=store,
            publication_number=f"JP-{rng.randint(2020001, 2024999)}-A"),
        lambda: litigation_risk(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: ptab_risk(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: litigation_search(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: ptab_search(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: ip_due_diligence(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
    ]
    return rng.choice(tasks)

def persona_rd_manager(store, resolver, rng):
    """P2: R&D Manager — landscape, cross-domain, invention intel"""
    tasks = [
        lambda: tech_landscape(store=store,
            cpc_prefix=rng.choice(CPC_CODES),
            date_from="2019-01-01", date_to="2024-12-31"),
        lambda: cross_domain_discovery(store=store, resolver=resolver,
            query=rng.choice(CPC_CODES), top_n=5),
        lambda: invention_intelligence(store=store, resolver=resolver,
            text=rng.choice(["水素燃料電池", "エッジAI", "バイオプラスチック", "6G通信",
                "核融合発電", "量子暗号通信", "再生医療"]),
            max_results=10),
        lambda: tech_trend(store=store,
            cpc_code=rng.choice(CPC_CODES)),
        lambda: tech_trend_alert(store=store, resolver=resolver,
            cpc_code=rng.choice(CPC_CODES)),
        lambda: technology_brief(store=store, resolver=resolver,
            query=rng.choice(CPC_CODES)),
        lambda: tech_fusion_detector(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: knowledge_flow(store=store, resolver=resolver,
            source=rng.choice(JP_FIRMS[:10]),
            target=rng.choice(JP_FIRMS[10:])),
        lambda: tech_clusters_list(store=store,
            cpc_filter=rng.choice(CPC_CODES)[:3]),
    ]
    return rng.choice(tasks)

def persona_investor(store, resolver, rng):
    """P3: Investment Analyst — valuation, option, VaR, bayesian"""
    tasks = [
        lambda: patent_valuation(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS), query_type="firm", purpose="portfolio_ranking"),
        lambda: patent_option_value(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: portfolio_var(store=store, resolver=resolver,
            firm=rng.choice(JP_FIRMS), confidence=0.95),
        lambda: tech_volatility(store=store, resolver=resolver,
            query=rng.choice(CPC_CODES)),
        lambda: tech_beta(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: bayesian_scenario(store=store, resolver=resolver,
            mode="init", technology=rng.choice(CLUSTER_IDS),
            firm_query=rng.choice(JP_FIRMS)),
        lambda: ma_target(store=store, resolver=resolver,
            acquirer=rng.choice(JP_FIRMS[:10]),
            budget_hint=rng.choice(["small", "medium", "large"])),
        lambda: portfolio_evolution(store=store, resolver=resolver,
            firm=rng.choice(JP_FIRMS)),
        lambda: sales_prospect(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
    ]
    return rng.choice(tasks)

def persona_competitive_intel(store, resolver, rng):
    """P4: Competitive Intelligence — adversarial, similar, gap"""
    f1, f2 = rng.sample(JP_FIRMS, 2)
    tasks = [
        lambda: adversarial_strategy(store=store, resolver=resolver,
            firm_a=f1, firm_b=f2),
        lambda: similar_firms(store=store, resolver=resolver,
            firm_query=rng.choice(JP_FIRMS), top_n=5),
        lambda: tech_gap(store=store, resolver=resolver,
            firm_a=f1, firm_b=f2),
        lambda: firm_patent_portfolio(store=store, resolver=resolver,
            firm=rng.choice(JP_FIRMS)),
        lambda: firm_tech_vector(store=store, resolver=resolver,
            firm=rng.choice(JP_FIRMS)),
        lambda: applicant_network(store=store, resolver=resolver,
            firm=rng.choice(JP_FIRMS)),
        lambda: patent_compare(store=store, resolver=resolver,
            firm_a=f1, firm_b=f2),
        lambda: corporate_hierarchy(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: network_topology(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
    ]
    return rng.choice(tasks)

def persona_ip_strategy(store, resolver, rng):
    """P5: IP Strategy — startability, SEP, portfolio benchmark"""
    tasks = [
        lambda: startability(store=store, resolver=resolver,
            firm_query=rng.choice(JP_FIRMS),
            tech_query_or_cluster_id=rng.choice(CLUSTER_IDS)),
        lambda: startability_ranking(store=store, resolver=resolver,
            mode="by_firm", query=rng.choice(JP_FIRMS)),
        lambda: startability_delta(store=store, resolver=resolver,
            mode="by_firm", query=rng.choice(JP_FIRMS)),
        lambda: startability_heatmap(store=store, resolver=resolver,
            firm_query=rng.choice(JP_FIRMS)),
        lambda: tech_fit(store=store, resolver=resolver,
            firm_query=rng.choice(JP_FIRMS),
            tech_query_or_cluster_id=rng.choice(CLUSTER_IDS)),
        lambda: sep_search(store=store, resolver=resolver,
            query=rng.choice(["5G", "LTE", "Wi-Fi", "HEVC", "AV1"])),
        lambda: sep_landscape(store=store, resolver=resolver,
            standard=rng.choice(["5G", "LTE", "Wi-Fi 6"])),
        lambda: group_startability(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS),
            cluster_id=rng.choice(CLUSTER_IDS)),
        lambda: tech_entropy(store=store, resolver=resolver,
            query=rng.choice(JP_FIRMS)),
        lambda: portfolio_benchmark(store=store, resolver=resolver,
            firm=rng.choice(JP_FIRMS)),
    ]
    return rng.choice(tasks)

PERSONAS = {
    "P1_attorney": persona_patent_attorney,
    "P2_rd_mgr": persona_rd_manager,
    "P3_investor": persona_investor,
    "P4_comp_intel": persona_competitive_intel,
    "P5_ip_strategy": persona_ip_strategy,
}

# ── Quality evaluation ──
def evaluate_response(result, tool_name, duration):
    """Evaluate response quality. Returns (quality_score, issues)."""
    issues = []
    score = 1.0  # start perfect

    if not isinstance(result, dict):
        issues.append(("critical", "non_dict_response", str(type(result))))
        return 0.0, issues

    # Error response
    if "error" in result:
        err = result["error"]
        if "timed out" in str(err).lower() or "timeout" in str(err).lower():
            issues.append(("warning", "timeout", str(err)[:200]))
            score -= 0.5
        elif "not found" in str(err).lower() or "no data" in str(err).lower():
            issues.append(("info", "no_data", str(err)[:200]))
            score -= 0.2
        else:
            issues.append(("error", "tool_error", str(err)[:200]))
            score -= 0.8
        return max(0, score), issues

    # Empty response
    if len(result) <= 1:
        issues.append(("warning", "near_empty_response", f"only {len(result)} keys"))
        score -= 0.3

    # Check for None values in top-level
    none_keys = [k for k, v in result.items() if v is None]
    if none_keys:
        issues.append(("info", "null_fields", f"null: {none_keys}"))
        score -= 0.05 * len(none_keys)

    # Check for empty lists/dicts
    empty_keys = [k for k, v in result.items() if isinstance(v, (list, dict)) and len(v) == 0
                  and k not in ("error", "warnings", "notes", "_pap_proof")]
    if empty_keys:
        issues.append(("info", "empty_collections", f"empty: {empty_keys}"))
        score -= 0.05 * len(empty_keys)

    # Slow response
    if duration > 30:
        issues.append(("warning", "very_slow", f"{duration:.1f}s"))
        score -= 0.2
    elif duration > 10:
        issues.append(("info", "slow", f"{duration:.1f}s"))
        score -= 0.05

    # Tool-specific checks
    if tool_name in ("patent_search", "fto_analysis", "invention_intelligence"):
        if "patents" in result and isinstance(result["patents"], list) and len(result["patents"]) == 0:
            if "total_count" in result and result["total_count"] == 0:
                issues.append(("info", "zero_results", "no patents found"))
                score -= 0.1

    if tool_name in ("adversarial_strategy", "tech_gap", "patent_compare"):
        if "overview" in result:
            ov = result["overview"]
            if isinstance(ov, dict):
                for k in ("firm_a", "firm_b"):
                    if k in ov and isinstance(ov[k], dict) and not ov[k].get("firm_id"):
                        issues.append(("warning", "unresolved_firm", f"{k} has no firm_id"))
                        score -= 0.15

    return max(0, round(score, 3)), issues


# ── Main loop ──
def run_iterations(n_iter, output_dir):
    store, resolver = setup()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    log_path = Path(output_dir) / "qa_log.jsonl"
    summary_path = Path(output_dir) / "qa_summary.json"
    issues_path = Path(output_dir) / "issues_registry.json"

    rng = random.Random(42)
    persona_names = list(PERSONAS.keys())

    # Counters
    total = 0; success = 0; errors = 0; timeouts = 0
    issue_registry = {}  # issue_type -> {count, examples, first_seen, last_seen}
    persona_stats = {p: {"calls": 0, "success": 0, "errors": 0, "avg_score": 0, "total_score": 0}
                     for p in persona_names}
    tool_stats = {}  # tool_name -> {calls, success, errors, timeouts, avg_duration}

    batch_size = 50
    batch_num = 0

    with open(log_path, "a") as log_f:
        for i in range(n_iter):
            persona_name = persona_names[i % len(persona_names)]
            persona_fn = PERSONAS[persona_name]

            try:
                task_fn = persona_fn(store, resolver, rng)
                tool_name = task_fn.__code__.co_qualname.split(".<locals>")[0] if hasattr(task_fn, '__code__') else "unknown"
                # Get actual tool name from the function
                # We can't easily get it from lambda, so extract from repr
                tool_name = "unknown"
                try:
                    # Try to extract from the lambda's closure
                    code = task_fn.__code__
                    freevars = code.co_freevars
                    tool_name = str(task_fn).split(" ")[-1].rstrip(">")
                except:
                    pass

                t0 = time.time()
                result = task_fn()
                duration = time.time() - t0

                # Try to identify tool name from result
                if isinstance(result, dict):
                    if "endpoint" in result:
                        tool_name = result["endpoint"]
                    elif "_tool" in result:
                        tool_name = result["_tool"]

                quality, issues = evaluate_response(result, tool_name, duration)
                total += 1

                is_error = isinstance(result, dict) and "error" in result
                is_timeout = is_error and ("timeout" in str(result.get("error", "")).lower())

                if is_error:
                    errors += 1
                    if is_timeout:
                        timeouts += 1
                else:
                    success += 1

                # Update persona stats
                ps = persona_stats[persona_name]
                ps["calls"] += 1
                if not is_error:
                    ps["success"] += 1
                else:
                    ps["errors"] += 1
                ps["total_score"] += quality
                ps["avg_score"] = round(ps["total_score"] / ps["calls"], 3)

                # Update tool stats
                if tool_name not in tool_stats:
                    tool_stats[tool_name] = {"calls": 0, "success": 0, "errors": 0,
                        "timeouts": 0, "durations": [], "avg_dur": 0}
                ts = tool_stats[tool_name]
                ts["calls"] += 1
                if is_timeout:
                    ts["timeouts"] += 1
                elif is_error:
                    ts["errors"] += 1
                else:
                    ts["success"] += 1
                ts["durations"].append(duration)
                ts["avg_dur"] = round(sum(ts["durations"]) / len(ts["durations"]), 3)

                # Update issue registry
                for severity, issue_type, detail in issues:
                    key = f"{severity}:{issue_type}"
                    if key not in issue_registry:
                        issue_registry[key] = {
                            "severity": severity, "type": issue_type,
                            "count": 0, "first_seen": i, "last_seen": i,
                            "examples": [], "tool_names": set(),
                        }
                    ir = issue_registry[key]
                    ir["count"] += 1
                    ir["last_seen"] = i
                    ir["tool_names"].add(tool_name)
                    if len(ir["examples"]) < 5:
                        ir["examples"].append({"iter": i, "detail": detail, "persona": persona_name})

                # Log
                log_entry = {
                    "iter": i, "persona": persona_name, "tool": tool_name,
                    "duration": round(duration, 3), "quality": quality,
                    "is_error": is_error, "is_timeout": is_timeout,
                    "issues": [(s, t, d) for s, t, d in issues],
                    "result_keys": list(result.keys()) if isinstance(result, dict) else [],
                }
                log_f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")

            except Exception as e:
                total += 1
                errors += 1
                tb = traceback.format_exc()
                err_type = type(e).__name__
                err_msg = str(e)[:300]

                key = f"critical:exception:{err_type}"
                if key not in issue_registry:
                    issue_registry[key] = {
                        "severity": "critical", "type": f"exception:{err_type}",
                        "count": 0, "first_seen": i, "last_seen": i,
                        "examples": [], "tool_names": set(),
                    }
                ir = issue_registry[key]
                ir["count"] += 1
                ir["last_seen"] = i
                if len(ir["examples"]) < 5:
                    ir["examples"].append({"iter": i, "detail": err_msg, "persona": persona_name, "tb": tb[-500:]})

                log_entry = {
                    "iter": i, "persona": persona_name, "tool": "EXCEPTION",
                    "duration": 0, "quality": 0, "is_error": True,
                    "is_timeout": False, "exception": err_type, "message": err_msg,
                }
                log_f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
                persona_stats[persona_name]["calls"] += 1
                persona_stats[persona_name]["errors"] += 1

            # Progress report every batch
            if (i + 1) % batch_size == 0:
                batch_num += 1
                rate = success / total * 100 if total > 0 else 0
                print(f"  [{i+1}/{n_iter}] ok={success} err={errors} to={timeouts} rate={rate:.1f}% "
                      f"issues={len(issue_registry)}", flush=True)

    # Serialize issue_registry (convert sets to lists)
    for k, v in issue_registry.items():
        v["tool_names"] = sorted(v["tool_names"])

    # Remove raw durations from tool_stats (too large)
    for ts in tool_stats.values():
        if "durations" in ts:
            durs = ts["durations"]
            ts["min_dur"] = round(min(durs), 3) if durs else 0
            ts["max_dur"] = round(max(durs), 3) if durs else 0
            ts["med_dur"] = round(sorted(durs)[len(durs)//2], 3) if durs else 0
            del ts["durations"]

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_iterations": n_iter,
        "total_calls": total,
        "success": success,
        "errors": errors,
        "timeouts": timeouts,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        "unique_issues": len(issue_registry),
        "persona_stats": persona_stats,
        "tool_stats": dict(sorted(tool_stats.items(), key=lambda x: x[1]["calls"], reverse=True)),
        "top_issues": sorted(
            [{"key": k, **v} for k, v in issue_registry.items()],
            key=lambda x: x["count"], reverse=True
        )[:30],
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    with open(issues_path, "w") as f:
        json.dump(issue_registry, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'='*60}")
    print(f"DONE: {n_iter} iterations")
    print(f"  Success: {success}/{total} ({summary['success_rate']}%)")
    print(f"  Errors: {errors} (timeouts: {timeouts})")
    print(f"  Unique issues: {len(issue_registry)}")
    print(f"  Results: {output_dir}/")
    print(f"{'='*60}")

    return summary


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    od = sys.argv[2] if len(sys.argv) > 2 else "/tmp/qa_results"
    run_iterations(n, od)
