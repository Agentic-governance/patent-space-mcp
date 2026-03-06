# Patent Space MCP — Tool Reference

38 tools organized by use case. All tools accept JSON parameters via MCP protocol.

---

## 1. Patent Search & Detail

### `patent_search`
Full-text search across 13.7M JP patents.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| query | string | null | Free-text search (JP/EN). Searches title and abstract via FTS5. |
| cpc_codes | string[] | null | Filter by CPC codes (e.g., `["G06N3"]`) |
| applicant | string | null | Filter by applicant name (partial match) |
| jurisdiction | string | "JP" | Country code |
| date_from | string | null | Start date (YYYY-MM-DD) |
| date_to | string | null | End date (YYYY-MM-DD) |
| max_results | int | 20 | Max results |

### `patent_detail`
Full record for a single patent.

| Parameter | Type | Description |
|-----------|------|-------------|
| publication_number | string | Patent number (e.g., `JP-7637366-B1` for granted, `JP-2020-123456-A` for applications) |
| include_claims | bool | Include claims text (default: false) |
| include_full_text | bool | Include full patent text (default: false) |

### `invention_intelligence`
Prior art search + FTO risk + whitespace analysis from natural language description.

| Parameter | Type | Description |
|-----------|------|-------------|
| text | string | Technology description (JP or EN) |
| max_prior_art | int | Max prior art results (default: 20) |
| include_fto | bool | Include FTO risk assessment (default: true) |
| include_whitespace | bool | Include whitespace opportunities (default: true) |

---

## 2. Firm Analysis

### `firm_patent_portfolio`
Portfolio overview: patent counts, CPC distribution, filing trends, co-applicants.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm | string | Company name (any language) or stock ticker |
| date | string | Cut-off date (default: all time) |
| include_expired | bool | Include expired patents (default: false) |

### `firm_tech_vector`
Pre-computed technology vector and diversity metrics. Fast lookup (~4,300 firms).

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_query | string | Company name or ticker |
| year | int | Analysis year (default: 2024, range: 2015-2024) |

### `entity_resolve`
Resolve company name to canonical form. 3-level matching: exact, normalized, fuzzy.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Company name (any language, ticker, or EDINET code) |
| limit | int | Max results (default: 5) |

### `patent_compare`
Compare multiple firms by patent volume, CPC mix, and trend.

| Parameter | Type | Description |
|-----------|------|-------------|
| firms | string[] | List of company names or tickers |
| cpc_prefix | string | Optional CPC filter |
| date_from / date_to | string | Date range |

### `similar_firms`
Find firms with similar patent portfolios via cosine similarity on tech vectors.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_query | string | Company name or ticker |
| top_n | int | Number of results (default: 10) |
| year | int | Analysis year (default: 2024) |

---

## 3. Technology Landscape

### `tech_landscape`
Filing trends and top applicants for a technology area.

| Parameter | Type | Description |
|-----------|------|-------------|
| cpc_prefix | string | CPC prefix (e.g., "G06N") |
| query | string | Free-text filter |
| date_from / date_to | string | Date range |
| granularity | string | "year" or "quarter" |

### `tech_clusters_list`
Browse 607 technology clusters derived from CPC classification.

| Parameter | Type | Description |
|-----------|------|-------------|
| cpc_filter | string | CPC prefix filter (e.g., "H01", "G06N") |
| sort_by | string | "patent_count" or "cluster_id" |
| top_n | int | Max clusters (default: 200) |

### `tech_trend`
Time-series filing trends with growth rates and new entrants.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Keyword, CPC code, or cluster_id |
| cpc_prefix | string | Optional CPC filter |
| year_from / year_to | int | Year range (default: 2016-2024) |

### `tech_trend_alert`
Auto-detect hot and cooling technology trends.

| Parameter | Type | Description |
|-----------|------|-------------|
| year_from / year_to | int | Year range (default: 2020-2024) |
| min_growth | float | Min growth rate to flag as hot (default: 0.3) |

### `cross_domain_discovery`
Find technology clusters in different CPC sections that share embedding proximity.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | CPC code or free-text technology description |
| top_n | int | Max results (default: 10) |
| exclude_same_domain | bool | Exclude same CPC section (default: true) |

---

## 4. Startability Engine

### `startability`
Compute startability score for a firm-technology pair.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_query | string | Company name or ticker |
| tech_query_or_cluster_id | string | Cluster ID (e.g., "H01M_0") or CPC code |
| year | int | Analysis year (default: 2024, range: 2016-2024) |

### `startability_ranking`
Rank clusters for a firm ("by_firm") or firms for a cluster ("by_tech").

| Parameter | Type | Description |
|-----------|------|-------------|
| mode | string | "by_firm" or "by_tech" |
| query | string | Firm name/ticker (by_firm) or cluster_id (by_tech) |
| year | int | Analysis year (default: 2024) |
| top_n | int | Results to return (default: 20) |

### `startability_delta`
Track startability change over time. Shows gainers and losers.

| Parameter | Type | Description |
|-----------|------|-------------|
| mode | string | "by_firm" or "by_tech" |
| query | string | Firm name/ticker or cluster_id |
| year_from / year_to | int | Year range (default: 2020-2024) |
| direction | string | "gainers", "losers", or "both" |

### `tech_fit`
Compute phi_tech fit components (CPC overlap, citation proximity, co-inventor).

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_query | string | Company name or ticker |
| tech_query_or_cluster_id | string | Cluster ID or CPC code |
| year | int | Analysis year (default: 2024) |

---

## 5. Strategic Analysis

### `adversarial_strategy`
Game-theoretic analysis of two firms' technology territories.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_a | string | First company |
| firm_b | string | Second company |
| year | int | Analysis year (default: 2024) |
| scenario_count | int | Scenarios to generate (default: 3) |

### `tech_gap`
Technology gap and synergy analysis between two firms.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_a | string | First company |
| firm_b | string | Second company |
| year | int | Analysis year (default: 2024) |

### `ma_target`
M&A acquisition target recommendations based on patent analysis.

| Parameter | Type | Description |
|-----------|------|-------------|
| acquirer | string | Acquiring company name or ticker |
| strategy | string | "tech_gap", "consolidation", or "diversification" |
| top_n | int | Number of targets (default: 10) |

### `sales_prospect`
Identify patent licensing sales targets with fit scores and narratives.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_query | string | Licensor company (your firm) |
| patent_or_tech | string | Patent number, tech description, or cluster_id |
| query_type | string | "patent", "text", or "cluster" |

---

## 6. Network Analysis

### `applicant_network`
Co-applicant network for a target company.

| Parameter | Type | Description |
|-----------|------|-------------|
| applicant | string | Company name or ticker |
| depth | int | Traversal depth (default: 1) |
| min_co_patents | int | Min shared patents per edge (default: 5) |

### `citation_network`
Patent citation network (BFS from patent or firm's top patents).

| Parameter | Type | Description |
|-----------|------|-------------|
| publication_number | string | Seed patent (patent mode) |
| firm_query | string | Company name (firm mode) |
| depth | int | BFS depth (1 or 2) |
| direction | string | "forward", "backward", or "both" |
| max_nodes | int | Max network nodes (default: 50) |

### `network_topology`
Scale-free analysis: power law gamma, small-world index, hub patents.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm | string | Company name |
| cpc_prefix | string | CPC prefix for tech area |
| max_patents | int | Max patents (default: 500) |

### `network_resilience`
Percolation theory: simulate hub removal to measure network fragility.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm | string | Company name |
| cpc_prefix | string | CPC prefix |
| attack_mode | string | "targeted" or "random" |

### `knowledge_flow`
Cross-CPC knowledge transfer via citation patterns.

| Parameter | Type | Description |
|-----------|------|-------------|
| source_cpc | string | Knowledge source CPC (e.g., "G06N") |
| target_cpc | string | Knowledge target CPC |
| firm | string | Filter by company |

### `tech_fusion_detector`
Detect technology convergence via co-citation analysis.

| Parameter | Type | Description |
|-----------|------|-------------|
| cpc_a | string | First CPC area |
| cpc_b | string | Second CPC area |
| firm | string | Filter by company |

### `tech_entropy`
Technology maturity via Shannon entropy of applicant diversity.

| Parameter | Type | Description |
|-----------|------|-------------|
| cpc_prefix | string | CPC prefix (e.g., "H01M") |
| query | string | Technology keyword |
| granularity | string | "year" or "quarter" |

---

## 7. Patent Finance

### `patent_option_value`
Black-Scholes real option valuation for patents.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Patent number, company name, or CPC code |
| query_type | string | "patent", "firm", or "technology" |
| S | float | Underlying asset value (auto-estimated if omitted) |
| K | float | Strike price (auto-estimated if omitted) |

### `tech_volatility`
Technology volatility with decay curve and half-life.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | CPC code, keyword, or company name |
| query_type | string | "technology", "text", or "firm" |

### `tech_beta`
CAPM-style technology beta: market sensitivity analysis.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | CPC code or company name |
| benchmark | string | "all" (full market) or "section" (same CPC section) |

### `portfolio_var`
Patent portfolio Value-at-Risk for expiration risk.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm | string | Company name or ticker |
| horizon_years | int | Risk horizon (default: 5) |
| confidence | float | VaR confidence level (default: 0.95) |

### `patent_valuation`
Score patent/portfolio/technology value with royalty rate reference.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Company name, patent number, or CPC code |
| query_type | string | "firm", "patent", or "technology" |
| purpose | string | "licensing", "portfolio_ranking", or "divestiture" |

### `bayesian_scenario`
Bayesian patent investment simulation with data-driven priors.

| Parameter | Type | Description |
|-----------|------|-------------|
| mode | string | "init", "update", or "simulate" |
| technology | string | Cluster ID or tech description (init) |
| firm_query | string | Optional firm context |
| investment_cost | float | Amount in 万円 (default: 10000) |
| session_id | string | Session ID from init (update/simulate) |

---

## 8. Cross-Border

### `cross_border_similarity`
Detect similar patent filings across international jurisdictions.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Firm name, patent number, or tech description |
| query_type | string | "firm", "patent", or "text" |
| target_jurisdictions | string[] | Country codes (default: ["CN","KR","US","EP"]) |
| min_similarity | float | Min CPC overlap threshold (default: 0.7) |

---

## 9. Media Intelligence

### `gdelt_company_events`
GDELT media signals: tone, event count, theme diversity. Pre-cached for ~46 major firms.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_query | string | Company name or ticker |
| date_from | int | Start date YYYYMMDD (e.g., 20200101) |
| date_to | int | End date YYYYMMDD |

### `patent_market_fusion`
Combine patent strength with GDELT market signals for strategic scoring.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Company, CPC code, or patent number |
| query_type | string | "firm", "technology", "text", or "patent" |
| purpose | string | "investment", "ma_target", "license_match", or "general" |

### `portfolio_evolution`
Track firm technology portfolio changes over time.

| Parameter | Type | Description |
|-----------|------|-------------|
| firm_query | string | Company name or ticker |
| year_from / year_to | int | Year range (default: 2016-2024) |

---

## Pagination

All list endpoints support pagination:
- `page` (default: 1) — Page number
- `page_size` (default: 20, max: 100) — Results per page

## Performance Notes

| Category | Response Time | Examples |
|----------|--------------|---------|
| Fast-path (pre-computed) | < 1s | startability, tech_fit, firm_tech_vector, startability_ranking |
| Medium (indexed queries) | 1-10s | patent_search, citation_network, tech_beta |
| Heavy (full-scan) | 10-60s | firm_patent_portfolio, applicant_network, tech_landscape |
| Very heavy (cold cache) | 60-120s | invention_intelligence, knowledge_flow on cold pages |
