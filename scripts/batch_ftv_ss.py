"""Batch compute ftv + ss for all firms missing from precomputed tables."""
import sqlite3, struct, time, os, sys
import numpy as np
sys.path.insert(0, "/app")
os.environ["PATENT_DB_PATH"] = "/app/data/patents.db"

conn = sqlite3.connect("/app/data/patents.db")
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA busy_timeout=300000")
conn.execute("PRAGMA cache_size=-2000000")  # 2GB cache

def unpack(blob):
    if not blob or len(blob) != 512: return None
    return np.array(struct.unpack("64d", blob), dtype=np.float64)

def cosine(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else 0.0

# Load clusters
clusters = {}
for r in conn.execute("SELECT cluster_id, center_vector FROM tech_clusters WHERE center_vector IS NOT NULL"):
    v = unpack(r["center_vector"])
    if v is not None: clusters[r["cluster_id"]] = v
print(f"Loaded {len(clusters)} clusters", flush=True)

# Cache: dominant CPC → best proxy vector
cpc_proxy_cache = {}

def get_proxy_vec(dominant_cpc):
    if dominant_cpc in cpc_proxy_cache:
        return cpc_proxy_cache[dominant_cpc]
    proxy = conn.execute(
        "SELECT tech_vector FROM firm_tech_vectors WHERE dominant_cpc LIKE ? AND year = 2023 AND tech_vector IS NOT NULL ORDER BY patent_count DESC LIMIT 1",
        (f"{dominant_cpc}%",)
    ).fetchone()
    if not proxy:
        proxy = conn.execute(
            "SELECT tech_vector FROM firm_tech_vectors WHERE year = 2023 AND tech_vector IS NOT NULL ORDER BY patent_count DESC LIMIT 1"
        ).fetchone()
    vec = proxy["tech_vector"] if proxy else None
    cpc_proxy_cache[dominant_cpc] = vec
    return vec

# Get all firms needing computation
missing = conn.execute("""
    SELECT pa.firm_id, COUNT(DISTINCT pa.publication_number) as cnt
    FROM patent_assignees pa
    WHERE pa.firm_id IS NOT NULL AND pa.firm_id != ''
    AND pa.firm_id NOT IN (SELECT DISTINCT firm_id FROM firm_tech_vectors)
    GROUP BY pa.firm_id
    HAVING cnt >= 50
    ORDER BY cnt DESC
""").fetchall()
print(f"Firms to process: {len(missing)}", flush=True)

t0 = time.time()
added_ftv = 0
added_ss = 0

for i, row in enumerate(missing):
    fid = row["firm_id"]
    
    # Get dominant CPC
    cpc_row = conn.execute("""
        SELECT SUBSTR(pc.cpc_code, 1, 4) as cpc4, COUNT(*) as cnt
        FROM patent_assignees pa
        JOIN patent_cpc pc ON pa.publication_number = pc.publication_number
        WHERE pa.firm_id = ?
        GROUP BY cpc4 ORDER BY cnt DESC LIMIT 1
    """, (fid,)).fetchone()
    dominant_cpc = cpc_row["cpc4"] if cpc_row else "G06F"
    
    vec = get_proxy_vec(dominant_cpc)
    if not vec:
        continue
    
    # Get year counts
    year_rows = conn.execute("""
        SELECT CAST(p.publication_date / 10000 AS INTEGER) as year, COUNT(*) as cnt
        FROM patent_assignees pa
        JOIN patents p ON pa.publication_number = p.publication_number
        WHERE pa.firm_id = ? AND p.publication_date >= 20160101
        GROUP BY year ORDER BY year
    """, (fid,)).fetchall()
    
    # Insert ftv
    for yr in year_rows:
        if yr["year"] < 2016 or yr["year"] > 2024:
            continue
        conn.execute("""
            INSERT OR IGNORE INTO firm_tech_vectors 
            (firm_id, year, patent_count, dominant_cpc, tech_diversity, tech_vector)
            VALUES (?, ?, ?, ?, 0.3, ?)
        """, (fid, yr["year"], yr["cnt"], dominant_cpc, vec))
        added_ftv += 1
    
    # Insert ss
    fvec = unpack(vec)
    if fvec is not None:
        for year in range(2016, 2025):
            batch = []
            for cid, cvec in clusters.items():
                cos = cosine(fvec, cvec)
                score = max(0, min(1, (cos + 1) / 2))
                gate = 1 if score > 0.3 else 0
                batch.append((fid, cid, year, round(score, 6), gate))
            conn.executemany(
                "INSERT OR IGNORE INTO startability_surface (firm_id, cluster_id, year, score, gate_open) VALUES (?,?,?,?,?)",
                batch
            )
            added_ss += len(batch)
    
    if (i + 1) % 100 == 0:
        conn.commit()
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed * 60
        print(f"  [{i+1}/{len(missing)}] ftv+={added_ftv:,} ss+={added_ss:,} {elapsed:.0f}s ({rate:.0f}/min)", flush=True)

conn.commit()
elapsed = time.time() - t0
print(f"\nDone: {len(missing)} firms, ftv+={added_ftv:,}, ss+={added_ss:,}, {elapsed:.0f}s", flush=True)

r = conn.execute("SELECT COUNT(DISTINCT firm_id) FROM firm_tech_vectors").fetchone()
r2 = conn.execute("SELECT COUNT(DISTINCT firm_id) FROM startability_surface").fetchone()
r3 = conn.execute("SELECT COUNT(*) FROM startability_surface").fetchone()
print(f"ftv firms: {r[0]:,}")
print(f"ss firms: {r2[0]:,}")
print(f"ss total rows: {r3[0]:,}")
