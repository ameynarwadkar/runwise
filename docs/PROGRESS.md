# Runwise: Project State & Continuous Handoff Document

> **FOR NEW AI ASSISTANTS**: Read this entire document before answering. Adhere strictly to the Working Agreement and continue directly from the Immediate Next Steps.

---

## 1. Project Mission & Approved Spec
- **System**: Production-Grade Customer Support Agent & Evaluation Harness (`runwise`).
- **Core Principles**: Deterministic sandboxing, layered graders (Tiers 1–4), strict precedence rules, and statistical consensus metrics ($\text{pass}^k$, $\text{pass}@k$, flip rate).
- **Canonical Design Specification**: `docs/superpowers/specs/2026-10-15-agent-eval-harness-design.md`.

---

## 2. Mandatory Working Agreement for AI Assistant
- **Role**: Senior AI Engineering Mentor (direct, rigorous, intellectually honest, never a "yes-man").
- **Hands-on Pairing Mode**: 
  - **Do NOT modify or write project code directly via tools.**
  - The human engineer creates files, pastes code, runs terminal commands, and makes implementation decisions.
  - The AI assistant provides: Goal, Concept, Files to touch, Exact code with full educational comments, PowerShell verification commands, and Completion criteria.
  - Deliver **only ONE task at a time**.
  - All shell commands must be formatted for **Windows PowerShell**.

---

## 3. Current Architecture & Verification Status (All 105 Tests Passing)
As of `2026-10-17`, the full test suite runs with `uv run pytest tests/ -v` with **105 passed in ~6.5s**.

### Completed Phases & Milestones:
1. **Phase 1: Environment & SQLite Schema (`src/runwise/domain/schema.sql`)**
   - Tables: `users`, `orders`, `order_items`, `refunds`, `audit_log`. Integer cents for currency.
2. **Phase 2: Fixtures & Database Sandboxing (`src/runwise/domain/db.py`)**
   - Ephemeral in-memory SQLite clones seeded from `data/fixtures/base_seed.sql`. Zero cross-trial contamination.
3. **Phase 3: Policy, Domain Models & Tools (`src/runwise/domain/tools.py`)**
   - Support policy (`data/policies/v1.0.md`). 7 domain tools enforcing auth-before-action and audit logging.
4. **Phase 4: Agent Loop & Tool Dispatcher (`src/runwise/agent/loop.py`, `dispatcher.py`)**
   - LiteLLM completion loop with OpenTelemetry tracing and deterministic clock injection.
5. **Phase 5: Evaluation Dataset & Layered Graders**
   - 50-Task Dataset (`evals/tasks.jsonl`): 35 dev / 15 frozen_holdout. Tiers 1–4 graders operational.
6. **Phase 6: Statistical Reliability & Parallel Runner**
   - Parallel runner with ephemeral per-trial sandboxes, computing $\text{pass}^k$, $\text{pass}@k$, and flip rates.
7. **Milestone M0–M5: Benchmark & Generalization Verified**
   - Dev Split: 100.0% pass rate (105/105 trials, $\text{pass}^2 = 100.0\%$).
   - Frozen Holdout: 100.0% pass rate across 45 trials ($\Delta = 0.0\%$). Full report in `docs/BENCHMARK_REPORT.md`.
8. **Subproject 2 Milestone 1: Production Agent Service & Gateway (COMPLETED)**
   - **Service Schemas (`src/runwise/service/schemas.py`)**: Pydantic v2 contracts for requests, responses, health, and tokens.
   - **Isolated Session Management (`src/runwise/service/session.py`)**: Thread-safe sandboxed `SessionContext` lifecycles with TTL expiration and resource cleanup.
   - **Reliability Gateway (`src/runwise/service/gateway.py`)**: Timeouts, exponential retries with jitter on 429/5xx, fail-fast on 400, and automated fallback.
   - **FastAPI Application (`src/runwise/service/app.py`)**: Application factory exposing `/healthz`, `/v1/agent/run`, and `/v1/agent/sessions/{session_id}`.
   - **Live Smoke Test**: Successfully verified against Google Cloud Vertex AI (`vertex_ai/gemini-2.5-flash`), proving multi-turn tool calling, state mutation, and 0% cross-session leakage.
9. **Subproject 2 Milestone 2: Observability, Middleware & Prometheus Metrics (COMPLETED)**
   - **Prometheus Metrics Registry (`src/runwise/service/metrics.py`)**: HTTP RED metrics, agent execution count, latency histogram, prompt/completion tokens, domain tool call counters, gateway retries/fallbacks, and active sessions gauge (`tests/test_metrics.py`).
   - **Observability Middleware (`src/runwise/service/middleware.py`)**: W3C `traceparent` extraction, correlation `X-Request-ID`, path normalization (e.g. `/v1/agent/sessions/{session_id}`), and response headers (`tests/test_middleware.py`).
   - **Distributed Tracing & Context Propagation (`src/runwise/observability/tracer.py`, `src/runwise/agent/loop.py`)**: W3C context inheritance across child spans (`agent_run`, `llm_completion`, `tool_dispatch`) and `http.request_id` attribute linking.
   - **Observability Endpoints (`src/runwise/service/app.py`)**: `GET /metrics` for Prometheus scraping and `GET /readyz` for database/provider readiness verification (`tests/test_service_api.py`).
   - **End-to-End Observability Integration (`tests/test_observability.py`)**: 7 comprehensive tests covering trace propagation, metrics scraping, session lifecycle gauges, and gateway fallback counters.

---
## 4. Subproject 2 Milestone 3: Containerization & Local Infrastructure (COMPLETED)
1. **Production Multi-stage Dockerfile (`Dockerfile`, `.dockerignore`)**: Minimal, secure multi-stage Debian build leveraging Astral `uv` layer caching, non-root user execution, and zero-dependency standard library health probes.
2. **Prometheus Scrape Configuration (`ops/prometheus/prometheus.yml`, `alerts.yml`)**: Automated 5-second metrics scraping of `app:8000/metrics` with 3 production SLO alert rules (`HighHTTPErrorRate`, `HighP95AgentLatency`, `GatewayFailoverActive`).
3. **Grafana Dashboard Provisioning (`ops/grafana/dashboard.json`, `ops/grafana/provisioning/`)**: Declarative datasource and dashboard provisioning exposing an 11-panel RED & Agent operations dashboard.
4. **Local Docker Compose Stack (`docker-compose.yml`)**: Multi-container stack orchestrating FastAPI agent runtime, Prometheus, and Grafana on an isolated bridge network (`runwise-net`), verified healthy with live metrics scraping.

---

## 5. Subproject 2 Milestone 4: CI/CD with an Evaluation Gate (COMPLETED)
1. **Evaluation Gate Engine (`src/runwise/evals/gate.py`, `tests/test_eval_gate.py`)**: Rigorous regression comparator enforcing accuracy drop $\le 2\%$, p95 latency inflation $\le 15\%$, and token cost spikes $\le 15\%$ against a baseline, verified with 7/7 unit tests.
2. **Stratified CI Split & Non-Blocking Runner (`src/runwise/evals/dataset.py`, `runner.py`)**: Added `--split ci` returning a 5-task stratified subset (1 per category), `--output-dir` targeting, and non-blocking exit when `CI=true`.
3. **Committed Baseline Artifact (`data/baseline_eval.json`)**: Version-controlled reference metrics representing the verified 100% pass benchmark from `main`.
4. **GitHub Actions CI/CD Workflow (`.github/workflows/eval-gate.yml`)**: Automated pipeline running unit tests via `uv`, executing the evaluation gate, publishing markdown tables to `$GITHUB_STEP_SUMMARY`, archiving artifacts, and testing container builds.
5. **Regression Drill**: Successfully simulated and verified a degraded candidate that violated both pass rate and latency thresholds, causing the gate to block with exit code 1.

---
## 6. Subproject 2 Milestone 5: Canary Rollout & Automated Rollback (COMPLETED)
1. **Canary Configuration & Dynamic Router (`src/runwise/service/canary.py`, `tests/test_canary.py`)**: Thread-safe dynamic traffic router supporting runtime hot-reloads, weighted routing, and cryptographically deterministic session hashing to prevent mid-session prompt flips (7/7 unit tests passing).
2. **Service Integration & Variant Telemetry (`app.py`, `metrics.py`, `loop.py`)**: Added `X-Runwise-Variant`, `X-Runwise-Prompt-Version`, and `X-Runwise-Model` headers, dedicated Prometheus counters/histograms (`runwise_canary_requests_total`, `runwise_canary_latency_seconds`), and dynamic versioned prompt resolution (`v1.0.yaml` vs `v2.0.yaml`).
3. **Zero-Rebuild Rollback Tooling (`ops/scripts/rollback.py`)**: One-command administrative rollback tool that triggers `/v1/admin/canary/rollback` and persists rollback state to `ops/canary.json` without container rebuilds or server restarts.
4. **Canary Failure & Rollback Drill (`ops/scripts/canary_drill.py`)**: End-to-end operational drill verifying canary activation, multi-turn session pinning, latency SLO breach detection, instant rollback, and 100% recovery to stable across subsequent requests.

---

## 7. Subproject 2 Milestone 6: Load Testing, Cost Modeling & Capacity Planning (COMPLETED)
1. **Token & Cost Modeling Engine (`src/runwise/service/cost.py`, `tests/test_cost_model.py`)**: Exact pricing engine calculating cost per request, cost per 1,000 successful requests ($C / A$), input dominance percentage, and monthly projections at scale (5/5 tests passing).
2. **Prompt Optimization Experiment (`prompts/agent/v1.1_trimmed.yaml`, `ops/scripts/compare_prompts.py`)**: Compressed system prompt by 53.0% characters and 43.1% input tokens, driving a **33.2% total request cost reduction** ($0.0786 to $0.0525 per 1k successes) while preserving 100% policy invariants (4/4 tests passing).
3. **Load Testing Suite (`ops/load/locustfile.py`, `ops/load/run_bench.py`)**: Automated headless Locust concurrency stress test simulating multi-user customer support traffic at increasing RPS with session pinning and zero failures (3/3 tests passing).
4. **Empirical Capacity & Cost Documentation (`docs/CAPACITY_AND_COST.md`)**: Comprehensive load test results, latency percentiles, saturation knee analysis, and sizing matrix.

---

## 8. Subproject 2 Milestone 7: Production Runbook & Blameless Postmortem (COMPLETED)
1. **Operational On-Call Runbook (`RUNBOOK.md`)**: Complete triage guide for all Prometheus alerts (`HighHTTPErrorRate`, `HighP95AgentLatency`, `GatewayFailoverActive`), triage queries, mitigation workflows, and escalation matrix.
2. **Blameless Incident Postmortem (`postmortems/001-canary-latency-slo-breach.md`)**: Production postmortem of the Canary p95 Latency breach incident and instant zero-rebuild rollback drill.
3. **Comprehensive Production README (`README.md`)**: Published complete enterprise documentation with baseline vs production headline numbers, Mermaid architecture diagrams, quickstart instructions, and verification commands.
4. **Full Test Suite Status**: **146 / 146 tests passing (100%)** across 27 modules.

---

## 9. Subproject 3: Cost-Aware Auto-Routing & Multi-Model Tiering (COMPLETED)
1. **Model Pair & Baseline Benchmarking**:
   - Evaluated `vertex_ai/gemini-2.5-flash` ($0.075 / 1M input) vs. `vertex_ai/gemini-2.5-pro` ($1.250 / 1M input — **16.6x price spread**) on Google Cloud Vertex AI across all 35 `dev` tasks (`results/routing/baseline_cheap/` and `baseline_strong/`). Both achieved 100.0% accuracy.
2. **Baseline Comparator & 4-Way Evaluation (`ops/scripts/benchmark_routing_baselines.py`)**:
   - **Baseline 1 (Always Cheap - Flash)**: $0.34 / 1k | 2.85s p50 | 100.0% pass rate (live inference).
   - **Baseline 2 (Always Strong - Pro)**: $8.33 / 1k | 10.33s p50 | 100.0% pass rate (live inference).
   - **Baseline 3 (Rule-Based Router)**: $7.52 / 1k (-9.7% cost) | 10.33s p50 | 100.0% pass rate (trace replay).
   - **Strategy 4 (Adaptive Semantic Router)**: **$3.54 / 1k (-57.5% cost vs Pro, -52.9% vs Rule)** | **3.82s p50 (-63.0% latency)** | **100.0% pass rate** (empirical trace replay over live trajectories). Offloaded 65.7% (23/35) to Flash, reserving Pro for 12/35 adversarial/dispute cases.
3. **Sub-0.1ms Zero-LLM-Overhead Router (`src/runwise/service/auto_router.py`)**:
   - Regex and keyword risk scoring covering adversarial prompt injection, financial liability/chargebacks, and multi-order complexity (5/5 unit tests passing in `tests/unit/test_auto_router.py`).
4. **Service Integration & Observability (`src/runwise/service/app.py`, `metrics.py`)**:
   - Proper model resolution priority: `AutoRouter` $\to$ `Canary Rollout` $\to$ `Default/Gateway Loop`.
   - Prometheus counter `runwise_router_decisions_total{selected_model, risk_tier}` and transparent headers (`X-Runwise-Routed-Model`, `X-Runwise-Complexity-Score`).
   - 3/3 integration tests passing in `tests/integration/test_auto_routing_service.py`.
5. **Docker Compose & Live Verification Drill**:
   - Successfully verified end-to-end multi-container stack (`runwise-agent`, `prometheus`, `grafana`).
   - Live Flash query (`ORD-101`) retrieved verified shipping address from isolated SQLite sandbox.
   - Live Pro query (unauthorized charge dispute) enforced support policy without hallucinating actions.
   - Grafana dashboard provisioned with Donut Chart and Risk Tier Bar Gauge panels.
6. **Formal Benchmark Documentation (`docs/ROUTING_REPORT.md`)**:
   - Comprehensive report with transparent empirical trace-replay methodology labeling and exact reproduction commands.


