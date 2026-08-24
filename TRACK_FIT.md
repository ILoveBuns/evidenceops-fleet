# Track fit and evidence gate

This matrix maps the current implementation to the All Things Agentic
requirements visible on August 23, 2026. It is an internal truth gate, not a
submission claim.

Official overview and requirements:
https://allthingsagentichackathon.devpost.com/

## Universal requirements

| Requirement | Current evidence | Gate |
|---|---|---|
| Gemini 3.5+ | `gemini-3.5-flash` in the ADK workflow and registry | Live deployed brief still required |
| Google agent framework | Graph-based Google ADK `Workflow` | Implemented and tested |
| Google Cloud infrastructure | Firestore adapter and least-privilege Cloud Run deployment | Actual deployment proof still required |
| Approximately four-minute demo | `DEMO_SCRIPT.md` targets 3:40 | Recording still required |
| Architecture diagram | `assets/architecture.svg` | Complete |
| Reproducible setup | README, container, deploy script, public verifier, fail-closed submission audit | Complete locally; video/cloud/published commit gates pending |

## Fortified Enterprise Fleet mapping

| Platform concern | Current evidence | Status |
|---|---|---|
| Discovery and lifecycle | `/agents` publishes version/lifecycle, owner, approved consumers, capability, data classification, region, and supports cross-department discovery | Implemented and tested |
| Runtime | Firestore-bound operations, deterministic per-attempt Cloud Tasks dispatch, failed-attempt recovery, transactional execution leases, and a token-guarded worker | Implemented and tested locally; live proof pending |
| Autonomous action | Fixed-host GitHub adapter retrieves commit and CI evidence, then dispatches the same durable operation | Implemented and tested locally; live public-repo proof pending |
| Secure long-term context | `/cases/{id}/memory` reconstructs redacted cross-session context from Firestore receipts; no TTL is disclosed | Implemented and tested; multi-week live proof pending |
| Agent identity and gateway | Dedicated Cloud Run service identity plus separate approval/brief guards | Implemented; live proof pending |
| Model/input guardrails | Raw evidence excluded from Gemini; deterministic policy owns authority | Implemented; Google Model Armor not claimed |
| Telemetry | OpenTelemetry spans omit evidence values | Implemented; live trace proof pending |

## Category decision gate

Remain in **Fortified Enterprise Fleet** only if all of these are true by
August 28:

1. A durable asynchronous operation path is implemented and tested.
2. Cloud Run, Firestore, and one live Gemini brief pass the public verifier.
3. The demo visibly proves service identity, durable state, and telemetry.

If any gate remains unmet, submit the same truthful product to **Taskmaster**
instead. Its complete evidence-review workflow already makes decisions and
produces an approval receipt beyond a chat loop, while avoiding unsupported
claims about a full enterprise agent platform.
