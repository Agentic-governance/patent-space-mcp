# Patent Space MCP

Patent intelligence MCP server with 38 tools covering 13.6M+ Japanese patents, 607 technology clusters, and 4,300+ resolved entities.

## Features

- **13.6M+ Japanese patents** with full metadata, CPC codes, and citation data
- **607 technology clusters** derived from CPC classification
- **4,300+ company entities** with name resolution (Japanese/English/ticker)
- **Startability engine** — measures firm readiness to enter technology areas
- **Patent finance tools** — Black-Scholes option valuation, VaR, CAPM beta
- **Network analysis** — citation topology, knowledge flow, resilience testing
- **GDELT integration** — media sentiment signals for ~46 major firms
- **NVMe-optimized** — fast-path queries return in <1s

## Quick Start

### As Claude Desktop MCP Server

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "patent-space": {
      "url": "https://patent-space.dev/mcp"
    }
  }
}
```

### As Smithery MCP

Available on [Smithery](https://smithery.ai/) as `patent-space-mcp`.

## Tools (38)

### Patent Search & Detail (2)
| Tool | Description |
|------|-------------|
| `patent_search` | Search patents by keyword, CPC code, applicant, or date range |
| `patent_detail` | Get full patent record including CPC codes, assignees, inventors, and citations |

### Company Analysis (5)
| Tool | Description |
|------|-------------|
| `firm_patent_portfolio` | Patent portfolio analysis — counts, CPC distribution, filing trends, co-applicants |
| `patent_compare` | Compare multiple firms by patent volume, CPC mix, and trend |
| `applicant_network` | Build co-applicant network for a target applicant |
| `similar_firms` | Discover firms with similar patent portfolios via cosine similarity |
| `firm_tech_vector` | Get a firm's precomputed technology vector and diversity metadata |

### Startability — Market Entry Analysis (4)
| Tool | Description |
|------|-------------|
| `startability` | Compute startability score for a firm-technology pair |
| `startability_delta` | Compute change in startability scores over time |
| `startability_ranking` | Rank tech clusters or firms using precomputed startability surface |
| `tech_fit` | Compute phi_tech fit components for a firm and technology cluster |

### Technology Analysis (7)
| Tool | Description |
|------|-------------|
| `tech_landscape` | Analyze filing trends and top applicants in a technology area |
| `tech_clusters_list` | List 607 technology clusters with optional CPC filtering |
| `tech_trend` | Analyze time-series technology trends with growth rates and new entrants |
| `tech_trend_alert` | Detect hot and cooling technology trends with market signals |
| `tech_entropy` | Technology maturity via Shannon entropy of applicant diversity |
| `tech_volatility` | Technology volatility analysis with decay curve and half-life |
| `tech_beta` | CAPM-style technology beta: market sensitivity analysis |

### Network Analysis (4)
| Tool | Description |
|------|-------------|
| `citation_network` | Build a patent citation network around a patent or firm's top patents |
| `network_topology` | Citation network topology analysis (scale-free, small-world, clustering) |
| `network_resilience` | Patent network resilience via percolation theory |
| `knowledge_flow` | Cross-CPC knowledge flow analysis via citation patterns |

### Strategy & M&A (4)
| Tool | Description |
|------|-------------|
| `adversarial_strategy` | Game-theoretic analysis of two firms' technology territories |
| `ma_target` | Recommend M&A acquisition targets based on patent portfolio analysis |
| `tech_gap` | Analyze technology gap and synergy between two firms |
| `sales_prospect` | Identify and rank patent licensing sales targets |

### Invention & FTO Analysis (3)
| Tool | Description |
|------|-------------|
| `invention_intelligence` | Analyze technology description for prior art, FTO risk, and whitespace |
| `cross_domain_discovery` | Discover cross-domain technology clusters related to a query |
| `cross_border_similarity` | Detect similar patent filings across international jurisdictions |

### Patent Finance & Valuation (4)
| Tool | Description |
|------|-------------|
| `patent_market_fusion` | Combine patent portfolio strength with market signals |
| `patent_valuation` | Score patent, portfolio, or technology area value with royalty rate reference |
| `patent_option_value` | Black-Scholes real option valuation for patents |
| `portfolio_var` | Portfolio Value-at-Risk for patent expiration risk |

### Technology Fusion & Evolution (3)
| Tool | Description |
|------|-------------|
| `tech_fusion_detector` | Technology fusion detector via co-citation analysis |
| `portfolio_evolution` | Track how a firm's technology portfolio evolved over time |
| `bayesian_scenario` | Bayesian patent investment simulation with data-driven priors |

### Utility (2)
| Tool | Description |
|------|-------------|
| `entity_resolve` | Resolve a company name to its canonical form |
| `gdelt_company_events` | Fetch GDELT events and cached five-axis features for a firm |

## Data Sources

| Source | Coverage | Size |
|--------|----------|------|
| Google Patents Public Data (BigQuery) | 13.6M+ Japanese patents | 310GB+ |
| CPC Classification | 607 technology clusters | Pre-computed |
| GDELT Global Knowledge Graph | Media signals for ~46 major firms (2020-2024) | Cached |
| Entity Registry | TSE Prime/Standard/Growth + S&P500 + Global | 4,300+ firms |

## Architecture

```
┌─────────────────────────────────────────────┐
│              Claude / MCP Client             │
└─────────────┬───────────────────────────────┘
              │ Streamable HTTP (/mcp)
┌─────────────▼───────────────────────────────┐
│           FastMCP 2.14.5 (Python 3.13)       │
│  ┌──────────────────────────────────────┐   │
│  │  38 Tool Functions + Entity Resolver  │   │
│  └──────────────┬───────────────────────┘   │
│  ┌──────────────▼───────────────────────┐   │
│  │  PatentStore (SQLite, WAL mode)       │   │
│  │  - patents: 13.6M rows               │   │
│  │  - patent_cpc: 44.8M rows            │   │
│  │  - startability_surface: 10.2M rows   │   │
│  │  - firm_tech_vectors: 27.8K rows      │   │
│  │  - tech_clusters: 607 rows            │   │
│  └──────────────────────────────────────┘   │
│              Docker (48GB mem limit)          │
│              NVMe SSD (2TB)                   │
└─────────────────────────────────────────────┘
```

## Performance

| Query Type | Response Time | Examples |
|-----------|--------------|---------|
| Pre-computed lookups | 3-40ms | entity_resolve, tech_fit, startability |
| Aggregation queries | 1-30s | tech_landscape, patent_compare |
| Full-text search | 100ms-5s | patent_search |
| Heavy analysis | 10-30s | invention_intelligence, network_topology |

## Self-Hosting

### Requirements
- 64GB+ RAM recommended
- 500GB+ NVMe SSD
- Docker + Docker Compose

### Setup
```bash
git clone https://github.com/Rei02061986/patent-space-mcp.git
cd patent-space-mcp
cp .env.example .env
# Configure PATENT_DB_PATH in .env
docker compose up -d
curl http://localhost:8001/health
```

## License

MIT
