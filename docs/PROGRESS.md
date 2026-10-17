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

## 5. Next Project Phase: CI/CD with an Evaluation Gate (Subproject 2, Milestone 4)
1. **Evaluation Gate Engine (`src/runwise/evals/gate.py`, `tests/test_eval_gate.py`)**: Automated regression comparator checking accuracy drop ($\le 2\%$), p95 latency inflation ($\le 15\%$), and token cost spikes ($\le 15\%$) against a baseline.
2. **Deterministic CI Eval Subset (`--split ci`)**: Fast, repeatable stratified evaluation split running without live external API costs during PR checks.
3. **GitHub Actions Workflow (`.github/workflows/eval-gate.yml`)**: Automated PR workflow running unit tests, executing the evaluation gate, rendering markdown comparison tables to `$GITHUB_STEP_SUMMARY`, and gating PR merges.
4. **Baseline Artifact & Regression Verification**: Committed baseline metrics artifact and regression drill proving the gate blocks failing PRs.

