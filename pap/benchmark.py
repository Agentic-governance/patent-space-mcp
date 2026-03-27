"""PAP benchmark harness — measures overhead across B0/B1/B2/B3 regimes.

Run from inside the container or server:
    python -m pap.benchmark
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.sqlite_store import PatentStore
from pap.config import PAPConfig, PAPLevel
from pap.context import PAPContext
from pap.proof import compute_artifact_hash, compute_cmd_hash, generate_proof, verify_proof
from pap.chain import HashChain
from pap.events import make_event


def _get_store():
    db_path = os.environ.get("PATENT_DB_PATH", "/app/data/patents.db")
    if not Path(db_path).exists():
        db_path = "/home/deploy/patent-space-mcp/data/patents.db"
    return PatentStore(db_path)


def benchmark_single_tool(store, tool_fn, tool_name, params, pap_level, n_runs=10):
    """Benchmark a single tool call across n_runs."""
    results = []
    
    for i in range(n_runs):
        os.environ["PAP_LEVEL"] = str(int(pap_level))
        config = PAPConfig()
        
        # Total timing
        t_total_start = time.time()
        
        if pap_level == PAPLevel.DISABLED:
            # B0: No PAP
            t_call_start = time.time()
            result = tool_fn(store=store, **params)
            t_call_end = time.time()
            proof_gen_time = 0.0
            verify_time = 0.0
            proof_size = 0
            log_size = 0
            event_count = 0
            
        else:
            ctx = PAPContext(config, tool_name, params)
            with ctx:
                # Log input
                ctx.log_event("tool.input", tool_name, {"params": list(params.keys())})
                
                # Execute
                t_call_start = time.time()
                result = tool_fn(store=store, **params)
                t_call_end = time.time()
                
                # Log output
                if isinstance(result, dict):
                    ctx.log_event("tool.output", tool_name, {"keys": list(result.keys())})
                
                # Bind artifact
                ctx.bind_artifact(result)
            
            # Measure proof generation (already done in __exit__, measure separately)
            t_proof_start = time.time()
            # Re-generate to measure
            chain2 = HashChain("bench")
            for ev in ctx.chain.events:
                chain2.append(ev.event_type, ev.tool_name, ev.payload)
            cmd_h = compute_cmd_hash(tool_name, params)
            art_h = compute_artifact_hash(result)
            proof = generate_proof(config, "bench", chain2, cmd_h, art_h, [tool_name], 0.0)
            proof_gen_time = time.time() - t_proof_start
            
            # Measure verification
            t_verify_start = time.time()
            verify_proof(config, proof)
            verify_time = time.time() - t_verify_start
            
            proof_size = proof.size_bytes()
            log_size = chain2.size_bytes()
            event_count = chain2.length
        
        t_total_end = time.time()
        
        results.append({
            "run": i,
            "pap_level": int(pap_level),
            "tool_name": tool_name,
            "call_latency": round(t_call_end - t_call_start, 6),
            "total_latency": round(t_total_end - t_total_start, 6),
            "proof_gen_time": round(proof_gen_time, 6),
            "verify_time": round(verify_time, 6),
            "proof_size_bytes": proof_size,
            "log_size_bytes": log_size,
            "event_count": event_count,
            "has_error": isinstance(result, dict) and "error" in result,
        })
    
    return results


def summarize_results(results):
    """Compute summary statistics."""
    latencies = [r["total_latency"] for r in results if not r["has_error"]]
    call_latencies = [r["call_latency"] for r in results if not r["has_error"]]
    proof_times = [r["proof_gen_time"] for r in results if not r["has_error"]]
    verify_times = [r["verify_time"] for r in results if not r["has_error"]]
    
    if not latencies:
        return {"error": "All runs failed", "n_runs": len(results)}
    
    return {
        "tool_name": results[0]["tool_name"],
        "pap_level": results[0]["pap_level"],
        "n_runs": len(results),
        "n_success": len(latencies),
        "n_error": len(results) - len(latencies),
        "total_latency": {
            "mean": round(statistics.mean(latencies), 6),
            "median": round(statistics.median(latencies), 6),
            "p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 6) if len(latencies) >= 2 else round(latencies[0], 6),
            "stdev": round(statistics.stdev(latencies), 6) if len(latencies) >= 2 else 0,
        },
        "call_latency": {
            "mean": round(statistics.mean(call_latencies), 6),
            "median": round(statistics.median(call_latencies), 6),
        },
        "proof_gen_time": {
            "mean": round(statistics.mean(proof_times), 6),
            "median": round(statistics.median(proof_times), 6),
        },
        "verify_time": {
            "mean": round(statistics.mean(verify_times), 6),
            "median": round(statistics.median(verify_times), 6),
        },
        "proof_size_bytes": results[0]["proof_size_bytes"],  # constant per config
        "log_size_bytes": results[0]["log_size_bytes"],
        "event_count": results[0]["event_count"],
    }


def run_benchmarks(n_runs=10, output_dir="/tmp/pap_benchmarks"):
    """Run full benchmark suite."""
    store = _get_store()
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Import tool functions
    from tools.search import patent_search
    from tools.landscape import tech_landscape
    from tools.portfolio import firm_patent_portfolio
    from tools.patent_valuation import patent_valuation
    from tools.claim_analysis import fto_analysis
    from tools.startability_tool import startability
    
    # Define test tasks
    tasks = {
        "T1_search": (patent_search, "patent_search", {
            "query": "全固体電池",
            "cpc_codes": ["H01M10"],
            "max_results": 20,
        }),
        "T1_fto": (fto_analysis, "fto_analysis", {
            "text": "全固体電池用の硫化物系固体電解質材料。リチウムイオン伝導性を持つ硫化物ガラスセラミックスを正極材料として使用する技術。",
            "cpc_codes": ["H01M10", "H01M4"],
            "target_jurisdiction": "JP",
        }),
        "T2_landscape": (tech_landscape, "tech_landscape", {
            "cpc_prefix": "B60W",
            "date_from": "2019-01-01",
            "date_to": "2024-12-31",
        }),
        "T2_portfolio": (firm_patent_portfolio, "firm_patent_portfolio", {
            "firm": "トヨタ",
        }),
        "T3_valuation": (patent_valuation, "patent_valuation", {
            "query": "パナソニック",
            "query_type": "firm",
            "purpose": "portfolio_ranking",
        }),
        "T3_startability": (startability, "startability", {
            "firm_query": "パナソニック",
            "tech_query_or_cluster_id": "H01M_0",
        }),
    }
    
    all_results = []
    summaries = []
    
    for task_name, (fn, tool_name, params) in tasks.items():
        for level in [PAPLevel.DISABLED, PAPLevel.ADHOC, PAPLevel.LEVEL0, PAPLevel.LEVEL1]:
            level_name = {-1: "B0", 0: "B1", 1: "B2", 2: "B3"}[int(level)]
            print(f"  Running {task_name} / {level_name} ({n_runs} runs)...", flush=True)
            
            try:
                results = benchmark_single_tool(store, fn, tool_name, params, level, n_runs=n_runs)
                summary = summarize_results(results)
                summary["task_name"] = task_name
                summary["regime"] = level_name
                
                all_results.extend(results)
                summaries.append(summary)
                
                print(f"    Done: median={summary.get('total_latency', {}).get('median', 'N/A')}s, "
                      f"proof={summary.get('proof_size_bytes', 0)}B")
            except Exception as e:
                print(f"    ERROR: {e}")
                summaries.append({
                    "task_name": task_name,
                    "regime": level_name,
                    "error": str(e),
                })
    
    # Save results
    raw_path = Path(output_dir) / "raw_results.jsonl"
    with open(raw_path, "w") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    summary_path = Path(output_dir) / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to {output_dir}/")
    print(f"  Raw: {raw_path} ({len(all_results)} records)")
    print(f"  Summary: {summary_path} ({len(summaries)} entries)")
    
    return summaries


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    run_benchmarks(n_runs=n)
