"""Recompute startability_surface — correct version using center_vector."""
import os, sys, time, sqlite3, struct
sys.path.insert(0, "/app")
os.environ["PATENT_DB_PATH"] = "/app/data/patents.db"

conn = sqlite3.connect("/app/data/patents.db")
conn.row_factory = sqlite3.Row

# Get cluster center vectors
print("Loading cluster vectors...", flush=True)
clusters = {}
for r in conn.execute("SELECT cluster_id, center_vector FROM tech_clusters WHERE center_vector IS NOT NULL"):
    blob = r["center_vector"]
    n = len(blob) // 4
    clusters[r["cluster_id"]] = struct.unpack(f"{n}f", blob)
print(f"  {len(clusters)} clusters loaded", flush=True)

# Find firms to recompute
missing = [r[0] for r in conn.execute("""
    SELECT DISTINCT firm_id FROM firm_tech_vectors
    WHERE firm_id NOT IN (SELECT DISTINCT firm_id FROM startability_surface)
""").fetchall()]

incomplete = [r[0] for r in conn.execute("""
    SELECT firm_id FROM startability_surface WHERE year = 2024
    GROUP BY firm_id HAVING COUNT(*) < 600
""").fetchall()]

all_firms = sorted(set(missing + incomplete))
print(f"Firms to process: {len(all_firms)} (missing={len(missing)}, incomplete={len(incomplete)})", flush=True)

def cosine(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = sum(x*x for x in a) ** 0.5
    nb = sum(x*x for x in b) ** 0.5
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return dot / (na * nb)

done = 0
errors = 0
t0 = time.time()

for i, firm_id in enumerate(all_firms):
    # Get firm vectors for recent years
    years_data = conn.execute(
        "SELECT year, tech_vector FROM firm_tech_vectors WHERE firm_id = ? AND tech_vector IS NOT NULL ORDER BY year",
        (firm_id,)
    ).fetchall()
    
    if not years_data:
        continue
    
    for row in years_data[-3:]:  # Last 3 years
        year = row["year"]
        blob = row["tech_vector"]
        if not blob:
            continue
        n = len(blob) // 4
        firm_vec = struct.unpack(f"{n}f", blob)
        
        batch = []
        for cid, cvec in clusters.items():
            if len(firm_vec) != len(cvec):
                continue
            cos = cosine(firm_vec, cvec)
            score = max(0, min(1, (cos + 1) / 2))
            gate = 1 if score > 0.3 else 0
            batch.append((firm_id, cid, year, round(score, 6), gate))
        
        if batch:
            conn.executemany(
                "INSERT OR REPLACE INTO startability_surface (firm_id, cluster_id, year, score, gate_open) VALUES (?,?,?,?,?)",
                batch
            )
            done += 1
    
    if (i + 1) % 20 == 0:
        conn.commit()
        elapsed = time.time() - t0
        print(f"  [{i+1}/{len(all_firms)}] done={done} err={errors} {elapsed:.0f}s", flush=True)

conn.commit()
print(f"\nDone: {done} firm-years, {errors} errors, {time.time()-t0:.0f}s", flush=True)
for r in conn.execute("SELECT COUNT(DISTINCT firm_id) FROM startability_surface"):
    print(f"Total firms in ss: {r[0]}")
for r in conn.execute("SELECT COUNT(*) FROM startability_surface WHERE firm_id='company_6758' AND year=2024"):
    print(f"sony 2024: {r[0]} clusters")
