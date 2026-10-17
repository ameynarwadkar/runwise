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

## 3. Current Architecture & Verification Status (All 66 Tests Passing)
As of `2026-10-17`, the full test suite runs with `uv run pytest tests/ -v` with **66 passed in ~12.9s**.

### Completed Phases & Milestones:
1. **Phase 1: Environment & SQLite Schema (`src/runwise/domain/schema.sql`)**
   - Tables: `users`, `orders`, `order_items`, `refunds`, `audit_log`. Integer cents for currency.
2. **Phase 2: Fixtures & Database Sandboxing (`src/runwise/domain/db.py`)**
   - Ephemeral in-memory SQLite clones seeded from `data/fixtures/base_seed.sql`. Zero cross-trial contamination.
3. **Phase 3: Policy, Domain Models & Tools (`src/runwise/domain/tools.py`)**
   - Support policy (`data/policies/v1.0.md`). 7 domain tools enforcing auth-before-action and audit logging.
4. **Phase 4: Agent Loop & Tool Dispatcher (`src/runwise/agent/loop.py`, `dispatcher.py`)**
   - Prompt `prompts/agent/v1.0.yaml`. LiteLLM completion loop with OpenTelemetry tracing and deterministic clock injection.
5. **Phase 5: Evaluation Dataset & Layered Graders**
   - 50-Task Dataset (`evals/tasks.jsonl`): 35 dev / 15 frozen_holdout. Tiers 1–4 graders operational.
6. **Phase 6: Statistical Reliability & Parallel Runner**
   - Parallel runner with ephemeral per-trial sandboxes, computing $\text{pass}^k$, $\text{pass}@k$, and flip rates.
7. **Milestone M0: Live Baseline Evaluation**
   - Evaluated 35 dev tasks across 105 trials: 94.3% baseline pass rate (`run_20261017_140437_142089`).
8. **Milestone M1 & M2: Observability & Trace Sanitization**
   - Integrated Arize Phoenix with OpenInference spans and custom span filtering to eliminate internal polluter spans.
9. **Milestone M3 & M4: Failure Mode Analysis & Prompt Hardening**
   - Eliminated cross-tenant IDOR, negative refunds, premature mutations, and date hallucinations.
   - **Dev Split Pass Rate: 100.0%** (105/105 trials, $\text{pass}^2 = 100.0\%$, `run_20261017_145012_28fee3`).
10. **Milestone M5: Generalization on Frozen Holdout**
   - Evaluated unseen 15 tasks across 45 trials: **100.0% pass rate** (`run_20261017_145501_aab243`).
   - Generalization gap: $\Delta = 0.0\%$. Full retrospective in `docs/BENCHMARK_REPORT.md`.

---

## 4. Next Project Phase: Production Agent Service & LLM Ops (Sub-Project 2)
1. **FastAPI Agent Service (`src/runwise/service/app.py`)**:
   - Asynchronous endpoints (`/v1/chat/completions`, `/v1/agent/run`).
   - Streaming SSE responses and session lifecycle management.
2. **Production Middleware & Health Checks**:
   - Prometheus metrics endpoint (`/metrics`) and health/readiness probes (`/healthz`).
   - Distributed trace correlation (propagating trace IDs from HTTP headers into `agent_run` spans).
3. **Model Auto-Routing & Cost Optimization (Sub-Project 3)**:
   - Benchmark lower-tier models (Gemini Flash Lite, open-weights) to evaluate difficulty trade-offs.
   - Implement query router to cut API spend by 60–80% without sacrificing 100% consensus reliability.
