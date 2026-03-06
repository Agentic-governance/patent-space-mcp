# Startability Engine — Technical Documentation

## Overview

Startability measures a firm's readiness to enter or compete in a technology area.
It combines three dimensions:

```
S(firm, tech, year) = w1 * phi_tech + w2 * phi_org + w3 * phi_dyn
```

Where:
- **phi_tech** (Technology Fit): How well the firm's patent portfolio aligns with the target technology
- **phi_org** (Organizational Capability): Firm-level capacity metrics (patent volume, diversity, concentration)
- **phi_dyn** (Dynamic Trajectory): How the firm's position is changing over time

---

## Components

### phi_tech (Technology Fit)

Computed by `tech_fit` tool. Three sub-components:

1. **CPC Overlap Ratio** (weight: 0.5)
   - Jaccard similarity between firm's CPC codes and cluster's CPC codes
   - Source: `firm_tech_vectors.tech_vector` (607-dim binary) vs cluster CPC set

2. **Citation Proximity** (weight: 0.3)
   - Fraction of firm's patents that cite or are cited by patents in the target cluster
   - Source: `patent_citations` table, `patent_cluster_mapping`

3. **Co-inventor Score** (weight: 0.2)
   - Whether the firm has inventors who also appear in patents of the target cluster
   - Source: `patent_inventors` table (when available)

### phi_org (Organizational Capability)

Derived from `firm_tech_vectors`:

- **Patent count**: Raw filing volume (log-scaled, normalized)
- **Tech diversity**: Shannon entropy of CPC distribution (range 0-6, normalized / 5.0)
- **Tech concentration**: Herfindahl index on CPC classes (inverted = more diverse is better)

### phi_dyn (Dynamic Trajectory)

Year-over-year change in tech_fit score:

```
phi_dyn = (tech_fit[year] - tech_fit[year-2]) / 2
```

Positive = firm is moving toward the technology. Negative = retreating.

---

## Pre-computed Data

### startability_surface table

10,267,405 rows pre-computed via BigQuery, covering:
- ~4,300 firms × 607 clusters × multiple years (2016-2024)
- Columns: `firm_id, cluster_id, year, score, phi_tech, phi_org, phi_dyn`

This enables sub-second lookups via `startability` and `startability_ranking` tools.

### firm_tech_vectors table

27,800 rows (firm × year), each containing:
- `firm_id`: Canonical firm identifier
- `year`: 2015-2024
- `patent_count`: Total patents filed that year
- `dominant_cpc`: Most common CPC subclass
- `tech_diversity`: Shannon entropy (0-6)
- `tech_concentration`: Herfindahl index (0-1)
- `tech_vector`: 607-dimensional BLOB (float32 array, one per tech cluster)

### tech_clusters table

607 clusters derived from CPC subclass groupings:
- `cluster_id`: Format `{CPC_prefix}_{index}` (e.g., "H01M_0", "G06N_0")
- `label`: Human-readable label (English + Japanese)
- `patent_count`: Total patents in cluster
- `top_applicants`: JSON array of top filing firms
- `top_terms`: JSON array of characteristic keywords

---

## Tools

| Tool | Purpose | Speed |
|------|---------|-------|
| `startability` | Single firm × cluster score | < 1s |
| `startability_ranking` | Rank clusters for firm or firms for cluster | < 1s |
| `startability_delta` | Score change over time | < 1s |
| `tech_fit` | Detailed phi_tech breakdown | < 1s |
| `firm_tech_vector` | Firm's technology vector and metrics | < 1s |

All use pre-computed `startability_surface` for fast-path lookups.

---

## Usage Examples

### "What technologies can Toyota enter?"
```
startability_ranking(mode="by_firm", query="toyota", year=2024, top_n=10)
```

### "Who is best positioned for battery technology?"
```
startability_ranking(mode="by_tech", query="H01M_0", year=2024, top_n=10)
```

### "How has Sony's AI readiness changed?"
```
startability_delta(mode="by_firm", query="sony", year_from=2020, year_to=2024, direction="gainers")
```

### "Detailed fit analysis: Panasonic × Batteries"
```
startability(firm_query="panasonic", tech_query_or_cluster_id="H01M_0", year=2024)
tech_fit(firm_query="panasonic", tech_query_or_cluster_id="H01M_0", year=2024)
```

---

## Methodology Notes

- Startability is **descriptive**, not predictive. A high score means a firm has the patent
  foundation to enter a technology; it does not guarantee commercial success.
- Scores are relative within each year. Cross-year comparisons use `startability_delta`.
- Firms not in the `startability_surface` table receive a computed score from
  `firm_tech_vectors` (slower but comprehensive).
- The 607 clusters cover all CPC subclasses with sufficient patent density (>100 patents).
