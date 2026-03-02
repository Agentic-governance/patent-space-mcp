# Patent Space MCP

A Model Context Protocol (MCP) server providing **26 tools** for patent intelligence — search, portfolio analysis, technology landscape mapping, startability scoring, cross-domain discovery, adversarial strategy, and patent-market fusion.

Built on **13.6M+ patent records** from Google Patents Public Data (BigQuery), with 607 technology clusters, 4,300+ resolved entities (JP TSE + US S&P 500), and pre-computed startability surfaces.

## Demo

### Basic: Ask AI about patents
https://github.com/Rei02061986/patent-space-mcp/raw/main/demo/demo_ja_basic.mp4

### Advanced: Simulate patent wars
https://github.com/Rei02061986/patent-space-mcp/raw/main/demo/demo_ja_strategy.mp4

## Quick Start

### Option 1: Claude Desktop (stdio)

```bash
# Clone and install
git clone https://github.com/Rei02061986/patent-space-mcp.git
cd patent-space-mcp
python -m venv .venv && source .venv/bin/activate
pip install .

# Place your patents.db in data/
# Configure Claude Desktop (see below)
```

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "patent-space": {
      "command": "/path/to/patent-space-mcp/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/path/to/patent-space-mcp",
      "env": {
        "PATENT_DB_PATH": "/path/to/patent-space-mcp/data/patents.db"
      }
    }
  }
}
```

### Option 2: Docker Compose (HTTP)

```bash
# Place patents.db in data/
docker compose up -d

# Server available at http://localhost:8001
```

### Option 3: HTTP server (no Docker)

```bash
python server.py --transport http --host 0.0.0.0 --port 8001
```

### Option 4: Remote / Hosted MCP (HTTP)

If running on a remote server, configure Claude Desktop to connect via HTTP:

```json
{
  "mcpServers": {
    "patent-space": {
      "url": "http://your-server-ip:8001/mcp"
    }
  }
}
```

Verify the server is running:

```bash
curl http://your-server-ip:8001/health
# Expected: {"status": "ok", ...}
```

**Endpoints**:
- `POST /mcp` — MCP protocol endpoint (streamable HTTP transport)
- `GET /health` — Health check (returns tool count, DB status)

## Tools (26)

### Search & Retrieval
| Tool | Description |
|------|-------------|
| `patent_search` | Full-text + multi-CPC + applicant + date search with English fallback |
| `patent_detail` | Single patent full record |
| `entity_resolve` | Company name resolution (any language, ticker, EDINET code) |

### Portfolio & Comparison
| Tool | Description |
|------|-------------|
| `firm_patent_portfolio` | Patent portfolio analysis for a company |
| `patent_compare` | Side-by-side comparison of multiple firms |
| `applicant_network` | Co-applicant graph |
| `firm_tech_vector` | 64-dim technology vector + diversity metrics |

### Technology Landscape
| Tool | Description |
|------|-------------|
| `tech_landscape` | Filing trends, top applicants, growth areas |
| `tech_clusters_list` | Browse 607 technology clusters |
| `tech_fit` | Technology fit components (cosine, distance, CPC Jaccard) |

### Startability
| Tool | Description |
|------|-------------|
| `startability` | S(v,f,t) score for a firm-technology pair |
| `startability_ranking` | Rank firms for a cluster or clusters for a firm |
| `startability_delta` | Track startability changes over time (gainers/losers) |

### Advanced Analysis
| Tool | Description |
|------|-------------|
| `cross_domain_discovery` | Find cross-section technology connections via embedding similarity |
| `adversarial_strategy` | Game-theoretic portfolio comparison with attack/defend/preempt scenarios |
| `invention_intelligence` | Prior art analysis, FTO risk, whitespace opportunities |
| `patent_market_fusion` | Combined tech-strength + GDELT market signal scoring |
| `gdelt_company_events` | GDELT news events and 5-axis features |

## Database

The server uses a single SQLite database (`data/patents.db`) containing:

| Table | Rows | Description |
|-------|------|-------------|
| `patents` | 13.7M | Core patent metadata |
| `patent_cpc` | 22M+ | CPC classification codes |
| `patent_assignees` | 15M+ | Assignee records with firm_id |
| `patent_research_data` | 6.4M+ | 64-dim embeddings (Google Patents Research) |
| `tech_clusters` | 607 | Technology clusters with centroids |
| `patent_cluster_mapping` | 2.4M | Patent-to-cluster assignments |
| `firm_tech_vectors` | 26K+ | Per-firm-per-year technology vectors |
| `startability_surface` | 1.7M | Pre-computed S(v,f,t) scores |
| `tech_cluster_momentum` | 14K+ | Year-over-year cluster growth |
| `patent_legal_status` | 13.7M | Derived legal status |
| `patent_value_index` | 13.7M | Composite patent value score |
| `patent_family` | 13.7M | INPADOC family sizes |
| `gdelt_company_features` | 3K+ | GDELT 5-axis market features |

## Building the Database

If you want to build the database from scratch using Google BigQuery:

```bash
# 1. Set up GCP credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export BIGQUERY_PROJECT=your-project-id

# 2. Ingest JP patent data
pip install ".[bigquery]"
python scripts/ingest_jp_patents.py --db data/patents.db

# 3. Ingest global patent data (US, EP, WO, CN, KR)
python scripts/ingest_global_patents.py --db data/patents.db --country-codes US,EP,WO

# 4. Build upper layers
pip install ".[compute]"
python scripts/compute_firm_tech_vectors.py --db data/patents.db
python scripts/build_tech_clusters.py --db data/patents.db
python scripts/compute_startability_surface.py --db data/patents.db --top-firms 0 --top-clusters 0

# 5. Derive supplementary tables
python scripts/derive_legal_status.py --db data/patents.db
python scripts/compute_family_sizes.py --db data/patents.db
python scripts/compute_patent_value.py --db data/patents.db

# 6. Export paper-ready datasets
python scripts/export_paper_data.py --db data/patents.db --output-dir paper_data/
```

## Entity Resolution

The server resolves company names to canonical entities using 3-level matching:

| Level | Method | Example |
|-------|--------|---------|
| Exact | Alias/ticker/EDINET lookup | "7203" → Toyota Motor Corporation |
| Normalized | Suffix stripping + NFKC | "トヨタ自動車株式会社" → Toyota |
| Fuzzy | Levenshtein ratio > 0.80 | "Toshiba Corp" → Toshiba Corporation |

**Coverage:**
- 2,785 Japanese firms (TSE Prime + Standard + Growth)
- ~100 US S&P 500 companies (top patent filers)
- Stock ticker and EDINET code resolution

## Project Structure

```
patent-space-mcp/
├── server.py                    # MCP server (18 tools)
├── db/
│   ├── sqlite_store.py          # Database access layer
│   └── migrations.py            # Schema definitions (20+ tables)
├── entity/
│   ├── registry.py              # Entity registry
│   ├── resolver.py              # Fuzzy name resolution
│   └── data/                    # Entity seed data
│       ├── tse_prime_seed.py    # TSE Prime (50 major JP firms)
│       ├── tse_expanded_seed.py # TSE Standard/Growth
│       ├── tse_auto_seed.py     # Auto-generated from CSV
│       └── sp500_seed.py        # S&P 500 (100 major US firms)
├── sources/
│   ├── base.py                  # Base source interface
│   ├── bigquery.py              # Google BigQuery connector
│   ├── gdelt_bigquery.py        # GDELT BigQuery connector
│   └── epo_ops.py               # EPO Open Patent Services connector
├── space/
│   ├── startability.py          # S(v,f,t) computation
│   └── embedding_bridge.py      # FTS-to-embedding proxy bridge
├── tools/
│   ├── search.py                # patent_search (multi-CPC, English fallback)
│   ├── portfolio.py             # firm_patent_portfolio
│   ├── landscape.py             # tech_landscape
│   ├── network.py               # applicant_network
│   ├── compare.py               # patent_compare
│   ├── vectors.py               # firm_tech_vector
│   ├── clusters.py              # tech_clusters_list
│   ├── tech_fit.py              # tech_fit
│   ├── startability_tool.py     # startability, startability_ranking
│   ├── startability_delta.py    # startability_delta (time-series)
│   ├── gdelt_tool.py            # gdelt_company_events
│   ├── cross_domain.py          # cross_domain_discovery
│   ├── adversarial.py           # adversarial_strategy
│   ├── invention_intel.py       # invention_intelligence
│   └── market_fusion.py         # patent_market_fusion
├── scripts/                     # Data pipeline scripts
│   ├── ingest_global_patents.py # Multi-jurisdiction patent ingestion
│   ├── export_paper_data.py     # Paper-ready dataset export
│   └── ...                      # Compute and analysis scripts
├── tests/                       # Test suite
├── Dockerfile
├── docker-compose.yml
├── ARCHITECTURE.md              # System architecture documentation
├── ATTRIBUTION.md               # Data source attribution
└── pyproject.toml
```

## Known Limitations

| Area | Limitation | Impact | Planned Fix |
|------|-----------|--------|-------------|
| **Embedding coverage** | ~46.6% of JP patents have embeddings (Google Patents Research covers 2000-2018 JP filings) | JP-2019+ patents lack some embeddings; tech vectors for recent years may be sparse | Global data expansion via `bq extract` (partially complete) |
| **GDELT coverage** | 46 of 50 target firms have market signal data | `patent_market_fusion` falls back to neutral sentiment (0.5) for uncovered firms | Incremental GDELT ingestion |
| **Small portfolios** | 309 firms have 2 or fewer patents | `firm_tech_vector` unreliable for these firms | Filter or flag in results |
| **Citation scope** | `citation_counts` reflect JP-internal citations only | Forward citation counts understate true impact | Global citation graph |
| **Legal status** | Derived heuristically from filing date + 20 years | May not reflect maintenance fee lapses | EPO OPS API integration (connector ready) |

## Requirements

- Python >= 3.11
- SQLite database with patent data
- ~60 GB disk for JP patents database

## License

MIT License

See [ATTRIBUTION.md](ATTRIBUTION.md) for data source licenses.
