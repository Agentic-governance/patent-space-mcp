"""Fast-path PAP benchmark v2 — fixed resolver."""
from __future__ import annotations
import json, os, statistics, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
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

from pap.config import PAPConfig, PAPLevel
from pap.context import PAPContext
from pap.proof import compute_artifact_hash, compute_cmd_hash, generate_proof, verify_proof
from pap.chain import HashChain


def _setup():
    store = PatentStore(os.environ["PATENT_DB_PATH"])
    reg = EntityRegistry()
    for e in TSE_PRIME_ENTITIES + TSE_EXPANDED_ENTITIES + TSE_AUTO_ENTITIES + SP500_ENTITIES:
        reg.register(e)
    resolver = EntityResolver(reg)
    return store, resolver


def bench(store, resolver, fn, tname, params, level, n=10):
    results = []
    for i in range(n):
        os.environ["PAP_LEVEL"] = str(int(level))
        cfg = PAPConfig()
        t0 = time.time()
        
        if level == PAPLevel.DISABLED:
            r = fn(store=store, resolver=resolver, **params)
            t1 = time.time()
            results.append({"run":i,"level":int(level),"tool":tname,
                "call_lat":round(t1-t0,6),"total_lat":round(t1-t0,6),
                "pg":0,"vt":0,"ps":0,"ls":0,"ec":0,
                "err":isinstance(r,dict) and "error" in r})
        elif level == PAPLevel.ADHOC:
            log = [{"ts":time.time(),"tool":tname,"p":list(params.keys())}]
            r = fn(store=store, resolver=resolver, **params)
            log.append({"ts":time.time(),"tool":tname,"ok":True})
            t1 = time.time()
            lj = json.dumps(log, default=str)
            results.append({"run":i,"level":int(level),"tool":tname,
                "call_lat":round(t1-t0,6),"total_lat":round(t1-t0,6),
                "pg":0,"vt":0,"ps":0,"ls":len(lj.encode()),"ec":2,
                "err":isinstance(r,dict) and "error" in r})
        else:
            ctx = PAPContext(cfg, tname, params)
            with ctx:
                ctx.log_event("tool.input", tname, {"p":list(params.keys())})
                tc = time.time()
                r = fn(store=store, resolver=resolver, **params)
                cd = time.time()-tc
                ctx.log_event("tool.exec", tname, {"dur":round(cd,4)})
                if isinstance(r, dict) and "error" not in r:
                    ctx.log_event("tool.output", tname, {"keys":list(r.keys())})
                ctx.bind_artifact(r)
            t1 = time.time()
            tp0=time.time()
            c2=HashChain("m")
            for e in ctx.chain.events: c2.append(e.event_type,e.tool_name,e.payload)
            ch=compute_cmd_hash(tname,params); ah=compute_artifact_hash(r)
            pf=generate_proof(cfg,"m",c2,ch,ah,[tname],0)
            pg=time.time()-tp0
            tv0=time.time(); verify_proof(cfg,pf); vt=time.time()-tv0
            results.append({"run":i,"level":int(level),"tool":tname,
                "call_lat":round(cd,6),"total_lat":round(t1-t0,6),
                "pg":round(pg,6),"vt":round(vt,6),
                "ps":pf.size_bytes(),"ls":c2.size_bytes(),"ec":c2.length,
                "err":isinstance(r,dict) and "error" in r})
    return results


def stats(vals):
    if not vals: return {}
    if len(vals)<2: return {"mean":round(vals[0],6),"med":round(vals[0],6),"p95":round(vals[0],6),"std":0}
    s=sorted(vals)
    return {"mean":round(statistics.mean(s),6),"med":round(statistics.median(s),6),
            "p95":round(s[min(int(len(s)*0.95),len(s)-1)],6),"std":round(statistics.stdev(s),6)}


if __name__=="__main__":
    n=int(sys.argv[1]) if len(sys.argv)>1 else 10
    od=sys.argv[2] if len(sys.argv)>2 else "/tmp/pap_bench2"
    Path(od).mkdir(parents=True, exist_ok=True)
    store,resolver=_setup()
    
    from tools.startability_tool import startability
    from tools.tech_fit import tech_fit
    from tools.similar_firms import similar_firms
    from tools.adversarial import adversarial_strategy
    from tools.tech_gap import tech_gap
    from tools.portfolio import firm_patent_portfolio
    
    tasks=[
        ("startability", startability, {"firm_query":"トヨタ","tech_query_or_cluster_id":"H01M_0","year":2024}),
        ("tech_fit", tech_fit, {"firm_query":"トヨタ","tech_query_or_cluster_id":"H01M_0","year":2024}),
        ("similar_firms", similar_firms, {"firm_query":"トヨタ","top_n":5}),
        ("adversarial", adversarial_strategy, {"firm_a":"トヨタ","firm_b":"ホンダ","year":2023}),
        ("tech_gap", tech_gap, {"firm_a":"トヨタ","firm_b":"ホンダ","year":2024}),
        ("portfolio", firm_patent_portfolio, {"firm":"トヨタ"}),
    ]
    
    levels=[PAPLevel.DISABLED, PAPLevel.ADHOC, PAPLevel.LEVEL0, PAPLevel.LEVEL1]
    ln={-1:"B0",0:"B1",1:"B2",2:"B3"}
    
    raw=[]; summaries=[]
    for tname,fn,params in tasks:
        for lv in levels:
            print(f"  {tname}/{ln[int(lv)]} x{n}...",end=" ",flush=True)
            try:
                rs=bench(store,resolver,fn,tname,params,lv,n)
                ok=[r for r in rs if not r["err"]]
                if ok:
                    s={"task":tname,"regime":ln[int(lv)],"n_ok":len(ok),"n_err":len(rs)-len(ok),
                       "total_lat":stats([r["total_lat"] for r in ok]),
                       "call_lat":stats([r["call_lat"] for r in ok]),
                       "proof_gen":stats([r["pg"] for r in ok]),
                       "verify":stats([r["vt"] for r in ok]),
                       "proof_size":ok[0]["ps"],"log_size":ok[0]["ls"],"events":ok[0]["ec"]}
                    summaries.append(s)
                    print(f"med={s['total_lat']['med']}s ps={s['proof_size']}B")
                else:
                    summaries.append({"task":tname,"regime":ln[int(lv)],"error":"all_failed"})
                    print("ALL FAILED")
                raw.extend(rs)
            except Exception as e:
                print(f"ERR: {e}")
                summaries.append({"task":tname,"regime":ln[int(lv)],"error":str(e)})
    
    with open(f"{od}/raw.jsonl","w") as f:
        for r in raw: f.write(json.dumps(r,ensure_ascii=False,default=str)+"\n")
    with open(f"{od}/summary.json","w") as f:
        json.dump(summaries,f,indent=2,ensure_ascii=False)
    print(f"\nDone: {len(raw)} raw, {len(summaries)} summaries -> {od}/")
