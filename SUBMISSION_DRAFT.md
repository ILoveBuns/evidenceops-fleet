# Devpost submission draft

## Project name

EvidenceOps Fleet

## Tagline

Fail-closed evidence review for the small teams carrying enterprise-sized risk.

## Track

Fortified Enterprise Fleet

## Inspiration

The unlikely heroes of a release are often a tiny compliance or operations team.
They must reconcile commits, tests, artifacts, and human sign-off before an
irreversible action, but the evidence is fragmented across tools and a single
missing or contradictory receipt can become an incident.

## What it does

EvidenceOps Fleet turns source-attributed evidence into a reproducible decision.
An intake agent structures the request, a policy agent identifies missing and
conflicting evidence, a deterministic verifier binds the result to a canonical
SHA-256 digest, and a supervisor agent explains the outcome without being able
to override it. Ready cases can receive an idempotent, evidence-bound human
approval receipt; blocked cases fail closed.

The included console demonstrates three synthetic paths: a complete release,
a missing test receipt, and conflicting source commits. Raw reviewer labels and
notes are hashed immediately and are never returned or persisted.

## How we built it

- **Gemini 3.5 Flash** powers the intake, policy, and supervisor agents.
- **Google ADK** runs a graph-based workflow from intake to policy to supervisor.
- **FastAPI** exposes the deterministic control plane and review console.
- **Firestore** provides transactional, durable case and approval storage.
- **Cloud Run** hosts the containerized service.
- **OpenTelemetry** records privacy-preserving operational spans.

Gemini receives only the persisted decision, digest, missing fields, conflicts,
and trace summaries when creating a brief. It never receives the original
evidence values. Generated prose is advisory: the source decision and digest
are copied from the deterministic result and cannot be mutated by the model.

## Operational utility — 40%

The project addresses a common, expensive boundary: proving readiness before
publication, signing, payment, or another irreversible action. It gives a small
team a clear queue, explicit missing/conflict reasons, one-click synthetic test
paths, and an immutable approval receipt. The API is idempotent, rejects reused
case IDs with changed evidence, and exposes machine-readable outcomes for
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
Cloud Run deployment instructions, Secret Manager integration points,
authorization boundaries, OpenTelemetry spans, a responsive dashboard, tests
across Python 3.11 and 3.12, and a public-deployment verifier. The verifier
replays ready, missing, conflict, approval, and Gemini-brief paths and emits a
timestamped JSON receipt instead of relying on screenshots alone.

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
