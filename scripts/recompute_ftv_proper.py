"""Recompute firm_tech_vectors using ACTUAL patent embeddings (not proxy).

For each firm: average all patent embeddings → firm tech vector.
This replaces the proxy-copied vectors with proper firm-specific vectors.
"""
import sqlite3, struct, time, os, sys
import numpy as np

sys.path.insert(0, "/app")
os.environ["PATENT_DB_PATH"] = "/app/data/patents.db"

conn = sqlite3.connect("/app/data/patents.db")
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA busy_timeout=300000")
conn.execute("PRAGMA cache_size=-2000000")

def pack_vec(arr):
    return struct.pack(f"{len(arr)}d", *arr)

def unpack_vec(blob):
    if not blob or len(blob) != 512: return None
    return np.array(struct.unpack("64d", blob), dtype=np.float64)

# Get all firms that need recomputation (those with duplicated/proxy vectors)
# Strategy: recompute ALL firms in ftv from their actual patent embeddings

firms = conn.execute("""
    SELECT DISTINCT firm_id FROM firm_tech_vectors
    WHERE firm_id IN (
        SELECT pa.firm_id FROM patent_assignees pa
        JOIN patent_research_data prd ON pa.publication_number = prd.publication_number
        WHERE pa.firm_id IS NOT NULL AND prd.embedding_v1 IS NOT NULL
        GROUP BY pa.firm_id
        HAVING COUNT(*) >= 5
    )
    ORDER BY firm_id
""").fetchall()

firm_ids = [r["firm_id"] for r in firms]
print(f"Firms to recompute: {len(firm_ids)}", flush=True)

t0 = time.time()
updated = 0
errors = 0

for i, fid in enumerate(firm_ids):
    try:
        # Get all patent embeddings for this firm, grouped by year
        year_vecs = {}
        rows = conn.execute("""
            SELECT CAST(p.publication_date / 10000 AS INTEGER) as year,
                   prd.embedding_v1
            FROM patent_assignees pa
            JOIN patents p ON pa.publication_number = p.publication_number
            JOIN patent_research_data prd ON pa.publication_number = prd.publication_number
            WHERE pa.firm_id = ? AND prd.embedding_v1 IS NOT NULL
            AND p.publication_date >= 20160101
        """, (fid,)).fetchall()
        
        for r in rows:
            yr = r["year"]
            if yr < 2016 or yr > 2024:
                continue
            vec = unpack_vec(r["embedding_v1"])
            if vec is not None:
                year_vecs.setdefault(yr, []).append(vec)
        
        if not year_vecs:
            continue
        
        # Also compute cumulative vector (all years combined) for latest year
        all_vecs = []
        for vecs in year_vecs.values():
            all_vecs.extend(vecs)
        
        # For each year, compute average embedding
        for yr, vecs in year_vecs.items():
            avg_vec = np.mean(vecs, axis=0)
            # Normalize
            norm = np.linalg.norm(avg_vec)
            if norm > 0:
                avg_vec = avg_vec / norm * 0.5  # Scale to match existing vector norms (~0.5-0.7)
            
            packed = pack_vec(avg_vec)
            conn.execute("""
                UPDATE firm_tech_vectors SET tech_vector = ?, patent_count = ?
                WHERE firm_id = ? AND year = ?
            """, (packed, len(vecs), fid, yr))
        
        updated += 1
        
    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  Error {fid}: {e}", flush=True)
    
    if (i + 1) % 200 == 0:
        conn.commit()
        elapsed = time.time() - t0
        print(f"  [{i+1}/{len(firm_ids)}] updated={updated} errors={errors} {elapsed:.0f}s", flush=True)

conn.commit()
elapsed = time.time() - t0
print(f"\nDone: {updated}/{len(firm_ids)} firms recomputed, {errors} errors, {elapsed:.0f}s", flush=True)

# Verify: check distinct vectors now
rows = conn.execute("SELECT tech_vector FROM firm_tech_vectors WHERE year=2023 AND tech_vector IS NOT NULL").fetchall()
vecs = set()
for r in rows:
    vecs.add(r[0])
print(f"Distinct vectors (2023): {len(vecs)}/{len(rows)} ({100*len(vecs)/len(rows):.1f}%)")

# Verify Tesla
t = conn.execute("SELECT tech_vector FROM firm_tech_vectors WHERE firm_id='tesla' AND year=2023").fetchone()
s = conn.execute("SELECT tech_vector FROM firm_tech_vectors WHERE firm_id='sumitomo_chemical' AND year=2023").fetchone()
if t and s:
    tv = unpack_vec(t["tech_vector"])
    sv = unpack_vec(s["tech_vector"])
    cos = float(np.dot(tv, sv) / (np.linalg.norm(tv) * np.linalg.norm(sv)))
    print(f"cosine(tesla, sumitomo_chemical) = {cos:.4f}")
