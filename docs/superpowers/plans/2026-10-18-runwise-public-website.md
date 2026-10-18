# Runwise Public Website & Live Playground Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a premier developer-portfolio website with a 30-second recruiter-optimized landing page, an interactive live AI agent playground connected to the real Runwise backend, and verified benchmark replay capability.

**Architecture:** Next.js 15 App Router (TypeScript, Tailwind CSS, Lucide icons) residing in `frontend/`, acting as a secure BFF proxy layer to the existing FastAPI backend. Features clean separation between Scenario Mode (fresh sandbox with deterministic graders) and Conversation Mode (multi-turn), with a fail-closed kill switch and versioned empirical replays.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, Lucide Icons, Python 3.11+, FastAPI, SQLite (in-memory sandboxes), LiteLLM, Google Vertex AI, Pytest.

## Global Constraints
- Design system: Dark charcoal `#101114`, surface `#16181D`, subtle border `#232730`, restrained orange `#F97316`, purple for Pro routing `#A855F7`, emerald for pass `#10B981`.
- Keep frontend strictly isolated in `frontend/`.
- 100% backward compatibility for existing backend clients; all 146 existing tests must continue to pass.
- Never invent benchmark statistics or claim 100% test coverage; strictly distinguish empirical trace replay from live inference.
- Fictional customer verification codes (e.g. 1234) must be clearly labeled as demo-only credentials.
- Cloud deployment and paid resource provisioning are strictly deferred until explicit user authorization in Phase 6.

---

### Task 1: Initialize Next.js 15 Application in `frontend/`

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/app/layout.tsx`

**Interfaces:**
- Produces: Functional Next.js 15 compilation environment with Tailwind CSS and dark mode defaults.

- [ ] **Step 1: Create package.json and install dependencies**
Run in root:
```powershell
npx -y create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --no-turbopack --yes
```
Verify `frontend/package.json` exists.

- [ ] **Step 2: Install lucide-react**
Run in `frontend/`:
```powershell
cd frontend; npm install lucide-react clsx tailwind-merge
```

- [ ] **Step 3: Configure Tailwind theme and global CSS**
Configure `frontend/tailwind.config.ts` with custom brand colors (`charcoal: '#101114'`, `surface: '#16181D'`, `surface-border: '#232730'`, `accent-orange: '#F97316'`, `accent-purple: '#A855F7'`).
Update `frontend/src/app/globals.css` with dark theme styling.

- [ ] **Step 4: Verify build**
Run in `frontend/`:
```powershell
npm run build
```
Expected: Build succeeds.

- [ ] **Step 5: Commit**
```bash
git add frontend/
git commit -m "feat(frontend): initialize next.js 15 app with tailwind and dark design system"
```

---

### Task 2: Shared Types, Constants & Verified Benchmark Data

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/constants.ts`

**Interfaces:**
- Produces: Typed TypeScript schemas for `AgentRunResponse`, `SanitizedToolCall`, `EvaluationSummarySchema`, `ScenarioDefinition`, and `ROUTING_BENCHMARK_DATA`.

- [ ] **Step 1: Write `frontend/src/lib/types.ts`**
Define TypeScript interfaces mirroring the backend Pydantic models:
`AgentRunRequest`, `AgentRunResponse`, `SanitizedToolCall`, `SanitizedTimelineEvent`, `EvaluationSummarySchema`, `GraderDetailSchema`, and `ScenarioDefinition`.

- [ ] **Step 2: Write `frontend/src/lib/constants.ts`**
Populate exact verified metrics and benchmark data from `README.md` and `docs/ROUTING_REPORT.md`:
- Always Cheap: $0.34 / 1k, 2.85s p50 (100% Live Vertex AI)
- Always Strong: $8.33 / 1k, 10.33s p50 (100% Live Vertex AI)
- Rule-Based: $7.52 / 1k, 10.33s p50 (Trace Replay)
- Adaptive Router: $3.54 / 1k (-57.5%), 3.82s p50 (-63.0%) (Trace Replay)
- Pricing cards: Flash ($0.075/1M in, $0.30/1M out), Pro ($1.25/1M in, $5.00/1M out)
- Verified contact links (LinkedIn, GitHub, Email).

- [ ] **Step 3: Run TypeScript compiler check**
Run in `frontend/`:
```powershell
npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/lib/
git commit -m "feat(frontend): add shared contracts, types, and verified benchmark constants"
```

---

### Task 3: Build Recruiter-Optimized Landing Page Components

**Files:**
- Create: `frontend/src/components/landing/Navbar.tsx`
- Create: `frontend/src/components/landing/HeroSection.tsx`
- Create: `frontend/src/components/landing/ArchitectureExplorer.tsx`
- Create: `frontend/src/components/landing/VerifiedMetrics.tsx`
- Create: `frontend/src/components/landing/BenchmarkComparison.tsx`
- Create: `frontend/src/components/landing/ContactSection.tsx`
- Create: `frontend/src/components/landing/Footer.tsx`
- Modify: `frontend/src/app/page.tsx`

**Interfaces:**
- Produces: Complete landing page at `/` communicating value in under 30 seconds with 3-tab architecture explorer, verified metrics, and contact section.

- [ ] **Step 1: Implement `Navbar.tsx`**
Sticky dark navigation bar with logo, orange status pulse, links (`Overview`, `Architecture`, `Live Demo`, `GitHub`, `Contact`), and `Try Live Demo →` primary CTA.

- [ ] **Step 2: Implement `HeroSection.tsx`**
Eyebrow, headline, subhead, direct CTAs (`Launch Live Playground` linking to `/demo` and `GitHub`), plus subtle animated pipeline showing request to evaluation.

- [ ] **Step 3: Implement `ArchitectureExplorer.tsx`**
3 interactive tabs:
- Execution: Request $\to$ AutoRouter $\to$ Agent $\to$ Sandboxed Tools
- Reliability: 50 Tasks $\to$ 4-Tier Deterministic Graders $\to$ CI Regression Gate
- Operations: Gateway Fallback $\to$ OTel Spans $\to$ Prometheus $\to$ Grafana Dashboards

- [ ] **Step 4: Implement `VerifiedMetrics.tsx` & `BenchmarkComparison.tsx`**
Render verified evidence (50 tasks, 146 tests, 3 pillars, -57.5% cost, -63% p50) with explicit trace replay vs. live inference callouts and workload comparability explanations.

- [ ] **Step 5: Implement `ContactSection.tsx` and `Footer.tsx`**
Render contact cards for LinkedIn, GitHub, and Email, plus Apache 2.0 license notice and backend status indicator.

- [ ] **Step 6: Assemble in `frontend/src/app/page.tsx` and verify build**
Run in `frontend/`:
```powershell
npm run build
```
Expected: Build succeeds, generates static `/`.

- [ ] **Step 7: Commit**
```bash
git add frontend/src/
git commit -m "feat(frontend): implement recruiter-optimized landing page and architecture explorer"
```

---

### Task 4: Build Live Playground (`/demo`) & 4-Tab Inspector

**Files:**
- Create: `frontend/src/components/playground/PlaygroundHeader.tsx`
- Create: `frontend/src/components/playground/ScenarioSelector.tsx`
- Create: `frontend/src/components/playground/ChatInterface.tsx`
- Create: `frontend/src/components/playground/ExecutionInspector.tsx`
- Create: `frontend/src/components/playground/ExecutionTimeline.tsx`
- Create: `frontend/src/components/playground/ToolCallsView.tsx`
- Create: `frontend/src/components/playground/EvaluationMatrix.tsx`
- Create: `frontend/src/components/playground/RoutingDiagnostics.tsx`
- Create: `frontend/src/app/demo/page.tsx`
- Create: `frontend/src/lib/replays.ts`

**Interfaces:**
- Produces: Interactive `/demo` playground supporting 5 ground-truth scenarios, multi-turn conversation, offline benchmark replay mode, and 4-tab live telemetry inspector.

- [ ] **Step 1: Implement `ScenarioSelector.tsx` and `PlaygroundHeader.tsx`**
5 scenario cards (Order Lookup, Shipping Address, Refund Eligibility, Multi-Order Dispute, Adversarial Injection) with task IDs and expected behavior. Header includes Reset Session and Replay Mode toggle.

- [ ] **Step 2: Implement `ChatInterface.tsx`**
Multi-turn message bubbles, demo-only credentials disclaimer banner, prompt input with character counter (max 1000 chars), and auto-route toggle.

- [ ] **Step 3: Implement `ExecutionInspector.tsx` with 4 Tabs**
- Tab 1 (`ExecutionTimeline.tsx`): Chronological sanitized events.
- Tab 2 (`ToolCallsView.tsx`): Allowlisted tool call arguments and results.
- Tab 3 (`EvaluationMatrix.tsx`): Deterministic Graders (Task Completion, Policy, Groundedness, Overall). Displays `NOT_EVALUATED` for conversational queries.
- Tab 4 (`RoutingDiagnostics.tsx`): Model badge (Flash vs Pro), complexity meter ($T = 0.45$), regex tags, selection reason.

- [ ] **Step 4: Implement `frontend/src/lib/replays.ts`**
Embed sanitized empirical benchmark traces from `results/routing/` so visitors can click "Inspect Verified Run" even if the backend is offline.

- [ ] **Step 5: Assemble in `frontend/src/app/demo/page.tsx` and verify build**
Run in `frontend/`:
```powershell
npm run build
```
Expected: Build succeeds, generates `/demo`.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/
git commit -m "feat(frontend): implement dual-mode live playground and execution inspector"
```

---

### Task 5: Backend API Contracts, Data Sanitization & Grader Integration (Python)

**Files:**
- Modify: `src/runwise/service/schemas.py`
- Modify: `src/runwise/service/app.py`
- Create: `src/runwise/service/demo.py`
- Create: `tests/integration/test_demo_api.py`

**Interfaces:**
- Produces: Enhanced backend endpoints:
  - `POST /v1/demo/scenarios/run` (server-controlled scenario runner)
  - `GET /v1/demo/scenarios` (canonical scenario catalog)
  - `GET /v1/demo/replays` & `GET /v1/demo/replays/{task_id}` (verified replay traces)
  - Additive backward-compatible fields in `AgentRunResponse` (`tool_calls`, `events`, `evaluation`, `cost_usd`, `is_replay`).

- [ ] **Step 1: Write integration tests in `tests/integration/test_demo_api.py`**
Test that:
- `GET /v1/demo/scenarios` returns the 5 ground-truth scenarios.
- `POST /v1/demo/scenarios/run` with `scenario_id="scenario_order_lookup"` runs agent, routes to Flash, executes `lookup_order`, runs deterministic graders, and returns `overall_status == "PASS"`.
- `POST /v1/demo/scenarios/run` with `scenario_id="scenario_adversarial_injection"` routes to Pro and polite refusal passes policy grader.
- `POST /v1/agent/run` with custom prompt returns `evaluation.overall_status == "NOT_EVALUATED"`.
- All tool calls and timeline events are sanitized with zero `thought_signature` or internal leaks.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/integration/test_demo_api.py -v`
Expected: FAIL (endpoints do not yet exist).

- [ ] **Step 3: Update `src/runwise/service/schemas.py`**
Add `SanitizedToolCall`, `SanitizedTimelineEvent`, `GraderDetailSchema`, `EvaluationSummarySchema`, `ScenarioRunRequest`, and enhance `AgentRunResponse` with default factories preserving 100% backward compatibility.

- [ ] **Step 4: Implement scenario execution & grading in `src/runwise/service/demo.py` and mount in `app.py`**
- Resolve canonical scenario configuration strictly on backend.
- Run `AgentLoop` in isolated `SessionContext`.
- Run `evaluate_trial` on resulting `Trajectory` and SQLite `conn`.
- Serialize allowlisted tool calls and timeline events.
- Mount `POST /v1/demo/scenarios/run`, `GET /v1/demo/scenarios`, and `GET /v1/demo/replays`.

- [ ] **Step 5: Run tests to verify they pass**
Run: `uv run pytest tests/integration/test_demo_api.py -v`
Expected: PASS.

- [ ] **Step 6: Run full test suite to guarantee 0 regressions**
Run: `uv run pytest tests/`
Expected: 146+ tests passing.

- [ ] **Step 7: Commit**
```bash
git add src/runwise/ tests/
git commit -m "feat(api): implement server-controlled scenario runner and deterministic grader integration"
```

---

### Task 6: BFF API Routes & Frontend-Backend Integration

**Files:**
- Create: `frontend/src/app/api/run/route.ts`
- Create: `frontend/src/app/api/scenarios/route.ts`
- Create: `frontend/src/app/api/scenarios/run/route.ts`
- Create: `frontend/src/app/api/replays/route.ts`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: Working Next.js Edge/Node BFF routes proxying to FastAPI backend with client-side IP rate limiting (10 req/min, 50 req/day), 1,000 char prompt limit, and graceful offline fallback.

- [ ] **Step 1: Implement `frontend/src/app/api/scenarios/run/route.ts`**
Validates `scenario_id`, forwards request to FastAPI `POST /v1/demo/scenarios/run`, attaches service auth header, and returns sanitized response. Falls back to static replay if backend is unreachable.

- [ ] **Step 2: Implement `frontend/src/app/api/run/route.ts`**
Enforces 1,000 character limit, rate limits per IP, forwards to FastAPI `POST /v1/agent/run`, and returns response.

- [ ] **Step 3: Test integration between Next.js and FastAPI locally**
Start FastAPI in background, verify Next.js BFF routes communicate cleanly.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/app/api/ frontend/src/lib/api.ts
git commit -m "feat(bff): add next.js api proxy routes with rate limiting and offline fallback"
```

---

### Task 7: Comprehensive Testing, Documentation & Project Verification

**Files:**
- Modify: `README.md`
- Run test suites and builds.

- [ ] **Step 1: Run complete Python test suite**
Run: `uv run pytest tests/ -v`
Expected: 100% tests passing.

- [ ] **Step 2: Run frontend type-check, lint, and build**
Run in `frontend/`:
```powershell
npm run lint; npm run build
```
Expected: 0 errors, successful production build.

- [ ] **Step 3: Update `README.md`**
Document the new public website and live playground architecture, local frontend quickstart (`cd frontend && npm run dev`), deployment guide, and defensibility matrix.

- [ ] **Step 4: Commit**
```bash
git add README.md
git commit -m "docs: update readme with public website and live playground architecture"
```
