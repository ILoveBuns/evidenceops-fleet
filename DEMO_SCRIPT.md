# Demo script — target 3:40, hard limit 4:00

Record one continuous, readable demonstration. Do not splice a successful model
response into the recording or imply that synthetic data is customer evidence.

## 0:00–0:25 — The unlikely hero

> Small release and compliance teams carry enterprise-sized risk. Before an
> irreversible action, they must prove that commits, tests, artifacts, and human
> review all agree. EvidenceOps Fleet autonomously moves observed GitHub CI to
> evidence-bound approval, with deterministic vetoes instead of another chatbot.

Show the title, `SYNTHETIC DEMO` label, and the three scenarios.

## 0:25–0:55 — Architecture and authority boundary

Show `assets/architecture.svg`.

> Gemini 3.5 Flash agents handle intake, policy explanation, and supervision
> through a Google ADK workflow. But they cannot authorize a release. A
> deterministic verifier owns missing and conflict checks and binds the outcome
> to a canonical SHA-256 digest. Cloud Run first writes an operation receipt to
> Firestore, then Cloud Tasks dispatches a deterministic per-attempt job. A
> dispatch retry deduplicates safely, while a failed execution can advance to a
> new attempt ID instead of being hidden by task-name retention.
> A Firestore transaction claims a five-minute execution lease, preventing
> overlapping delivery while allowing a crashed worker to be reclaimed.
> The queue itself is cost-bounded to five attempts within fifteen minutes.

## 0:55–1:35 — Autonomous GitHub CI evidence

Call `POST /integrations/github/operations` with the public repository and the
exact commit shown in GitHub Actions, then show the operation polling to ready.

> The fixed-host adapter retrieved the commit and two successful checks; no one
> copied CI text into the form. The operation first shows queued, then reaches
> ready. Its input digest makes dispatch reproducible, while the final receipt
> exposes one execution attempt and a cleared lease. The operation endpoint does
> not return the fetched evidence values.

Point to the decision, digest, and traces. Create the synthetic human approval.

> Approval is explicitly human-bound and idempotent. The raw reviewer label and
> note are hashed immediately; the receipt remains bound to this exact evidence
> digest.

Open `/cases/{case_id}/memory` and point to the ordered case, operation, and
approval events, `raw_evidence_included=false`, and the explicit retention policy.

## 1:35–2:15 — Fail closed twice

Run **Missing test receipt**.

> A missing test receipt blocks the case and identifies the exact remediation.
> The interface does not offer approval.

Run **Conflicting source commits**.

> Conflicting source commits also block the action. Gemini cannot talk either
> failure into a pass.

## 2:15–2:55 — Real ADK and Gemini brief

Generate a brief for the ready case and show the response.

> This is a real graph-based Google ADK workflow using Gemini 3.5 Flash. Gemini
> receives only the persisted decision, evidence digest, missing fields,
> conflicts, and trace summaries—never the original evidence values. Its prose
> is advisory, while the source decision and digest remain authoritative.

Open `/workflow`, then filter `/agents?department=internal-audit` and
`/agents?capability=bind-sha256-digest`. The workflow proves three ADK LLM agents
delegate the redacted brief while a deterministic authority remains outside
model control. The catalog shows four approved specialists; the capability
filter returns only the verifier with its owner, data class, and region. Then
show the brief's `source_decision`,
`source_evidence_digest`, model, and final author.

## 2:55–3:25 — Production evidence

Show the Cloud Run service and revision, the Cloud Tasks queue, then the
Firestore operation and case records or a redacted query result. Show the
successful JSON output from:

```bash
python scripts/verify_public_deployment.py \
  https://YOUR-SERVICE-URL --require-gemini \
  --source-commit "$(git rev-parse HEAD)" \
  --github-repository ILoveBuns/evidenceops-fleet \
  --github-commit "$(git rev-parse HEAD)"
```

> The public verifier independently replays durable asynchronous execution,
> autonomous GitHub evidence collection, ready, missing, conflict, approval,
> memory, and Gemini paths. CI runs the test suite on Python 3.11 and 3.12. Secrets are
> injected at deployment and never enter the repository.

## 3:25–3:40 — Close

> EvidenceOps Fleet helps the person holding the final operational risk move
> quickly without surrendering control: agents explain, deterministic policy
> decides, and a human authorizes the irreversible step.

## Recording checklist

- Hosted URL is the exact URL entered on Devpost.
- Browser zoom keeps decision, digest, and traces readable.
- Gemini generation succeeds live during the recording.
- Cloud Run revision and Firestore evidence are visible but secrets are not.
- Cloud Tasks queue and one terminal operation receipt are visible.
- Video is public, not unlisted, and playable without authentication.
- Final duration is under four minutes.
