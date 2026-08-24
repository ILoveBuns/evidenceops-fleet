# Devpost submission draft

## Project name

EvidenceOps Fleet

## Tagline

Autonomous GitHub-to-approval control for tiny release teams: deterministic
vetoes, durable receipts, and zero raw evidence.

## Track

Fortified Enterprise Fleet

## Inspiration

The unlikely heroes of a release are often a tiny compliance or operations team.
They must reconcile commits, tests, artifacts, and human sign-off before an
irreversible action, but the evidence is fragmented across tools and a single
missing or contradictory receipt can become an incident.

## What it does

EvidenceOps Fleet owns the narrow path from an observed GitHub commit and CI
checks to an evidence-bound human approval. No operator copies check text into a
chat window. An intake agent structures the request, a policy agent identifies
missing and conflicting evidence, a deterministic verifier binds the result to a
canonical SHA-256 digest, and a supervisor explains the outcome without being
able to override it. Ready cases can receive an idempotent approval receipt;
blocked cases fail closed.

Each request is first bound to a durable operation receipt. Cloud Tasks uses a
deterministic per-attempt task ID: dispatch retries deduplicate one attempt,
while a failed operation advances to a new task ID. The worker revalidates both
a Secret Manager-backed task token whenever the secret is present, including
during deployment transitions, and the original input digest before running.
A transactional execution lease prevents overlapping at-least-once deliveries
and permits safe recovery after a crashed worker.
The deployment reconciles the queue to five attempts over a 15-minute window,
so transient failures recover without creating an unbounded retry or cost loop.
Firestore mode refuses to fall back to in-process execution when queue
configuration is incomplete; it fails before persisting an operation.

The included console demonstrates three synthetic paths: a complete release,
a missing test receipt, and conflicting source commits. Raw reviewer labels and
notes are hashed immediately and are never returned or persisted.

A bounded GitHub integration can autonomously fetch a validated commit and its
CI check runs from the fixed GitHub API host. It forwards only the SHA,
successful-check summary, and source URLs into the durable operation; absent,
pending, or failed checks become missing evidence and fail closed.

## How we built it

- **Gemini 3.5 Flash** powers the intake, policy, and supervisor agents.
- **Google ADK** runs a graph-based workflow from intake to policy to supervisor.
- **FastAPI** exposes the deterministic control plane and review console.
- **Firestore** provides transactional, durable case and approval storage.
- **Cloud Tasks** provides durable, rate-limited asynchronous dispatch.
- **Cloud Run** hosts the containerized service.
- **OpenTelemetry** records privacy-preserving operational spans.

The agent catalog supports cross-department discovery by capability and
publishes lifecycle, owner, approved consumers, data classifications, and
allowed region for every specialist. An empty result is returned when no
approved registration satisfies the requested department and capability.

A read-only case memory endpoint reconstructs cross-session context from the
case, latest operation, approvals, and cached brief. It returns only IDs,
timestamps, statuses, and digests, explicitly reports that raw evidence is not
included, and discloses that no Firestore TTL is configured. This makes weeks of
context inspectable without inventing a production-duration claim.

Gemini receives only the persisted decision, digest, missing fields, conflicts,
and trace summaries when creating a brief. It never receives the original
evidence values. Generated prose is advisory: the source decision and digest
are copied from the deterministic result and cannot be mutated by the model.

## Operational utility — 40%

The project addresses a common, expensive boundary: proving readiness before
publication, signing, payment, or another irreversible action. It gives a small
team a clear queue, explicit missing/conflict reasons, one-click synthetic test
paths, and an immutable approval receipt. The API is idempotent, rejects reused
case IDs with changed evidence, safely re-dispatches queued operations after a
transient Cloud API failure, and exposes machine-readable outcomes for
integration with existing release systems.

## Architectural discipline — 30%

The architecture separates probabilistic reasoning from authority. Agents may
structure and explain, while deterministic policy and canonical hashing own the
decision. The workflow minimizes model disclosure, binds every downstream brief
and approval to the evidence digest, and fails closed when credentials,
evidence, or authorization are absent. Specialized roles are visible through
the agent registry and the architecture diagram.

## Production readiness — 30%

The repository includes a container image, transactional Firestore adapter,
rate-limited Cloud Tasks queue, Cloud Run deployment instructions, Secret Manager integration points,
authorization boundaries, OpenTelemetry spans, a responsive dashboard, tests
across Python 3.11 and 3.12, and a public-deployment verifier. The verifier
replays durable asynchronous execution, ready, missing, conflict, approval,
Gemini-brief, and redacted cross-session memory paths, then emits a timestamped
JSON receipt instead of relying on screenshots alone.

## Challenges

The hardest design choice was preventing a fluent model response from becoming
an authorization decision. We solved this by making deterministic checks and
the evidence digest authoritative, then constraining Gemini to a redacted,
post-decision brief. We also designed approval receipts to remain useful for
auditing without storing raw reviewer identity or notes.

## Accomplishments

- A real Google ADK workflow using Gemini 3.5 Flash.
- Fail-closed missing and conflict detection.
- Canonical evidence binding and idempotent case semantics.
- Durable asynchronous operations with deterministic, safely retryable dispatch.
- Privacy-preserving, evidence-bound human approval receipts.
- Reproducible local, CI, and public-deployment verification paths.

## What we learned

Agentic production systems need a narrow authority boundary more than they need
another general-purpose chatbot. Redaction, deterministic policy, idempotency,
and evidence binding make the agent useful in places where a plausible but
incorrect answer would otherwise be dangerous.

## What's next

Next steps are authenticated enterprise ingress, connectors for CI and issue
trackers, configurable policy packs, signed export bundles, and deployment-level
SLOs. Customer discovery would validate which irreversible workflow should be
the first production integration.

## Links to fill at submission

- Source repository: https://github.com/ILoveBuns/evidenceops-fleet
- Hosted application: `ADD_VERIFIED_CLOUD_RUN_URL`
- Demonstration video: `ADD_PUBLIC_VIDEO_URL`

## Data and traction disclosure

The dashboard uses synthetic demonstration data. The project does not claim
customers, revenue, or production usage.

## Prior work disclosure

This repository and implementation were created during the contest period. No
code was copied from the entrant's earlier Opportunity Memory Agent project;
only general experience with evidence-gated workflows informed the problem
selection.

## Final claims gate

Do not state that Cloud Run, Firestore, or live Gemini execution is verified
until `scripts/verify_public_deployment.py` has passed against the submitted URL
and the deployment evidence has been recorded in `CLOUD_EVIDENCE.md`.
