# Patent Space MCP — Data Acquisition

## Data Sources

### Primary: Google Patents Public Data (BigQuery)

All patent data was acquired from Google's BigQuery public dataset
`patents-public-data.patents.publications`.

**Coverage**: 13,677,823 Japanese patents (JP jurisdiction)
**Fields**: title, abstract, CPC codes, applicants/assignees, inventors,
filing dates, publication dates, citation relationships, legal status

**Acquisition pipeline**:
```
BigQuery SQL → Export to Parquet → GCS bucket → Hetzner download → SQLite import
```

**Cost**: ~$20 total (BigQuery scan fees for initial export)

### Entity Data

**TSE Prime/Standard/Growth**: ~1,800 listed companies with EDINET codes, tickers, Japanese/English names
**S&P 500**: US-listed companies with CIK codes and tickers
**Global entities**: Major international firms (Samsung, TSMC, etc.)
**Total resolved entities**: ~4,300 firms

Source: Hand-curated seed files + automated expansion via patent assignee matching.

### GDELT Media Signals

**Source**: GDELT Global Knowledge Graph (BigQuery public dataset)
**Coverage**: ~46 major firms, 2020Q1-2024Q4
**Features**: tone, event_count, theme_diversity, geographic_spread, source_diversity

---

## Database Schema

### Core Tables

| Table | Rows | Description |
|-------|------|-------------|
| patents | 13.7M | Core patent records (title, abstract, dates, status) |
| patent_cpc | 44.8M | Patent-to-CPC code mappings |
| patent_assignees | 30.4M | Patent-to-assignee mappings with firm_id |
| patent_citations | ~200M | Forward/backward citation pairs |
| citation_counts | 13.7M | Pre-computed forward citation counts |

### Pre-computed Tables

| Table | Rows | Description |
|-------|------|-------------|
| firm_tech_vectors | 27.8K | Per-firm-year technology vectors (607-dim BLOB) |
| startability_surface | 10.3M | Pre-computed startability scores (firm × cluster × year) |
| tech_clusters | 607 | Technology cluster definitions (label, top_applicants, top_terms) |
| patent_cluster_mapping | 76K | Patent-to-cluster assignments |
| gdelt_company_features | ~800 | GDELT 5-axis features per firm-quarter |

### FTS5 Index

`patent_search_fts` — Full-text search index on title + abstract (Japanese/English tokenized).

---

## Indexes

Key indexes for query performance:

```sql
-- Core lookups
CREATE INDEX idx_patents_pub ON patents(publication_number);
CREATE INDEX idx_patents_filing ON patents(filing_date);
CREATE INDEX idx_patents_assignee ON patent_assignees(assignee_name);
CREATE INDEX idx_patents_firm ON patent_assignees(firm_id);
CREATE INDEX idx_patents_cpc ON patent_cpc(cpc_code);

-- Citation graph
CREATE INDEX idx_citations_citing ON patent_citations(citing_publication);
CREATE INDEX idx_citations_cited ON patent_citations(cited_publication);

-- Pre-computed lookups
CREATE INDEX idx_ftv_firm_year ON firm_tech_vectors(firm_id, year);
CREATE INDEX idx_ss_cluster_year ON startability_surface(cluster_id, year);
CREATE INDEX idx_ss_firm_year ON startability_surface(firm_id, year);
```

---

## Global Patent Data (Pending)

133M global patents have been exported from BigQuery and downloaded to the server:
- 14,216 Parquet files, ~2.2TB total
- Jurisdictions: US, EP, CN, KR, WO, and more
- Ingestion into SQLite paused at ~34% (4,820/14,216 files)
- Estimated final DB size: 2-3TB
- Resumable via `scripts/ingest_global_patents.py`

---

## Refresh Cadence

| Data | Refresh | Method |
|------|---------|--------|
| JP patents | Quarterly | BigQuery delta export |
| Entity registry | As needed | Seed file updates |
| firm_tech_vectors | Annually | `scripts/compute_firm_tech_vectors.py` |
| startability_surface | Annually | `scripts/compute_startability_surface.py` |
| tech_clusters | Stable | Derived from CPC taxonomy |
| GDELT features | Quarterly | `scripts/extract_gdelt_500.py` |
