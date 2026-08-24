# Competitive positioning

This internal note records public gallery observations from August 24, 2026. It
is not submission copy and does not claim access to competitors' private code.

## Nearby public entries

| Entry | Public positioning | Collision risk |
|---|---|---|
| EvidenceBound Recovery Mesh | Fleet integrity, deterministic trust propagation, blast radius, selective recomputation, recovery | High on fail-closed architecture; lower on release-team workflow |
| AgentProof | Authorization, provider-confirmed action, false-success and replay checks | High on proof-of-action and idempotency |
| Proofline | Deterministic acceptance, contradiction checks, proof packets | High on evidence gating |
| kazilaw | Contract compliance review on Cloud Run and Firestore | Low on mechanics; competes for compliance persona attention |

## Defensible wedge

EvidenceOps Fleet should not lead with generic phrases such as "trustworthy
agents," "proof packs," or "fail-closed AI." Those claims are crowded. Lead
with one inspectable operational path:

> observed GitHub commit and CI checks → durable asynchronous operation →
> deterministic veto → redacted cross-session receipt → evidence-bound human
> approval.

The unlikely hero is a tiny release or compliance team, not a general enterprise
administrator. The distinct proof is that no operator copies CI text into chat,
the operation response does not return fetched evidence values, and a changed
digest cannot reuse an approval.

## Submission decisions

1. Keep the existing project name to avoid destabilizing repository, deployment,
   and video assets close to submission.
2. Put "GitHub-to-approval" and "tiny release teams" in the tagline and opening.
3. Demonstrate the real public GitHub adapter before synthetic failure cases.
4. Keep recovery, catalog, memory, and model redaction as architectural support,
   not as the opening pitch.
5. Never compare against or name another submission in public materials.
