# Judging scorecard

This is an internal, fail-closed map from the official weighted judging criteria
to evidence a judge can inspect. It is not a claim that pending cloud or video
evidence already exists.

## Innovation & Operational Utility (40%)

| Judge question | Evidence location | Remaining risk |
|---|---|---|
| Does it remove real friction rather than chat? | `SUBMISSION_DRAFT.md` GitHub-to-approval wedge; `POST /integrations/github/operations`; durable operation and approval receipts | Video must show one uninterrupted source-to-decision run |
| Is autonomous execution high value? | GitHub adapter fetches observed commit and CI state, then dispatches the governed workflow | Do not describe synthetic examples as customer use |
| Is a fleet warranted? | `/agents` catalog separates intake, policy, verifier, and supervisor authority | Demo must make delegation visible rather than merely listing agents |
| Is the unlikely hero clear? | Small compliance and release-operations teams carrying enterprise-sized risk | Keep this persona explicit in the first 20 seconds |

## Architectural Discipline & Tech Stack (30%)

| Judge question | Evidence location | Remaining risk |
|---|---|---|
| Are authority boundaries enforced? | Deterministic policy and digest own decisions; Gemini receives redacted post-decision state only | Live Gemini receipt still requires deployment |
| Is state durable and retry-safe? | Firestore store, Cloud Tasks per-attempt IDs, five-minute transactional lease, bounded retry policy | Cloud evidence remains pending |
| Are tools isolated and scoped? | Fixed GitHub API host, optional token, Secret Manager worker guard, fail-closed Firestore mode | Cloud service identity must be visible in the demo |
| Can failures recover safely? | Duplicate dispatch, failed-attempt advance, lease reclaim, and missing/conflict tests | Show at least one recovery or fail-closed path live |
| Is cross-session memory governed? | `/cases/{case_id}/memory` returns IDs, timestamps, statuses, and digests only | No multi-week production-history claim is permitted |

## Demo & Production Readiness (30%)

| Judge question | Evidence location | Remaining risk |
|---|---|---|
| Is there unedited proof of action? | `DEMO_SCRIPT.md` is continuous for 220 seconds | Public recording not yet available |
| Is Google Cloud visibly running? | `CLOUD_EVIDENCE.md` and public verifier define the proof receipt | Cloud Run, Firestore, Cloud Tasks, and Gemini observations remain pending |
| Can judges reproduce it? | README local/cloud steps, container, deployment script, verifier | Published source must match the demonstrated commit |
| Is the architecture understandable? | `assets/architecture.svg` | Keep the diagram on screen while explaining authority and retry boundaries |

## Final evidence gate

Run `python scripts/audit_submission_readiness.py`. Submission is not ready while
the public video, observed Google Cloud evidence, or clean published source gate
is false. Optional bonus activities must never replace these required proofs.
