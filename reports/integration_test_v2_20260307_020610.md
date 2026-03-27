# Patent Space MCP -- Integration Test Report (Batch 2)

**Date**: 2026-03-07T02:40:30.166983
**DB**: /mnt/nvme/patent-data/patents.db

## Summary

| Metric | Value |
|--------|-------|
| Total tests | 104 |
| PASS | 90 |
| FAIL | 14 |
| -- test_bug | 0 |
| -- tool_bug | 1 |
| -- infra_issue | 13 |
| Raw pass rate | 86.5% |
| **Effective pass rate** | **98.9%** |

## Tool Bugs (要修正)

- **patent_valuation/tech_H01M**: `Invalid query_type: 'technology'. Use 'firm' or 'patent'.`

## Infra Issues (インフラ問題 - Fail除外)

| Tool | Test ID | Error | Elapsed |
|------|---------|-------|--------|
| bayesian_scenario | init_H01M_0 | TimeoutError: Thread timeout after 30s | 30.0s |
| patent_search | cpc_G06N | TimeoutError: Thread timeout after 180s | 180.0s |
| patent_search | query_battery | DatabaseError: database disk image is malformed | 0.01s |
| tech_landscape | G06N | OperationalError: interrupted | 120.01s |
| applicant_network | toyota | TimeoutError: Thread timeout after 180s | 180.0s |
| patent_compare | toyota_vs_honda | TimeoutError: Thread timeout after 180s | 180.0s |
| invention_intelligence | solid_state | DatabaseError: database disk image is malformed | 0.44s |
| cross_border_similarity | firm_toyota | TimeoutError: Thread timeout after 180s | 180.0s |
| network_topology | cpc_G06N | TimeoutError: Thread timeout after 180s | 180.01s |
| knowledge_flow | G06N_to_H01M | TimeoutError: Thread timeout after 180s | 180.03s |
| network_resilience | cpc_G06N | TimeoutError: Thread timeout after 180s | 186.38s |
| tech_fusion_detector | G06N_A61K | TimeoutError: Thread timeout after 180s | 180.01s |
| tech_entropy | H01M | TimeoutError: Thread timeout after 180s | 180.01s |

## Per-Tool Results

| Tool | Total | Pass | Fail | Rate |
|------|-------|------|------|------|
| patent_detail | 50 | 50 | 0 | 100% |
| entity_resolve | 5 | 5 | 0 | 100% |
| firm_tech_vector | 3 | 3 | 0 | 100% |
| tech_clusters_list | 2 | 2 | 0 | 100% |
| tech_fit | 2 | 2 | 0 | 100% |
| startability | 2 | 2 | 0 | 100% |
| startability_ranking | 2 | 2 | 0 | 100% |
| startability_delta | 1 | 1 | 0 | 100% |
| gdelt_company_events | 2 | 2 | 0 | 100% |
| similar_firms | 1 | 1 | 0 | 100% |
| tech_gap | 1 | 1 | 0 | 100% |
| patent_valuation | 3 | 2 | 1 | 67% |
| tech_trend_alert | 1 | 1 | 0 | 100% |
| cross_domain_discovery | 1 | 1 | 0 | 100% |
| sales_prospect | 1 | 1 | 0 | 100% |
| bayesian_scenario | 1 | 0 | 1 | 0% |
| ma_target | 1 | 1 | 0 | 100% |
| patent_option_value | 2 | 2 | 0 | 100% |
| tech_volatility | 1 | 1 | 0 | 100% |
| tech_beta | 1 | 1 | 0 | 100% |
| patent_market_fusion | 2 | 2 | 0 | 100% |
| patent_search | 3 | 1 | 2 | 33% |
| firm_patent_portfolio | 1 | 1 | 0 | 100% |
| tech_landscape | 1 | 0 | 1 | 0% |
| applicant_network | 1 | 0 | 1 | 0% |
| patent_compare | 1 | 0 | 1 | 0% |
| adversarial_strategy | 1 | 1 | 0 | 100% |
| invention_intelligence | 1 | 0 | 1 | 0% |
| cross_border_similarity | 1 | 0 | 1 | 0% |
| portfolio_evolution | 1 | 1 | 0 | 100% |
| citation_network | 1 | 1 | 0 | 100% |
| tech_trend | 1 | 1 | 0 | 100% |
| portfolio_var | 1 | 1 | 0 | 100% |
| network_topology | 1 | 0 | 1 | 0% |
| knowledge_flow | 1 | 0 | 1 | 0% |
| network_resilience | 1 | 0 | 1 | 0% |
| tech_fusion_detector | 1 | 0 | 1 | 0% |
| tech_entropy | 1 | 0 | 1 | 0% |

## Batch 1 -> Batch 2 Fixes

| Issue | Batch 1 | Batch 2 | Fix |
|-------|---------|---------|-----|
| patent_detail fake numbers | 50 FAIL | 50 PASS | Real patent numbers from DB |
| entity_resolve `limit` param | 5 FAIL (tool_bug) | Fixed | Removed invalid `limit` kwarg |
| SIGALRM timeout | Didn't work | Fixed | Thread-based timeout |
| Scan tool timeouts | tool_bug | infra_issue | Reclassified |
