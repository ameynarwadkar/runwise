# Runwise Production Service On-Call Runbook

**Service**: `runwise` Production Agent Service  
**Target Availability SLO**: $\ge 99.0\%$ availability over 7 days  
**Target Latency SLO**: p95 latency $\le 4.0\text{s}$ under standard traffic  
**Escalation Lead**: Primary On-Call Engineer  

---

## 1. Quick Triage & Diagnostic Dashboard

When paged, run these commands first to assess cluster and service health:

### 1.1 Health & Readiness Probes
```powershell
# Liveness probe (checks if process is running and responding)
curl.exe -i http://127.0.0.1:8000/healthz

# Readiness probe (verifies SQLite sandboxing and provider credentials)
curl.exe -i http://127.0.0.1:8000/readyz
```

### 1.2 Telemetry Endpoints
- **Grafana Live Dashboards**: [http://localhost:3000](http://localhost:3000) (Default admin: `admin` / `admin`)
- **Prometheus Query Console**: [http://localhost:9090](http://localhost:9090)
- **Phoenix OTel Distributed Traces**: [http://localhost:6006](http://localhost:6006)
- **Raw Prometheus Metrics**: `curl.exe http://127.0.0.1:8000/metrics`

### 1.3 Active Canary & Routing State
```powershell
# Check active canary status and routing distribution
curl.exe http://127.0.0.1:8000/v1/admin/canary/status
```

---

## 2. Alert Dictionary & Mitigation Workflows

Every alert defined in `ops/prometheus/alerts.yml` is detailed below.

---

### Alert: `HighHTTPErrorRate`
- **Severity**: `CRITICAL`
- **Condition**: Over 5% of incoming HTTP requests returned 5xx status codes over the last 1 minute:
  ```promql
  (sum(rate(runwise_http_requests_total{status_code=~"5.."}[1m])) or vector(0)) / (sum(rate(runwise_http_requests_total[1m])) > 0) > 0.05
  ```
- **User Impact**: Customer requests are dropping or failing outright; service availability SLO is actively burning error budget.

#### What to Check First:
1. Run `curl.exe http://127.0.0.1:8000/readyz`. If `status != ready`, look at `detail` to see if SQLite DB creation or LLM configuration failed.
2. Inspect the Uvicorn terminal or container logs for unhandled Python exceptions:
   ```powershell
   docker compose logs -n 50 app
   ```
3. Check if Google Cloud ADC / Vertex AI credentials expired or quota is exhausted:
   ```promql
   sum by (error_type) (rate(runwise_gateway_errors_total[2m]))
   ```

#### Mitigation:
1. **Upstream Quota Exhaustion (429 / 503)**:
   - Check if `GatewayFailoverActive` is firing. If the primary model quota is saturated, force the Gateway to fail over to the secondary route by setting `PRIMARY_MODEL=secondary` in `.env` and reloading.
2. **Database or Memory Corruption**:
   - If SQLite memory allocation is locked, clear stale sessions via admin or restart the container:
     ```powershell
     docker compose restart app
     ```
3. **Bad Release**:
   - If this error spiked immediately following a deployment, roll back to the previous container image tag.

---

### Alert: `HighP95AgentLatency`
- **Severity**: `WARNING`
- **Condition**: 95th percentile agent reasoning duration exceeds 4.0 seconds for 2 minutes:
  ```promql
  histogram_quantile(0.95, sum(rate(runwise_agent_run_duration_seconds_bucket[5m])) by (le)) > 4.0
  ```
- **User Impact**: Customer chat experiences perceptible lag or timeouts (> 4 seconds per turn).

#### What to Check First:
1. **Is the latency spike isolated to the Canary variant?**
   Query Prometheus:
   ```promql
   histogram_quantile(0.95, sum(rate(runwise_canary_latency_seconds_bucket[5m])) by (le, variant))
   ```
   If `variant="canary"` is elevated while `variant="stable"` is normal, the candidate prompt/model is regressing.
2. **Check for Tool-Calling Infinite Loops**:
   Inspect average steps per request:
   ```promql
   sum(rate(runwise_agent_tool_calls_total[5m])) / sum(rate(runwise_agent_runs_total[5m]))
   ```
   If average tool calls exceed 3.0 per run, the prompt may be failing to reach consensus or stalling on a tool.
3. **Check Upstream Provider Status**:
   Verify Vertex AI or LLM provider latency in Phoenix traces ([http://localhost:6006](http://localhost:6006)).

#### Mitigation:
1. **If Canary is Causing the Breach**: Execute instant one-command rollback:
   ```powershell
   uv run python ops/scripts/rollback.py --reason "High p95 latency breach detected on canary variant"
   ```
   *This takes effect immediately with zero container rebuilds or downtime.*
2. **If Upstream LLM Provider is Slow**:
   - Verify `max_steps` cap in `src/runwise/agent/loop.py` is enforced (default: 10).
   - If provider latency continues to exceed SLO, switch primary traffic to secondary provider via `ops/canary.json`.

---

### Alert: `GatewayFailoverActive`
- **Severity**: `WARNING`
- **Condition**: Model Gateway has initiated automated failover from primary model to secondary fallback route:
  ```promql
  sum(rate(runwise_gateway_fallbacks_total[2m])) > 0
  ```
- **User Impact**: Requests are still succeeding, but incurring secondary provider costs or alternative latency profiles.

#### What to Check First:
1. Check the Grafana "Gateway Fallbacks" graph to identify the failing route and root cause:
   ```promql
   sum by (primary_model, secondary_model) (rate(runwise_gateway_fallbacks_total[5m]))
   ```
2. Verify why the primary route failed:
   - Upstream rate limit (HTTP 429)
   - Connection timeout (> 15s)
   - Invalid API token or authentication rejection (HTTP 401/403)

#### Mitigation:
1. Check Google Cloud Console / Vertex AI quotas for `gemini-2.5-flash`.
2. Model Gateway will automatically restore traffic to the primary model once successful health probes resume.
3. If primary provider is experiencing an extended regional outage, update `ops/canary.json` or `.env` to make the secondary provider default.

---

## 3. Emergency Procedures

### 3.1 Instant Zero-Rebuild Canary Rollback
If a canary deployment exhibits unexpected hallucinations, elevated error rates, or latency breaches:

```powershell
# 1. Trigger automated rollback tool
uv run python ops/scripts/rollback.py --reason "Emergency rollback triggered by on-call engineer"

# 2. Confirm rollback status
curl.exe http://127.0.0.1:8000/v1/admin/canary/status
# Expected output: {"enabled": false, "weight": 0.0, "status": "rolled_back"}

# 3. Verify subsequent traffic routes 100% to stable
curl.exe -i -X POST http://127.0.0.1:8000/v1/agent/run -H "Content-Type: application/json" -d "{\"prompt\":\"Status of ORD-101?\"}"
# Response header MUST include: X-Runwise-Variant: stable
```

### 3.2 Service Hard Reset (Docker Compose)
If the local infrastructure stack needs a complete state refresh:

```powershell
# Stop and remove containers, preserving volumes
docker compose down

# Restart the full stack in background
docker compose up -d

# Verify all services report healthy
docker compose ps
```

### 3.3 CI/CD Evaluation Gate Emergency Override
If an emergency hotfix PR is blocked by the CI evaluation gate:
1. **Never bypass tests without authorization.**
2. If verified as a false positive caused by upstream mock drift, inspect the Step Summary markdown in GitHub Actions.
3. Re-run baseline comparison locally:
   ```powershell
   uv run python -m runwise.evals.gate --candidate results/eval_candidate/summary.json --baseline data/baseline_eval.json
   ```

---

## 4. Contact & Escalation Matrix

| Role | Contact | Responsibilities |
| :--- | :--- | :--- |
| **Primary On-Call** | Slack `#runwise-ops` / PagerDuty | First response (< 15m), triage, rollback |
| **Secondary On-Call** | Slack `#runwise-leads` | Escalations, provider quota overrides |
| **LLM Platform Lead** | `@llm-core` | Model evaluations, prompt updates, gate policies |
| **Cloud SRE** | `@cloud-infra` | Google Cloud Vertex AI quotas, VPC peering, Docker host |