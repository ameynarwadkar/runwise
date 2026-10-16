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

## 3. Current Architecture & Verification Status (64/64 Tests Passing)
As of `2026-10-16`, the test suite runs with `uv run pytest tests/ -v` with **64 passed in ~5.5s**.

### Completed Phases:
1. **Phase 1: Environment & SQLite Schema (`src/runwise/domain/schema.sql`)**
   - Tables: `users`, `orders`, `order_items`, `refunds`, `audit_log`.
   - Integer cents for currency, SQLite check constraints on statuses and amounts.
2. **Phase 2: Fixtures & Database Sandboxing (`src/runwise/domain/db.py`)**
   - Ephemeral in-memory SQLite clones seeded from `data/fixtures/base_seed.sql`.
   - Zero cross-trial contamination.
3. **Phase 3: Policy, Domain Models & Tools (`src/runwise/domain/tools.py`)**
   - Support policy (`data/policies/v1.0.md`).
   - 7 tools: `lookup_user`, `verify_customer`, `lookup_order`, `lookup_policy`, `update_shipping_address`, `cancel_order`, `issue_refund`.
   - Enforces auth-before-mutation and logs `MUTATION_BLOCKED` to `audit_log`.
4. **Phase 4: Agent Loop & Tool Dispatcher (`src/runwise/agent/loop.py`, `dispatcher.py`)**
   - Prompt `prompts/agent/v1.0.yaml`.
   - LiteLLM completion loop with deterministic `mock_completions` support.
   - Sequenced `Trajectory` recording with deterministic event IDs (`seq`).
5. **Phase 5: Evaluation Dataset & Layered Graders**
   - **50-Task Dataset (`evals/tasks.jsonl`, `src/runwise/evals/dataset.py`)**: 35 dev / 15 frozen_holdout split across 5 categories.
   - **Tier 1 Code Graders (`src/runwise/evals/graders/code.py`)**: `DBStateGrader` (SQL assertions) and `SafetyInvariantAuditor` (`audit_log` checks).
   - **Tier 2 Trajectory Grader (`src/runwise/evals/graders/trajectory.py`)**: `TrajectoryPolicyGrader` checking auth-before-action, blocked mutation penalties, and loop/thrashing detection.
   - **Tier 3 Hallucination Grader (`src/runwise/evals/graders/hallucination.py`)**: `DeterministicHallucinationGrader` catching fabricated actions and ungrounded entities.
   - **Tier 4 Scoped LLM Judge (`src/runwise/evals/graders/judge.py`)**: `ScopedLLMJudge` checking refusal clarity and tone when `requires_judge=True`.
   - **Hierarchical Aggregator (`src/runwise/evals/graders/aggregation.py`)**: Implements Precedence Rule (Deterministic Tiers 1–3 strictly overrule Tier 4).
6. **Phase 6: Statistical Reliability & Parallel Runner**
   - **Stats Engine (`src/runwise/evals/stats.py`)**: Computes $\text{pass}^k$, $\text{pass}@k$, flip rate, and category summaries.
   - **Parallel Runner (`src/runwise/evals/runner.py`)**: Multi-threaded executor with per-trial ephemeral sandboxes, writing `trajectories.jsonl` and `summary.json`.

---

## 4. Immediate Next Tasks to Execute
1. **Live Baseline Evaluation (Milestone M0 Completion)**:
   - Configure `.env` with `GEMINI_API_KEY`.
   - Run the baseline evaluation on a subset or full `dev` split:
     ```powershell
     uv run python -m runwise.evals.runner --split dev --limit 5 --trials 1 --workers 2
     ```
   - Inspect the terminal summary report and `results/runs/<run_id>/summary.json`.
2. **Empirical Noise Floor / Flip Rate (Milestone M1)**:
   - Run the runner twice with identical settings and calculate the flip rate using `stats.compute_flip_rate`.
3. **Observability Integration (Phoenix / OpenTelemetry)**:
   - Wire trace spans into `AgentLoop` using `arize-phoenix-client` to visualize multi-turn tool calling.
