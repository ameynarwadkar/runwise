# Incident Postmortem: 001 — Canary Latency SLO Breach & One-Command Rollback

**Incident Identifier**: INC-20261017-001  
**Date**: October 17, 2026  
**Status**: Resolved  
**Severity**: P2 (SLO Latency Breach / Canary Degradation)  
**Authors**: Senior AI Systems Engineer & On-Call Engineering Team  

---

## 1. Executive Summary

During a staged deployment of agent prompt version `v2.0` routed at 50% traffic weight, the canary variant's 95th percentile latency spiked to **3,420 ms**, breaching our production SLO ceiling of **3,000 ms** (+420 ms / +14.0% regression).

The automated canary telemetry stream isolated the latency anomaly to the canary variant within 5 seconds of traffic initiation. The on-call engineer triggered an administrative one-command zero-rebuild rollback via `ops/scripts/rollback.py`. Within 180 ms, canary traffic was dropped to 0.0%, routing 100% of subsequent customer sessions back to the stable baseline (`v1.0`). Zero customer requests failed, and p95 latency recovered to 1,450 ms with zero container restarts or downtime.

---

## 2. Impact Assessment

| Metric | Measured Impact |
| :--- | :--- |
| **Availability Impact** | 0 dropped requests (100% availability maintained). |
| **Latency SLO Impact** | Canary p95 reached **3,420 ms** (SLO limit: 3,000 ms; Stable baseline: 1,450 ms). |
| **Affected Sessions** | 50% of concurrent customer sessions during the 12-request verification window. |
| **Time to Detect (TTD)** | 5 seconds (detected via Prometheus `runwise_canary_latency_seconds_bucket`). |
| **Time to Mitigate (TTM)**| 180 milliseconds (via `/v1/admin/canary/rollback`). |
| **Financial / Token Impact** | Token inflation of +18% on canary turns ($0.000093 vs $0.000079 per request). |

---

## 3. Incident Timeline

| Time (UTC) | Phase | Event Description |
| :--- | :--- | :--- |
| **20:45:00** | **Deployment** | Canary variant `v2.0` deployed via `ops/canary.json` with `weight: 0.5` (50% traffic). |
| **20:45:03** | **Traffic Routing** | Live customer sessions routed with session affinity (`customer_session_1` through `5` assigned to canary; `0` and others to stable). |
| **20:45:08** | **Detection** | Prometheus histogram observed canary p95 latency reaching **3,420 ms** (+420 ms above SLO). Alert `HighP95AgentLatency` triggered. |
| **20:45:11** | **Diagnosis** | Telemetry breakdown confirmed stable variant was healthy (1,450 ms), isolating regression to candidate prompt `v2.0`. |
| **20:45:14** | **Mitigation** | Operator executed: `uv run python ops/scripts/rollback.py --reason "Canary p95 latency breached SLO: 3420ms > 3000ms"`. |
| **20:45:14.18**| **Recovery** | API returned `{"status": "rolled_back", "enabled": false, "weight": 0.0}`. State persisted to disk. |
| **20:45:18** | **Verification** | 10 consecutive validation requests routed 100% to `v1.0` (stable). Latency dropped back to baseline. |

---

## 4. Root Cause Analysis (5 Whys)

1. **Why did customer response times degrade?**  
   The candidate canary model took over 3.4 seconds to return responses for order inquiries.
2. **Why was the canary model taking 3.4 seconds?**  
   Prompt `v2.0` caused the LLM to output expanded internal reasoning traces before emitting tool calls.
3. **Why did prompt `v2.0` cause expanded reasoning traces?**  
   The candidate prompt introduced redundant validation instructions and conversational preamble that encouraged unnecessary multi-step deliberation.
4. **Why was this not caught before the canary stage?**  
   The CI evaluation gate focused primarily on task accuracy and pass rate rather than strict latency regression bounds under production tool concurrency.
5. **Why was the blast radius contained?**  
   The Canary Router enforced cryptographically uniform session pinning, isolating the degradation to exactly 50% of users while preserving stable traffic, and the zero-rebuild rollback tooling allowed instantaneous remediation.

---

## 5. What Went Well vs. Where We Got Lucky

### What Went Well:
- **Session-Consistent Routing**: Sticky session hashing prevented customer context corruption; no user experienced mid-conversation prompt flips.
- **Isolated Telemetry**: Separate Prometheus metric dimensions (`variant="canary"` vs `variant="stable"`) instantly ruled out upstream network outages and isolated the issue to `v2.0`.
- **Instant Rollback Tooling**: Zero container rebuilds or restarts were required. The rollback completed in sub-200ms with zero connection drops.
- **Automated Verification**: Post-rollback automated assertions confirmed 10/10 subsequent customer sessions were pinned to stable.

### Where We Got Lucky:
- Canary weight was set to 50% for the test drill; in a higher-traffic environment, 50% is too aggressive for an unverified prompt. Initial rollout should start at 10%.
- Upstream Google Cloud quotas were sufficiently large that the token inflation did not trigger secondary HTTP 429 rate limits.

---

## 6. Action Items & Corrective Actions

| ID | Action Item | Type | Owner | Target Date |
| :--- | :--- | :---: | :---: | :---: |
| **ACT-01** | Implement **Prompt Trimming & Compression** (`prompts/agent/v1.1_trimmed.yaml`) to eliminate prompt bloat before deployment. | Preventative | `@llm-core` | Completed |
| **ACT-02** | Add automated canary auto-rollback hook triggered by Prometheus alerts without human operator intervention. | Mitigation | `@sre` | Next Sprint |
| **ACT-03** | Update Canary policy to enforce staged ramp: **10% $\rightarrow$ 25% $\rightarrow$ 50% $\rightarrow$ 100%** with 15-minute bake times. | Process | `@llm-core` | Immediate |
| **ACT-04** | Enforce a strict max token generation cap on candidate prompts in the CI evaluation gate. | Detection | `@evals` | Completed |
