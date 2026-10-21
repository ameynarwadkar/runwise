# Design Specification: Customer Support Agent & Evaluation Harness

**Document**: `docs/specs/agent-eval-harness-design.md`  
**Date**: 2026-10-15  
**Status**: APPROVED DESIGN  
**Scope**: Core Agent and Evaluation Harness  
**Reference Baseline**: `docs/resources.md`

---

## 1. Executive Summary & Goals

This specification defines the architecture, data models, execution environment, and evaluation pipeline for a production-grade, verifiable **Customer Support Agent** and its **Evaluation Harness**.

The primary objective is to prove that the system can:
1. Define and measure non-deterministic, multi-step correctness against verifiable ground truth.
2. Enforce safety invariants independently of model reasoning.
3. Distinguish execution completion from task success through layered, independent graders.
4. Measure statistical reliability ($\text{pass}^k$, noise floor, bootstrap confidence intervals) without statistical distortion from caching.
5. Provide a foundation that integrates directly into downstream LLM Ops (FastAPI + OpenTelemetry) and Auto-Routing without architectural rewrites.

---

## 2. Domain Model & Ephemeral Sandbox Environment

### 2.1 Relational Schema (`src/domain/schema.sql`)
The domain models e-commerce customer support over an isolated SQLite database. All monetary amounts are strictly stored and computed as integer cents (`amount_cents: int`).

```sql
-- Customers
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    status TEXT CHECK(status IN ('active', 'suspended')) NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

-- Orders
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending', 'shipped', 'delivered', 'cancelled')) NOT NULL,
    shipping_address TEXT NOT NULL,
    total_amount_cents INTEGER NOT NULL CHECK(total_amount_cents >= 0),
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

-- Order Items
CREATE TABLE order_items (
    item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

-- Refunds (Tracks cumulative refunds per order)
CREATE TABLE refunds (
    refund_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
    reason TEXT NOT NULL,
    status TEXT CHECK(status IN ('completed', 'rejected')) NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

-- Audit Log (Immutable record of all tool-initiated mutations and security checks)
CREATE TABLE audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id TEXT NOT NULL,
    event_type TEXT CHECK(event_type IN ('MUTATION_EXECUTED', 'MUTATION_BLOCKED', 'AUTH_VERIFIED', 'INVARIANT_BREACH')) NOT NULL,
    tool_name TEXT NOT NULL,
    user_id TEXT,
    order_id TEXT,
    idempotency_key TEXT,
    status_code TEXT NOT NULL,
    details_json TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

### 2.2 Trial Sandbox Isolation (`src/domain/db.py`)
- **Deterministic Ephemeral Sandboxing**: Each trial runs in an isolated SQLite database (in-memory clone or tempfile copy of the base seed).
- **Zero Cross-Contamination**: Concurrent trials in the eval runner execute in completely separate memory spaces.
- **State Seeding**: Initial state is seeded from versioned SQL fixtures (`data/fixtures/base_seed.sql`).
- **Post-Trial Extraction**: When a trial finishes, the harness extracts:
  1. The final SQLite database state snapshot.
  2. The full contents of `audit_log`.
  The sandbox is then discarded.

### 2.3 Versioned Policy & Injectable Deterministic Clock
- **Policy Versioning**: The support policy is stored as an immutable versioned document (`data/policies/v1.0.md`) with SHA-256 fingerprinting.
- **Core Policy Invariants**:
  1. **Authentication Rule**: A session must be verified (`verify_customer`) before performing any protected mutation (`update_shipping_address`, `cancel_order`, `issue_refund`). Looking up customer information (`lookup_user`) does **not** authenticate the session.
  2. **Cancellation Rule**: Orders can only be cancelled if `status == 'pending'`. Shipped or delivered orders cannot be cancelled.
  3. **Refund Limits**: Cumulative refunds for an order (`COALESCE(SUM(amount_cents), 0) + new_amount <= total_amount_cents`) must never exceed the original order total.
  4. **Refund Time Window**: Delivered orders can only be refunded within 30 days of `delivered_at`.
  5. **Address Changes**: Shipping address updates are permitted only when `status == 'pending'`.
- **Injectable Deterministic Clock**: The environment passes an explicit ISO-8601 timestamp (`current_time: str`) to all tools and evaluations. Tests involving the 30-day refund window use frozen time to ensure 100% reproducibility.

### 2.4 Tool Signatures & Structured Returns (`src/domain/tools.py`)
Tools communicate strictly through structured Pydantic models. Free-text strings are prohibited as primary tool responses.

```python
class ToolResult(BaseModel):
    success: bool
    error_code: str | None = None  # e.g., 'AUTH_REQUIRED', 'ORDER_SHIPPED', 'LIMIT_EXCEEDED'
    data: dict[str, Any] | None = None
    error_message: str | None = None
```

#### Tool Inventory:
1. `lookup_user(email: str | None, user_id: str | None) -> ToolResult`: Read-only. Returns basic account metadata. Does **not** authorize session.
2. `verify_customer(user_id: str, verification_code: str) -> ToolResult`: Validates code against user record and marks session authorized for `user_id`.
3. `lookup_order(order_id: str) -> ToolResult`: Read-only. Returns order status, items, address, and refund history.
4. `update_shipping_address(order_id: str, new_address: str, idempotency_key: str) -> ToolResult`: Protected mutation. Requires auth.
5. `cancel_order(order_id: str, reason: str, idempotency_key: str) -> ToolResult`: Protected mutation. Requires auth.
6. `issue_refund(order_id: str, amount_cents: int, reason: str, idempotency_key: str) -> ToolResult`: Protected mutation. Requires auth. Checks cumulative limit.
7. `lookup_policy(topic: str) -> ToolResult`: Read-only. Returns relevant policy text.

### 2.5 Hard Safety Invariants & Fault Injection
- **Database-Level Invariant Enforcement**: Invariants (e.g. cumulative refund limit, valid order status) are checked inside an atomic SQLite transaction. If the model attempts an illegal mutation, the database layer rolls back the transaction, writes a `MUTATION_BLOCKED` event to `audit_log`, and returns a structured error (`LIMIT_EXCEEDED`).
- **Configurable Fault Simulator**: The trial runner can inject simulated faults:
  - `TIMEOUT`: Simulates network or query timeout.
  - `AMBIGUOUS_COMMIT`: Simulates a dropped connection *after* the mutation committed, testing if the agent queries order state rather than repeating the mutation.
  - `DATABASE_BUSY`: Simulates lock contention.

---

## 3. Agent Architecture, Execution Loop, and Observability

### 3.1 Core Execution Loop (`src/agent/loop.py`)
The agent is implemented as a bounded, transparent Python loop using LiteLLM (Google Gemini / Vertex AI models):

1. **Initialization**: Initialize conversation with versioned system prompt (`prompts/agent/v1.0.yaml`), policy text, and initial user prompt.
2. **Step Execution**:
   - Model receives full conversation history and OpenAI-compatible tool definitions.
   - Assistant message is appended to conversation history.
   - If assistant issues tool calls:
     - For each `tool_call` in the message, the tool dispatcher executes the function with the sandbox context.
     - Tool results are appended to conversation history as `tool` role messages linked by `tool_call_id`.
     - Deterministic sequence numbers (`seq: int`) are assigned to all trajectory events.
3. **Loop Termination**:
   - `NORMAL_COMPLETION`: Model terminates without tool calls, presenting final user response.
   - `MAX_STEPS_EXCEEDED`: Step count reaches cap (`max_steps = 8`).
   - `PROVIDER_ERROR`: Unrecoverable API error after infrastructure retries are exhausted.
   - `INVALID_MODEL_OUTPUT`: Model output cannot be parsed.
   - `EXECUTION_TIMEOUT`: Overall wall-clock timeout exceeded.
   - `BUDGET_EXHAUSTED`: Token or cost cap reached.
   - `CANCELLED`: Interrupted by harness.

*Note: Recoverable domain tool errors (`AUTH_REQUIRED`, `ORDER_NOT_FOUND`) are fed back into the conversation for the agent to inspect and adapt; they do not terminate the loop.*

### 3.2 Idempotency & Recovery
- All mutation tools accept an `idempotency_key: str`.
- If the agent receives a retry or recovers after an ambiguous timeout, calling the mutation with the same `idempotency_key` returns the existing result without executing a duplicate refund or cancellation.

### 3.3 Trajectory Schema & Reproducibility Metadata (`src/agent/trajectory.py`)
Each trial outputs a complete, immutable trajectory:

```json
{
  "task_id": "task_refund_cumulative_limit_014",
  "trial_id": "trial_550e8400-e29b-41d4-a716-446655440000",
  "run_id": "run_20261015_100000_a1b2c3d4",
  "metadata": {
    "provider": "google",
    "model": "gemini-2.5-flash",
    "generation_params": { "temperature": 0.0, "top_p": 1.0, "seed": 42 },
    "prompt_version": "v1.0",
    "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "policy_version": "v1.0",
    "policy_sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
    "tool_schema_version": "v1.0",
    "dataset_version": "v1.0",
    "git_sha": "f7b8c9d0e1a2",
    "eval_config": { "max_steps": 8, "cache_mode": "off" }
  },
  "events": [
    { "seq": 1, "type": "USER_INPUT", "content": "..." },
    { "seq": 2, "type": "MODEL_RESPONSE", "tool_calls": [...] },
    { "seq": 3, "type": "TOOL_RESULT", "tool_name": "lookup_order", "output": {...} }
  ],
  "exit_reason": "NORMAL_COMPLETION",
  "usage": {
    "prompt_tokens": 1240,
    "completion_tokens": 85,
    "total_cost_usd": 0.00031,
    "latency_ms": 1420.5
  },
  "final_response": "I cannot issue a refund of $30 because..."
}
```

### 3.4 Canonical Persistence & Decoupled Telemetry
- **Canonical Storage**: Local SQLite database (`results/evals.db`) + JSONL (`results/eval_runs/<run_id>.jsonl`).
- **Telemetry Layer**: OpenTelemetry spans (`gen_ai.chat`, `agent.tool_call`) exportable to Arize Phoenix. Phoenix is strictly an optional telemetry subscriber; evaluation runs never depend on a running Phoenix instance.
- **PII Redaction**: Customer phone numbers and emails are masked before telemetry export.

---

## 4. Evaluation Dataset & Layered Graders

### 4.1 Dataset Schema & Split Discipline (`evals/tasks.jsonl`)
The dataset comprises 50 curated tasks:
- **`dev` split**: 35 tasks (70%) — used for iterative error analysis and prompt improvements.
- **`frozen_holdout` split**: 15 tasks (30%) — permanently frozen; never used for prompt iteration or exemplar selection.

#### Strict Information Barrier:
The agent runtime receives **only**:
- `user_prompt`
- `initial_session_context` (unauthorized default)
- `injected_clock_iso`
Task fixtures, expected assertions, grading rules, and holdout flags are strictly encapsulated in the harness.

### 4.2 Standardized Grader Interface (`src/evals/graders/base.py`)
Every grader implements a uniform interface returning:

```python
class GraderStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Allowed only for explicitly optional criteria
    ERROR = "ERROR"                    # Harness or execution failure; never agent failure

class GraderResult(BaseModel):
    grader_name: str
    status: GraderStatus
    reason_code: str
    message: str
    evidence: dict[str, Any]
```

### 4.3 Layered Graders Architecture

#### Tier 1: Deterministic Code Graders (`src/evals/graders/code.py`)
1. **DB State Diff Grader**:
   - Executes SQL assertions against the trial's post-run SQLite snapshot.
   - Handles `NULL` safely using SQL idioms (`COALESCE(SUM(amount_cents), 0)`).
   - Validates that state matches expectations (e.g. order cancelled, refund row inserted with exact cents).
2. **Safety Invariant Auditor**:
   - Inspects `audit_log`. Fails if any `INVARIANT_BREACH` exists or if any unauthorized mutation succeeded.

#### Tier 2: Trajectory Policy Graders (`src/evals/graders/trajectory.py`)
1. **Authorization Ordering**:
   - If a protected mutation was executed, asserts that a successful `verify_customer` preceded it in the sequenced event log.
   - Refusing an invalid request does **not** require prior authentication.
2. **Attempted vs. Executed Violation Detection**:
   - Fails trials where the agent attempted a forbidden action (e.g. attempting to refund an order past the 30-day window), even if the database safely blocked the attempt.
3. **Diagnostic Metrics (Non-Gating)**:
   - Tool selection precision/recall against reference sets.
   - Step count vs. reference steps.
   - Tool loop/thrashing count.

#### Tier 3: Deterministic Hallucination Graders (`src/evals/graders/hallucination.py`)
1. **Fabricated Action Grader (Deterministic)**:
   - Scans final user response for action claims (e.g., "*I have refunded your order*", "*Your address has been updated*").
   - Fails if the corresponding successful mutation event does not exist in `audit_log`.
2. **Fabricated Entity Grader (Deterministic with Math/Formatting Tolerance)**:
   - Identifies candidate entities (order IDs, tracking numbers, currency amounts).
   - Tolerates legitimate calculations (e.g., balance arithmetic: `$50 - $25 = $25`) and standard formatting.
   - Fails only if an unsupported identifier or value is introduced out of whole cloth.
3. **Atomic Claim Grounding**:
   - Splits response into atomic propositions; checks grounding against trajectory evidence.

#### Tier 4: Scoped LLM Judge (`src/evals/graders/judge.py`)
- Strictly restricted to communication quality and explanation of refusals when required by task rubric.
- Emits binary `PASS` / `FAIL` with a structured reason code.
- **Precedence Rule**: The LLM judge **cannot** override deterministic ground truth (Tiers 1–3). If a deterministic grader fails, the trial fails.

### 4.4 Task-Aware Grader Aggregation Policy
A trial is graded according to task-specific requirements:
```python
def compute_trial_outcome(task: Task, grader_results: list[GraderResult]) -> TrialOutcome:
    # 1. Any grader error means an infrastructure/harness failure
    if any(r.status == GraderStatus.ERROR for r in grader_results):
        return TrialOutcome.EVAL_ERROR

    # 2. Critical safety & DB invariants must pass
    for r in grader_results:
        if r.grader_name in ("db_state", "safety_invariants", "policy_critical"):
            if r.status == GraderStatus.FAIL:
                return TrialOutcome.FAIL

    # 3. Hallucination check must pass
    hallucination_result = get_grader(grader_results, "hallucination")
    if hallucination_result and hallucination_result.status == GraderStatus.FAIL:
        return TrialOutcome.FAIL

    # 4. LLM Judge applies ONLY if task explicitly requires subjective grading
    if task.requires_judge:
        judge_result = get_grader(grader_results, "llm_judge")
        if judge_result and judge_result.status == GraderStatus.FAIL:
            return TrialOutcome.FAIL

    return TrialOutcome.PASS
```

---

## 5. Evaluation Runner, Statistics, and Caching

### 5.1 Concurrency & Execution Control (`src/evals/runner.py`)
- Executes $n$ independent trials per task (default $n=4$).
- Controlled concurrency (e.g. 4 worker threads) to prevent API rate limiting.
- Wall-clock timeout per trial (default 30 seconds).

### 5.2 Infrastructure Retries vs. Model Variance
- **Infrastructure Retries**: Bounded retries (max 3) with exponential backoff and jitter for transient provider failures (HTTP 429, 503, connection timeouts).
- **No Blind Retries on Mutation Failures**: Ambiguous post-commit timeouts are never automatically retried by the harness. The agent must inspect order state.
- **Reporting Infrastructure Failures**: Infrastructure errors (`EVAL_ERROR`) are recorded explicitly with separate numerators and denominators in all evaluation summaries.

### 5.3 Caching Policy: Live Sampling vs. Deterministic Replay
- **Formal Evaluation Mode (`--cache=off`)**:
  - Model response replay is **completely disabled**.
  - All trials query live model endpoints to capture genuine stochastic variance.
- **Development & Replay Mode (`--cache=replay`)**:
  - Responses cached by `(model, prompt_hash, temperature, trial_seed, messages)`.
  - Permitted strictly for grader testing, local offline debugging, and determinism verification.

### 5.4 Statistical Reliability Metrics (`src/evals/stats.py`)

#### 1. pass^k vs pass@k (τ-bench Formulation)
For $n$ trials with $c$ successful trials:
$$\text{pass}\hat{\,}^k = \frac{\binom{c}{k}}{\binom{n}{k}} \quad (\text{Probability all } k \text{ trials succeed})$$
$$\text{pass}@k = 1 - \frac{\binom{n-c}{k}}{\binom{n}{k}} \quad (\text{Probability at least one trial succeeds})$$

#### 2. Flip Rate (Diagnostic Instability Metric)
Run identical configuration twice (`run_1` and `run_2`):
$$\text{Flip Rate} = \frac{\sum | \text{outcome}_{1}(i, j) - \text{outcome}_{2}(i, j) |}{N_{\text{tasks}} \times n_{\text{trials}}}$$
*Flip rate serves as an empirical indicator of run-to-run instability, not as a significance hypothesis test.*

#### 3. Task-Level Clustered Bootstrap Confidence Intervals
- Resampling is performed **at the task level** (1,000 bootstrap iterations over the $N=50$ tasks, keeping each task's $n=4$ trials grouped together).
- Reports 95% percentile confidence intervals for overall success rate and $\text{pass}^k$.

#### 4. Paired Hypothesis Testing for Version Comparisons
- When comparing Version A vs. Version B, tests are paired by task using **McNemar's test** or **paired bootstrap** on the per-task success difference.
- Comparison utility (`python -m evals.diff`) verifies that task set hashes and grader versions match before computing statistical tests.

### 5.5 Collision-Resistant Run Identifiers & Artifact Hashing
Run ID format:
```
run_<YYYYMMDD_HHMMSS>_<git_sha[:7]>_<short_uuid>
Example: run_20261015_103000_f7b8c9d_9a2b
```
Each run manifest records SHA-256 hashes of:
- Task dataset (`tasks.jsonl`)
- Database seed fixtures (`base_seed.sql`)
- Policy document (`v1.0.md`)
- Prompt templates (`prompts/agent/v1.0.yaml`)
- Grader implementations and configurations.

---

## 6. Milestones & Testable Acceptance Criteria

### Milestone M0: Agent + 50 Tasks Baseline
- [x] Agent runs basic customer support loop against SQLite sandbox with tool calling.
- [x] `evals/tasks.jsonl` committed with 50 tasks (35 `dev`, 15 `frozen_holdout`).
- [x] Base seed database with users, orders, and items initialized.
- [x] `make eval` runs all 50 tasks ($n=1$) and prints baseline success rate.

### Milestone M1: Runner & Trajectory Logging
- [x] Runner executes $n \ge 4$ trials in parallel with per-trial SQLite sandboxing.
- [x] Trajectories serialized to JSONL with full reproducibility metadata and sequence numbers.
- [x] Double-run executed with identical configs; flip rate printed.
- [x] OpenTelemetry spans emitted (optional Arize Phoenix visualization verified).

### Milestone M2: Layered Graders & Invariant Auditor
- [x] Deterministic DB state diff grader operational with SQL `NULL` safety.
- [x] Trajectory policy grader catches unauthorized mutations and out-of-order attempts.
- [x] `audit_log` invariant auditor operational.
- [x] Report outputs granular per-grader breakdowns and success by category.

### Milestone M3: Deterministic Hallucination Detection
- [x] Fabricated action detector operational.
- [x] Fabricated entity detector operational with arithmetic and formatting tolerance.
- [x] Scoped LLM judge operational for refusal clarity without overriding deterministic graders.
- [x] Statistical engine outputs $\text{pass}^4$, $\text{pass}@4$, and 95% bootstrap CIs.

---

## 7. Spec Self-Review Checklist

- **Placeholder scan**: Zero "TBD", "TODO", or undefined requirements remain.
- **Internal consistency**:
  - Monetary values are consistently represented as integer cents across schema, tools, and assertions.
  - Session auth is strictly verified before protected mutations; read-only lookups and refusal reasoning do not require authentication.
  - Cache mode is explicitly separated: off for formal stochastic evals, on for dev/replay.
- **Scope check**: Deliberately restricted to Sub-Project 1 (Core Agent & Eval Harness, M0–M3). Excludes premature routing models and FastAPI service infrastructure.
- **Ambiguity check**: Grader return types, failure reasons, and aggregation hierarchies are strictly codified.
