"""Fast-path PAP benchmark — uses pre-computed tools only."""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("PATENT_DB_PATH", "/app/data/patents.db")

from db.sqlite_store import PatentStore
from pap.config import PAPConfig, PAPLevel
from pap.context import PAPContext
from pap.proof import compute_artifact_hash, compute_cmd_hash, generate_proof, verify_proof
from pap.chain import HashChain


def bench_tool(store, fn, tool_name, params, pap_level, n_runs=10):
    results = []
    for i in range(n_runs):
        os.environ["PAP_LEVEL"] = str(int(pap_level))
        config = PAPConfig()
        
        t0 = time.time()
        
        if pap_level == PAPLevel.DISABLED:
            result = fn(store=store, **params)
            t1 = time.time()
            results.append({
                "run": i, "pap_level": int(pap_level), "tool_name": tool_name,
                "call_latency": round(t1 - t0, 6), "total_latency": round(t1 - t0, 6),
                "proof_gen_time": 0, "verify_time": 0,
                "proof_size": 0, "log_size": 0, "event_count": 0,
                "error": isinstance(result, dict) and "error" in result,
            })
        elif pap_level == PAPLevel.ADHOC:
            # Simple JSON log, no chain
            log_entries = []
            log_entries.append({"ts": time.time(), "tool": tool_name, "params": list(params.keys())})
            result = fn(store=store, **params)
            log_entries.append({"ts": time.time(), "tool": tool_name, "output_keys": list(result.keys()) if isinstance(result, dict) else []})
            t1 = time.time()
            log_json = json.dumps(log_entries, default=str)
            results.append({
                "run": i, "pap_level": int(pap_level), "tool_name": tool_name,
                "call_latency": round(t1 - t0, 6), "total_latency": round(t1 - t0, 6),
                "proof_gen_time": 0, "verify_time": 0,
                "proof_size": 0, "log_size": len(log_json.encode()), "event_count": 2,
                "error": isinstance(result, dict) and "error" in result,
            })
        else:
            ctx = PAPContext(config, tool_name, params)
            with ctx:
                ctx.log_event("tool.input", tool_name, {"params": list(params.keys())})
                t_call = time.time()
                result = fn(store=store, **params)
                call_dur = time.time() - t_call
                ctx.log_event("tool.execution", tool_name, {"duration": round(call_dur, 4)})
                if isinstance(result, dict) and "error" not in result:
                    ctx.log_event("tool.output", tool_name, {"keys": list(result.keys())})
                ctx.bind_artifact(result)
            t1 = time.time()
            
            # Measure proof gen separately
            tp0 = time.time()
            chain2 = HashChain("m")
            for e in ctx.chain.events:
                chain2.append(e.event_type, e.tool_name, e.payload)
            cmd_h = compute_cmd_hash(tool_name, params)
            art_h = compute_artifact_hash(result)
            proof = generate_proof(config, "m", chain2, cmd_h, art_h, [tool_name], 0)
            tp1 = time.time()
            
            tv0 = time.time()
            verify_proof(config, proof)
            tv1 = time.time()
            
            results.append({
                "run": i, "pap_level": int(pap_level), "tool_name": tool_name,
                "call_latency": round(call_dur, 6), "total_latency": round(t1 - t0, 6),
                "proof_gen_time": round(tp1 - tp0, 6), "verify_time": round(tv1 - tv0, 6),
                "proof_size": proof.size_bytes(), "log_size": chain2.size_bytes(),
                "event_count": chain2.length,
                "error": isinstance(result, dict) and "error" in result,
            })
    return results


def summarize(results):
    ok = [r for r in results if not r["error"]]
    if not ok:
        return {"error": "all_failed", "n": len(results), "tool": results[0]["tool_name"], "level": results[0]["pap_level"]}
    def stats(vals):
        if len(vals) < 2:
            return {"mean": round(vals[0], 6), "median": round(vals[0], 6), "p95": round(vals[0], 6), "std": 0}
        return {"mean": round(statistics.mean(vals), 6), "median": round(statistics.median(vals), 6),
                "p95": round(sorted(vals)[min(int(len(vals)*0.95), len(vals)-1)], 6),
                "std": round(statistics.stdev(vals), 6)}
    return {
        "tool": ok[0]["tool_name"], "level": ok[0]["pap_level"],
        "n_ok": len(ok), "n_err": len(results)-len(ok),
        "total_latency": stats([r["total_latency"] for r in ok]),
        "call_latency": stats([r["call_latency"] for r in ok]),
        "proof_gen": stats([r["proof_gen_time"] for r in ok]),
        "verify": stats([r["verify_time"] for r in ok]),
        "proof_size": ok[0]["proof_size"], "log_size": ok[0]["log_size"],
        "events": ok[0]["event_count"],
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/pap_bench"
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    
    store = PatentStore(os.environ.get("PATENT_DB_PATH", "/app/data/patents.db"))
    
    # Fast-path tools only (pre-computed data, no FTS5 scan)
    from tools.startability_tool import startability, startability_ranking
    from tools.tech_fit import tech_fit
    from tools.portfolio import firm_patent_portfolio
    from tools.landscape import tech_landscape
    from tools.patent_valuation import patent_valuation
    from tools.similar_firms import similar_firms
    from tools.adversarial import adversarial_strategy
    from tools.tech_gap import tech_gap
    
    tasks = [
        ("startability", startability, {"firm_query": "トヨタ", "tech_query_or_cluster_id": "H01M_0"}),
        ("tech_fit", tech_fit, {"firm_query": "トヨタ", "tech_query_or_cluster_id": "H01M_0"}),
        ("portfolio", firm_patent_portfolio, {"firm": "トヨタ"}),
        ("landscape", tech_landscape, {"cpc_prefix": "H01M"}),
        ("valuation", patent_valuation, {"query": "トヨタ", "query_type": "firm", "purpose": "portfolio_ranking"}),
        ("adversarial", adversarial_strategy, {"firm_a": "トヨタ", "firm_b": "ホンダ"}),
    ]
    
    levels = [PAPLevel.DISABLED, PAPLevel.ADHOC, PAPLevel.LEVEL0, PAPLevel.LEVEL1]
    level_names = {-1: "B0", 0: "B1", 1: "B2", 2: "B3"}
    
    all_raw = []
    all_summary = []
    
    for tname, fn, params in tasks:
        for lv in levels:
            ln = level_names[int(lv)]
            print(f"  {tname} / {ln} x{n}...", end=" ", flush=True)
            try:
                raw = bench_tool(store, fn, tname, params, lv, n_runs=n)
                s = summarize(raw)
                s["task"] = tname
                s["regime"] = ln
                all_raw.extend(raw)
                all_summary.append(s)
                lat = s.get("total_latency", {})
                print(f"median={lat.get('median','?')}s proof={s.get('proof_size',0)}B")
            except Exception as e:
                print(f"ERROR: {e}")
                all_summary.append({"task": tname, "regime": ln, "error": str(e)})
    
    with open(f"{out_dir}/raw.jsonl", "w") as f:
        for r in all_raw:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    with open(f"{out_dir}/summary.json", "w") as f:
        json.dump(all_summary, f, indent=2, ensure_ascii=False)
    
    print(f"\nDone. {len(all_raw)} raw records, {len(all_summary)} summaries → {out_dir}/")
