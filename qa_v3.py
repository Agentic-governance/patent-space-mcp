"""QA v3 — fast tools only (pre-computed), 30s timeout per call, 300 iterations."""
from __future__ import annotations
import json,os,sys,time,traceback,random,collections,signal
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/app")
os.environ["PATENT_DB_PATH"] = "/app/data/patents.db"

from db.sqlite_store import PatentStore
from entity.registry import EntityRegistry
from entity.resolver import EntityResolver
from entity.data.tse_prime_seed import TSE_PRIME_ENTITIES
from entity.data.tse_expanded_seed import TSE_EXPANDED_ENTITIES
from entity.data.tse_auto_seed import TSE_AUTO_ENTITIES
try: from entity.data.sp500_seed import SP500_ENTITIES
except: SP500_ENTITIES = []
try: from entity.data.global_seed import GLOBAL_ENTITIES
except: GLOBAL_ENTITIES = []

store = PatentStore("/app/data/patents.db")
reg = EntityRegistry()
for lst in [TSE_PRIME_ENTITIES,TSE_EXPANDED_ENTITIES,TSE_AUTO_ENTITIES,SP500_ENTITIES,GLOBAL_ENTITIES]:
    for e in lst: reg.register(e)
resolver = EntityResolver(reg)

from tools.startability_tool import startability, startability_ranking
from tools.startability_delta import startability_delta
from tools.tech_fit import tech_fit
from tools.similar_firms import similar_firms
from tools.adversarial import adversarial_strategy
from tools.tech_gap import tech_gap
from tools.patent_valuation import patent_valuation
from tools.claim_analysis import fto_analysis, claim_analysis
from tools.portfolio import firm_patent_portfolio
from tools.tech_trend import tech_trend
from tools.cross_domain import cross_domain_discovery
from tools.patent_finance import patent_option_value, tech_volatility, portfolio_var, tech_beta
from tools.bayesian_scenario import bayesian_scenario
from tools.network_analysis import network_topology, knowledge_flow, tech_fusion_detector, tech_entropy
from tools.sep_analysis import sep_search, sep_landscape
from tools.ptab import ptab_search, ptab_risk, litigation_search, litigation_risk
from tools.corporate_hierarchy import corporate_hierarchy, group_startability
from tools.sales_prospect import sales_prospect
from tools.ma_target import ma_target
from tools.patent_summary import technology_brief
from tools.visualization import startability_heatmap
from tools.ip_due_diligence import ip_due_diligence
from tools.compare import patent_compare
from tools.clusters import tech_clusters_list
from tools.network import applicant_network
from tools.vectors import firm_tech_vector
from tools.cross_border import cross_border_similarity
from tools.invention_intel import invention_intelligence
from tools.portfolio_evolution import portfolio_evolution

JP = ["トヨタ","ホンダ","ソニー","パナソニック","日立","キヤノン","東芝",
      "三菱電機","デンソー","日産","NEC","富士通","シャープ","京セラ",
      "オムロン","ファナック","村田製作所","TDK","ブリヂストン","旭化成"]
CPC = ["H01M","H01L","G06N","B60W","H04W","A61K","B25J","G01N",
       "H02S","C08L","G06F","H04N","B01J","F02D","G02B","C07K","B60L","G06T","A61B"]
CL = [f"{c}_0" for c in CPC]
s,r,S = store, resolver, store

class TimeoutError(Exception): pass
def timeout_handler(signum, frame): raise TimeoutError("Call timed out")

def safe_call(fn, timeout=30):
    """Call fn with timeout."""
    old = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    try:
        result = fn()
        signal.alarm(0)
        return result
    except TimeoutError:
        return {"error": "Timed out after 30s"}
    finally:
        signal.signal(signal.SIGALRM, old)

# ALL tasks (name, callable) — only fast-path or moderate tools
def all_tasks(rng):
    f1,f2 = rng.sample(JP,2)
    f = rng.choice(JP)
    c = rng.choice(CPC)
    cl = rng.choice(CL)
    return [
        # P1: Attorney
        ("fto_analysis", lambda: fto_analysis(store=S, text=rng.choice(["全固体電池","自動運転LiDAR","mRNA医薬","量子暗号"]), cpc_codes=[c])),
        ("litigation_risk", lambda: litigation_risk(store=S, resolver=r, firm_query=f)),
        ("ptab_risk", lambda: ptab_risk(store=S, resolver=r, cpc_prefix=c)),
        ("litigation_search", lambda: litigation_search(store=S, resolver=r, plaintiff=f)),
        ("ptab_search", lambda: ptab_search(store=S, resolver=r, patent_owner=f)),
        ("ip_due_diligence", lambda: ip_due_diligence(store=S, resolver=r, query=f)),
        # P2: R&D
        ("cross_domain", lambda: cross_domain_discovery(store=S, query=c, top_n=5)),
        ("invention_intel", lambda: invention_intelligence(store=S, resolver=r, text=rng.choice(["水素燃料電池","エッジAI","バイオプラスチック","6G通信"]), max_results=5)),
        ("tech_trend", lambda: tech_trend(store=S, resolver=r, query=c)),
        ("tech_clusters", lambda: tech_clusters_list(store=S, cpc_filter=c[:3])),
        ("technology_brief", lambda: technology_brief(store=S, cpc_prefix=c)),
        ("knowledge_flow", lambda: knowledge_flow(store=S, resolver=r, source_cpc=rng.choice(CPC[:10]), target_cpc=rng.choice(CPC[10:]))),
        ("tech_fusion", lambda: tech_fusion_detector(store=S, resolver=r, query=f)),
        # P3: Investor
        ("patent_valuation", lambda: patent_valuation(store=S, resolver=r, query=f, query_type="firm")),
        ("patent_option_value", lambda: patent_option_value(store=S, resolver=r, query=f)),
        ("portfolio_var", lambda: portfolio_var(store=S, resolver=r, firm=f)),
        ("tech_volatility", lambda: tech_volatility(store=S, resolver=r, query=c)),
        ("tech_beta", lambda: tech_beta(store=S, resolver=r, query=f)),
        ("bayesian_scenario", lambda: bayesian_scenario(store=S, resolver=r, mode="init", technology=cl, firm_query=f)),
        ("ma_target", lambda: ma_target(store=S, resolver=r, acquirer=f, top_n=3)),
        ("sales_prospect", lambda: sales_prospect(store=S, resolver=r, firm_query=f, patent_or_tech=cl)),
        # P4: Competitive Intel
        ("adversarial", lambda: adversarial_strategy(store=S, resolver=r, firm_a=f1, firm_b=f2)),
        ("similar_firms", lambda: similar_firms(store=S, resolver=r, firm_query=f, top_n=3)),
        ("tech_gap", lambda: tech_gap(store=S, resolver=r, firm_a=f1, firm_b=f2)),
        ("patent_compare", lambda: patent_compare(store=S, resolver=r, firms=[f1,f2])),
        ("firm_tech_vector", lambda: firm_tech_vector(store=S, resolver=r, firm_query=f)),
        ("applicant_network", lambda: applicant_network(store=S, resolver=r, applicant=f)),
        ("corporate_hierarchy", lambda: corporate_hierarchy(store=S, resolver=r, query=f)),
        ("network_topology", lambda: network_topology(store=S, resolver=r, firm=f)),
        # P5: IP Strategy
        ("startability", lambda: startability(store=S, resolver=r, firm_query=f, tech_query_or_cluster_id=cl)),
        ("startability_ranking", lambda: startability_ranking(store=S, resolver=r, mode="by_firm", query=f)),
        ("startability_delta", lambda: startability_delta(store=S, resolver=r, mode="by_firm", query=f)),
        ("startability_heatmap", lambda: startability_heatmap(store=S, resolver=r, firms=[f])),
        ("tech_fit", lambda: tech_fit(store=S, resolver=r, firm_query=f, tech_query_or_cluster_id=cl)),
        ("sep_search", lambda: sep_search(store=S, query=rng.choice(["5G","LTE","Wi-Fi","HEVC"]))),
        ("sep_landscape", lambda: sep_landscape(store=S, standard=rng.choice(["5G","LTE","Wi-Fi 6"]))),
        ("group_startability", lambda: group_startability(store=S, resolver=r, query=f, cluster_id=cl)),
        ("tech_entropy", lambda: tech_entropy(store=S, resolver=r, query=f)),
        ("cross_border", lambda: cross_border_similarity(store=S, resolver=r, query=f)),
        ("portfolio_evolution", lambda: portfolio_evolution(store=S, resolver=r, firm=f)),
        ("firm_portfolio", lambda: firm_patent_portfolio(store=S, resolver=r, firm=f)),
    ]

rng = random.Random(42)
N = int(sys.argv[1]) if len(sys.argv)>1 else 300
od = sys.argv[2] if len(sys.argv)>2 else "/tmp/qa_v3"
Path(od).mkdir(parents=True, exist_ok=True)

ok=err=exc=to=0
tool_ok=collections.Counter(); tool_err=collections.Counter(); tool_dur=collections.defaultdict(list)
iss_ctr=collections.Counter(); exc_ctr=collections.Counter()

with open(f"{od}/qa_log.jsonl","w") as lf:
    for i in range(N):
        tasks = all_tasks(rng)
        tn, fn = rng.choice(tasks)
        t0 = time.time()
        try:
            result = safe_call(fn, timeout=30)
            dur = time.time()-t0
            is_err = isinstance(result,dict) and "error" in result
            is_to = is_err and "timed out" in str(result.get("error","")).lower()
            q = 1.0
            issues = []
            if is_err:
                err+=1; tool_err[tn]+=1
                emsg = str(result.get("error",""))[:200]
                if is_to: to+=1; issues.append(("warn","timeout",emsg)); q=0.3
                elif any(x in emsg.lower() for x in ["no data","not found","insufficient","no patent"]):
                    issues.append(("info","no_data",emsg)); q=0.7
                else: issues.append(("error","tool_error",emsg)); q=0.2
            else:
                ok+=1; tool_ok[tn]+=1
                if isinstance(result,dict):
                    ek=[k for k,v in result.items() if isinstance(v,(list,dict)) and len(v)==0 and k not in ("error","warnings","_pap_proof","visualization_hint")]
                    if ek: issues.append(("info","empty",str(ek))); q-=0.02*len(ek)
                    nk=[k for k,v in result.items() if v is None and k not in ("_pap_proof","visualization_hint")]
                    if nk: issues.append(("info","nulls",str(nk))); q-=0.01*len(nk)
                if dur>15: issues.append(("warn","slow",f"{dur:.1f}s")); q-=0.1
            tool_dur[tn].append(dur)
            for s2,t2,_ in issues: iss_ctr[f"{s2}:{t2}"]+=1
            lf.write(json.dumps({"i":i,"t":tn,"dur":round(dur,2),"q":round(max(0,q),3),"err":is_err,"to":is_to,"iss":[(s2,t2) for s2,t2,_ in issues]},ensure_ascii=False)+"\n")
            lf.flush()
        except Exception as e:
            dur = time.time()-t0
            exc+=1; err+=1
            etype=type(e).__name__; emsg=str(e)[:200]
            exc_ctr[f"{etype}: {emsg}"]+=1
            tool_err[tn]+=1
            lf.write(json.dumps({"i":i,"t":tn,"dur":round(dur,2),"q":0,"err":True,"to":False,"exc":etype,"msg":emsg},ensure_ascii=False)+"\n")
            lf.flush()
        if (i+1)%50==0:
            total=ok+err
            print(f"  [{i+1}/{N}] ok={ok}({ok*100//max(total,1)}%) err={err-exc} exc={exc} to={to}",flush=True)

total=ok+err
rate=ok*100//max(total,1)
summary = {
    "n":N,"total":total,"ok":ok,"err":err-exc,"exc":exc,"to":to,"rate":rate,
    "tools":{t:{"ok":tool_ok.get(t,0),"err":tool_err.get(t,0),
        "med":round(sorted(tool_dur[t])[len(tool_dur[t])//2],2) if tool_dur[t] else 0}
        for t in sorted(set(list(tool_ok)+list(tool_err)))},
    "issues":iss_ctr.most_common(20),
    "exceptions":exc_ctr.most_common(20),
}
with open(f"{od}/summary.json","w") as f: json.dump(summary,f,indent=2,ensure_ascii=False,default=str)
print(f"\nDONE: {N} iterations — ok={ok}/{total} ({rate}%)")
print(f"Errors: {err-exc}, Exceptions: {exc}, Timeouts: {to}")
if exc_ctr:
    print("Exceptions:")
    for k,c in exc_ctr.most_common(10): print(f"  {c}x {k}")
if iss_ctr:
    print("Issues:")
    for k,c in iss_ctr.most_common(10): print(f"  {c}x {k}")
