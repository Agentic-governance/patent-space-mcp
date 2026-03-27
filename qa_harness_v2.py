"""MCP QA Harness v2 — Fixed tool signatures, 5 Personas × 300 Iterations."""
from __future__ import annotations
import json, os, sys, time, traceback, random, collections
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

def setup():
    store = PatentStore(os.environ["PATENT_DB_PATH"])
    reg = EntityRegistry()
    for lst in [TSE_PRIME_ENTITIES, TSE_EXPANDED_ENTITIES, TSE_AUTO_ENTITIES, SP500_ENTITIES, GLOBAL_ENTITIES]:
        for e in lst: reg.register(e)
    return store, EntityResolver(reg)

# Imports
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
from tools.monitoring import list_watches, check_alerts, run_monitoring
from tools.ai_classifier import category_landscape, portfolio_benchmark
from tools.compare import patent_compare
from tools.clusters import tech_clusters_list
from tools.network import applicant_network
from tools.vectors import firm_tech_vector
from tools.cross_border import cross_border_similarity
from tools.tech_trend_alert import tech_trend_alert
from tools.ip_due_diligence import ip_due_diligence

JP_FIRMS = ["トヨタ","ホンダ","ソニー","パナソニック","日立","キヤノン","東芝",
            "三菱電機","デンソー","日産","NEC","富士通","シャープ","京セラ",
            "オムロン","ファナック","村田製作所","TDK","ブリヂストン","旭化成"]
CPC_CODES = ["H01M","H01L","G06N","B60W","H04W","A61K","B25J","G01N",
             "H02S","C08L","G06F","H04N","B01J","F02D","G02B","C07K",
             "H01S","B60L","G06T","A61B"]
CLUSTER_IDS = [f"{c}_0" for c in CPC_CODES]

# ── FIXED Persona definitions ──
def P1_attorney(s, r, rng):
    """Patent Attorney"""
    return rng.choice([
        # fto_analysis: store only (no resolver), text + cpc_codes + target_jurisdiction
        lambda: ("fto_analysis", fto_analysis(store=s,
            text=rng.choice(["全固体電池の正極材料","自動運転用LiDAR","mRNA医薬品の送達技術",
                "量子コンピュータの誤り訂正","有機ELディスプレイの封止技術"]),
            cpc_codes=[rng.choice(CPC_CODES)], target_jurisdiction="JP")),
        # claim_analysis: store only
        lambda: ("claim_analysis", claim_analysis(store=s,
            publication_number=f"JP-{rng.randint(2020001,2024999)}-A")),
        # litigation_risk: store + resolver, firm_query (not query)
        lambda: ("litigation_risk", litigation_risk(store=s, resolver=r,
            firm_query=rng.choice(JP_FIRMS))),
        # ptab_risk: store + resolver, firm_query or cpc_prefix
        lambda: ("ptab_risk", ptab_risk(store=s, resolver=r,
            cpc_prefix=rng.choice(CPC_CODES))),
        # litigation_search: store + resolver, plaintiff/defendant
        lambda: ("litigation_search", litigation_search(store=s, resolver=r,
            plaintiff=rng.choice(JP_FIRMS))),
        # ptab_search: store + resolver, patent_owner
        lambda: ("ptab_search", ptab_search(store=s, resolver=r,
            patent_owner=rng.choice(JP_FIRMS))),
        # ip_due_diligence: store + resolver, query
        lambda: ("ip_due_diligence", ip_due_diligence(store=s, resolver=r,
            query=rng.choice(JP_FIRMS))),
    ])

def P2_rd_mgr(s, r, rng):
    """R&D Manager"""
    return rng.choice([
        lambda: ("tech_landscape", tech_landscape(store=s,
            cpc_prefix=rng.choice(CPC_CODES), date_from="2019-01-01", date_to="2024-12-31")),
        # cross_domain_discovery: store only (no resolver)
        lambda: ("cross_domain_discovery", cross_domain_discovery(store=s,
            query=rng.choice(CPC_CODES), top_n=5)),
        lambda: ("invention_intelligence", invention_intelligence(store=s, resolver=r,
            text=rng.choice(["水素燃料電池","エッジAI","バイオプラスチック","6G通信",
                "核融合発電","量子暗号通信","再生医療"]), max_results=10)),
        # tech_trend: store+resolver, query (not cpc_code)
        lambda: ("tech_trend", tech_trend(store=s, resolver=r,
            query=rng.choice(CPC_CODES))),
        # tech_trend_alert: store only (no resolver)
        lambda: ("tech_trend_alert", tech_trend_alert(store=s,
            cpc_code=rng.choice(CPC_CODES))),
        # technology_brief: store only (no resolver), query or cpc_prefix
        lambda: ("technology_brief", technology_brief(store=s,
            cpc_prefix=rng.choice(CPC_CODES))),
        lambda: ("tech_fusion_detector", tech_fusion_detector(store=s, resolver=r,
            query=rng.choice(JP_FIRMS))),
        # knowledge_flow: store+resolver, source_cpc + target_cpc (not source/target)
        lambda: ("knowledge_flow", knowledge_flow(store=s, resolver=r,
            source_cpc=rng.choice(CPC_CODES[:10]),
            target_cpc=rng.choice(CPC_CODES[10:]))),
        lambda: ("tech_clusters_list", tech_clusters_list(store=s,
            cpc_filter=rng.choice(CPC_CODES)[:3])),
    ])

def P3_investor(s, r, rng):
    """Investment Analyst"""
    return rng.choice([
        lambda: ("patent_valuation", patent_valuation(store=s, resolver=r,
            query=rng.choice(JP_FIRMS), query_type="firm", purpose="portfolio_ranking")),
        lambda: ("patent_option_value", patent_option_value(store=s, resolver=r,
            query=rng.choice(JP_FIRMS))),
        lambda: ("portfolio_var", portfolio_var(store=s, resolver=r,
            firm=rng.choice(JP_FIRMS), confidence=0.95)),
        lambda: ("tech_volatility", tech_volatility(store=s, resolver=r,
            query=rng.choice(CPC_CODES))),
        lambda: ("tech_beta", tech_beta(store=s, resolver=r,
            query=rng.choice(JP_FIRMS))),
        lambda: ("bayesian_scenario", bayesian_scenario(store=s, resolver=r,
            mode="init", technology=rng.choice(CLUSTER_IDS),
            firm_query=rng.choice(JP_FIRMS))),
        # ma_target: store+resolver, acquirer, top_n (no budget_hint)
        lambda: ("ma_target", ma_target(store=s, resolver=r,
            acquirer=rng.choice(JP_FIRMS[:10]), top_n=5)),
        lambda: ("portfolio_evolution", portfolio_evolution(store=s, resolver=r,
            firm=rng.choice(JP_FIRMS))),
        # sales_prospect: store+resolver, firm_query (not query)
        lambda: ("sales_prospect", sales_prospect(store=s, resolver=r,
            firm_query=rng.choice(JP_FIRMS))),
    ])

def P4_comp_intel(s, r, rng):
    """Competitive Intelligence"""
    f1, f2 = rng.sample(JP_FIRMS, 2)
    return rng.choice([
        lambda: ("adversarial_strategy", adversarial_strategy(store=s, resolver=r,
            firm_a=f1, firm_b=f2)),
        lambda: ("similar_firms", similar_firms(store=s, resolver=r,
            firm_query=rng.choice(JP_FIRMS), top_n=5)),
        lambda: ("tech_gap", tech_gap(store=s, resolver=r,
            firm_a=f1, firm_b=f2)),
        lambda: ("firm_patent_portfolio", firm_patent_portfolio(store=s, resolver=r,
            firm=rng.choice(JP_FIRMS))),
        # firm_tech_vector: store+resolver, firm_query (not firm)
        lambda: ("firm_tech_vector", firm_tech_vector(store=s, resolver=r,
            firm_query=rng.choice(JP_FIRMS))),
        # applicant_network: store+resolver, applicant (not firm)
        lambda: ("applicant_network", applicant_network(store=s, resolver=r,
            applicant=rng.choice(JP_FIRMS))),
        # patent_compare: store+resolver, firms=[list] (not firm_a/firm_b)
        lambda: ("patent_compare", patent_compare(store=s, resolver=r,
            firms=[f1, f2])),
        lambda: ("corporate_hierarchy", corporate_hierarchy(store=s, resolver=r,
            query=rng.choice(JP_FIRMS))),
        # network_topology: store+resolver, firm (not query)
        lambda: ("network_topology", network_topology(store=s, resolver=r,
            firm=rng.choice(JP_FIRMS))),
    ])

def P5_ip_strategy(s, r, rng):
    """IP Strategy"""
    return rng.choice([
        lambda: ("startability", startability(store=s, resolver=r,
            firm_query=rng.choice(JP_FIRMS),
            tech_query_or_cluster_id=rng.choice(CLUSTER_IDS))),
        lambda: ("startability_ranking", startability_ranking(store=s, resolver=r,
            mode="by_firm", query=rng.choice(JP_FIRMS))),
        lambda: ("startability_delta", startability_delta(store=s, resolver=r,
            mode="by_firm", query=rng.choice(JP_FIRMS))),
        # startability_heatmap: store+resolver, firms=[list] (not firm_query)
        lambda: ("startability_heatmap", startability_heatmap(store=s, resolver=r,
            firms=[rng.choice(JP_FIRMS)])),
        lambda: ("tech_fit", tech_fit(store=s, resolver=r,
            firm_query=rng.choice(JP_FIRMS),
            tech_query_or_cluster_id=rng.choice(CLUSTER_IDS))),
        # sep_search: store only (no resolver)
        lambda: ("sep_search", sep_search(store=s,
            query=rng.choice(["5G","LTE","Wi-Fi","HEVC","AV1"]))),
        # sep_landscape: store only (no resolver)
        lambda: ("sep_landscape", sep_landscape(store=s,
            standard=rng.choice(["5G","LTE","Wi-Fi 6"]))),
        lambda: ("group_startability", group_startability(store=s, resolver=r,
            query=rng.choice(JP_FIRMS),
            cluster_id=rng.choice(CLUSTER_IDS))),
        lambda: ("tech_entropy", tech_entropy(store=s, resolver=r,
            query=rng.choice(JP_FIRMS))),
        # portfolio_benchmark: store+resolver, firm_query (not firm)
        lambda: ("portfolio_benchmark", portfolio_benchmark(store=s,
            firm_query=rng.choice(JP_FIRMS), resolver=r)),
    ])

PERSONAS = {"P1":P1_attorney,"P2":P2_rd_mgr,"P3":P3_investor,"P4":P4_comp_intel,"P5":P5_ip_strategy}

def evaluate(result, tool_name, dur):
    issues = []
    score = 1.0
    if not isinstance(result, dict):
        return 0.0, [("critical","non_dict",str(type(result)))]
    if "error" in result:
        err = str(result["error"])
        if "timeout" in err.lower() or "timed out" in err.lower():
            issues.append(("warn","timeout",err[:200])); score -= 0.5
        elif "no data" in err.lower() or "not found" in err.lower() or "no patent" in err.lower() or "insufficient" in err.lower():
            issues.append(("info","no_data",err[:200])); score -= 0.2
        else:
            issues.append(("error","tool_error",err[:200])); score -= 0.8
        return max(0,score), issues
    if len(result) <= 1:
        issues.append(("warn","tiny_response",f"{len(result)} keys")); score -= 0.3
    nk = [k for k,v in result.items() if v is None and k not in ("_pap_proof","visualization_hint")]
    if nk: issues.append(("info","nulls",str(nk))); score -= 0.02*len(nk)
    ek = [k for k,v in result.items() if isinstance(v,(list,dict)) and len(v)==0 and k not in ("error","warnings","_pap_proof","visualization_hint")]
    if ek: issues.append(("info","empty",str(ek))); score -= 0.02*len(ek)
    if dur > 30: issues.append(("warn","very_slow",f"{dur:.1f}s")); score -= 0.2
    elif dur > 10: issues.append(("info","slow",f"{dur:.1f}s")); score -= 0.05
    return max(0,round(score,3)), issues

def run(n, od):
    store, resolver = setup()
    Path(od).mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    pnames = list(PERSONAS.keys())
    total=ok=err=to=0
    issues_ctr = collections.Counter()
    exc_ctr = collections.Counter()
    tool_ok = collections.Counter()
    tool_err = collections.Counter()
    tool_dur = collections.defaultdict(list)
    p_stats = {p:{"ok":0,"err":0,"scores":[]} for p in pnames}

    with open(f"{od}/qa_log.jsonl","w") as lf:
        for i in range(n):
            pn = pnames[i % len(pnames)]
            try:
                task = PERSONAS[pn](store, resolver, rng)
                t0 = time.time()
                tn, result = task()
                dur = time.time()-t0
                total += 1
                is_err = isinstance(result,dict) and "error" in result
                is_to = is_err and ("timeout" in str(result.get("error","")).lower())
                q, iss = evaluate(result, tn, dur)
                if is_err: err+=1; p_stats[pn]["err"]+=1; tool_err[tn]+=1
                else: ok+=1; p_stats[pn]["ok"]+=1; tool_ok[tn]+=1
                if is_to: to+=1
                p_stats[pn]["scores"].append(q)
                tool_dur[tn].append(dur)
                for s,t,d in iss: issues_ctr[f"{s}:{t}"]+=1
                lf.write(json.dumps({"i":i,"p":pn,"t":tn,"dur":round(dur,2),
                    "q":q,"err":is_err,"to":is_to,"iss":[(s,t) for s,t,_ in iss],
                    "keys":list(result.keys()) if isinstance(result,dict) else []},
                    ensure_ascii=False,default=str)+"\n")
                lf.flush()
            except Exception as e:
                total+=1; err+=1; p_stats[pn]["err"]+=1
                etype = type(e).__name__
                emsg = str(e)[:200]
                exc_ctr[f"{etype}: {emsg}"]+=1
                lf.write(json.dumps({"i":i,"p":pn,"t":"EXCEPTION","dur":0,
                    "q":0,"err":True,"to":False,"exc":etype,"msg":emsg},
                    ensure_ascii=False,default=str)+"\n")
                lf.flush()
            if (i+1)%50==0:
                rate=ok/total*100 if total else 0
                print(f"  [{i+1}/{n}] ok={ok} err={err} to={to} rate={rate:.1f}% exc={sum(exc_ctr.values())}",flush=True)

    # Summary
    rate = ok/total*100 if total else 0
    summary = {
        "ts": datetime.now().isoformat(), "n": n, "total": total,
        "ok": ok, "err": err, "to": to, "rate": round(rate,1),
        "persona_stats": {p:{"ok":v["ok"],"err":v["err"],
            "avg_q":round(sum(v["scores"])/len(v["scores"]),3) if v["scores"] else 0}
            for p,v in p_stats.items()},
        "tool_success": {t:{"ok":tool_ok.get(t,0),"err":tool_err.get(t,0),
            "med_dur":round(sorted(tool_dur[t])[len(tool_dur[t])//2],2) if tool_dur[t] else 0}
            for t in sorted(set(list(tool_ok.keys())+list(tool_err.keys())))},
        "top_issues": issues_ctr.most_common(20),
        "top_exceptions": exc_ctr.most_common(20),
    }
    with open(f"{od}/summary.json","w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n{'='*60}")
    print(f"DONE: {n} iterations — ok={ok}/{total} ({rate:.1f}%)")
    print(f"Errors: {err} (timeout: {to}, exceptions: {sum(exc_ctr.values())})")
    if exc_ctr:
        print(f"\nTop exceptions:")
        for k,c in exc_ctr.most_common(10): print(f"  {c:3d}x {k}")
    if issues_ctr:
        print(f"\nTop issues:")
        for k,c in issues_ctr.most_common(10): print(f"  {c:3d}x {k}")
    print(f"\nPer-persona:")
    for p,v in p_stats.items():
        avgq = round(sum(v["scores"])/len(v["scores"]),3) if v["scores"] else 0
        print(f"  {p}: ok={v['ok']} err={v['err']} avg_q={avgq}")
    print(f"{'='*60}")
    return summary

if __name__=="__main__":
    n=int(sys.argv[1]) if len(sys.argv)>1 else 300
    od=sys.argv[2] if len(sys.argv)>2 else "/tmp/qa_v2"
    run(n, od)
