# 03 — Cost-Aware Model Auto-Routing

For the complete technical benchmark report, pricing analysis, and trace-replay evaluation methodology, see:
👉 **[ROUTING_REPORT.md](ROUTING_REPORT.md)**

## Quick Summary

- **Implementation**: [`src/runwise/service/auto_router.py`](file:///e:/Coding/production-level-agent/src/runwise/service/auto_router.py)
- **Comparator Script**: [`ops/scripts/benchmark_routing_baselines.py`](file:///e:/Coding/production-level-agent/ops/scripts/benchmark_routing_baselines.py)
- **Model Tiers**: `vertex_ai/gemini-2.5-flash` ($0.075 / 1M) vs `vertex_ai/gemini-2.5-pro` ($1.250 / 1M — 16.6x spread)
- **Key Result (35 Dev Tasks)**:
  - **-57.5% Cost Reduction** vs. Always Pro ($3.54 vs. $8.33 / 1k requests)
  - **-63.0% Latency Reduction** (3.82s vs. 10.33s p50)
  - **100.0% Accuracy** maintained across all 35 tasks
  - **65.7% Traffic Offloaded** to Flash
- **Evaluation Methodology**: Empirical trace replay over live Vertex AI trajectories.
- **Prometheus Telemetry**: `runwise_router_decisions_total{selected_model, risk_tier}`