# Demo script — target 3:40, hard limit 4:00

Record one continuous, readable demonstration. Do not splice a successful model
response into the recording or imply that synthetic data is customer evidence.

## 0:00–0:25 — The unlikely hero

> Small release and compliance teams carry enterprise-sized risk. Before an
> irreversible action, they must prove that commits, tests, artifacts, and human
> review all agree. EvidenceOps Fleet gives that team a fail-closed evidence
> control plane instead of another chatbot.

Show the title, `SYNTHETIC DEMO` label, and the three scenarios.

## 0:25–0:55 — Architecture and authority boundary

Show `assets/architecture.svg`.

> Gemini 3.5 Flash agents handle intake, policy explanation, and supervision
> through a Google ADK workflow. But they cannot authorize a release. A
> deterministic verifier owns missing and conflict checks and binds the outcome
> to a canonical SHA-256 digest. Cloud Run hosts the service and Firestore stores
> cases and approval receipts transactionally.

## 0:55–1:35 — Complete evidence

Open the hosted console and run **Complete release evidence**.

> This request has source-attributed commit, test, and artifact receipts. The
> decision is ready, the digest makes the evidence set reproducible, and the
> trace shows which specialized stage produced each result.

Point to the decision, digest, and traces. Create the synthetic human approval.

> Approval is explicitly human-bound and idempotent. The raw reviewer label and
> note are hashed immediately; the receipt remains bound to this exact evidence
> digest.

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

Show `/agents` briefly, then show the brief's `source_decision`,
`source_evidence_digest`, model, and final author.

## 2:55–3:25 — Production evidence

Show the Cloud Run service and revision, then the Firestore records or a
redacted query result. Show the successful JSON output from:

```bash
python scripts/verify_public_deployment.py \
  https://YOUR-SERVICE-URL --require-gemini
```

> The public verifier independently replays ready, missing, conflict, approval,
> and Gemini paths. CI runs the test suite on Python 3.11 and 3.12. Secrets are
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
- Video is public or unlisted and playable without authentication.
- Final duration is under four minutes.
