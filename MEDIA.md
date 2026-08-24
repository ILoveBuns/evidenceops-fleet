# Submission media

All screenshots are direct captures of the local EvidenceOps Fleet console using
synthetic fixtures. They contain no customer data, credentials, API keys, raw
reviewer identity, or revenue claims.

## Recommended order and captions

1. **Complete evidence becomes ready**  
   `assets/screenshots/evidenceops-ready.png`  
   A complete source-attributed release package passes deterministic policy,
   receives a canonical SHA-256 evidence digest, and exposes the specialist
   intake, policy, and verifier traces.

2. **Missing tests fail closed**  
   `assets/screenshots/evidenceops-missing.png`  
   The same bounded workflow blocks publication when the required test receipt
   is absent and names `tests` as the missing evidence.

3. **Conflicting commits fail closed**  
   `assets/screenshots/evidenceops-conflict.png`  
   Two source-attributed commit values produce a visible `commit` conflict;
   generated prose cannot override the blocked decision.

4. **Human approval stays evidence-bound and private**  
   `assets/screenshots/evidenceops-approved.png`  
   A ready synthetic case receives an idempotent approval receipt bound to the
   evidence digest. Reviewer label and note appear only as digests.

5. **Architecture**  
   `assets/architecture.svg`  
   Gemini 3.5 and Google ADK handle specialist reasoning while deterministic
   policy, canonical verification, Firestore, and a human boundary retain
   authority.

## Integrity receipt

```text
abfb467e898c017b4fe28ca6a49c406b4b9d69ed14c2290060c85dac43a64d53  evidenceops-approved.png
dc8b5ac43cdb1b2d12cf6a34e4b4786c6529dbb516560034667d8f4b66bb7c03  evidenceops-conflict.png
79e3713aadb56200f7306e54d9cc997528b4779dda1bee3a671046792bdd9823  evidenceops-missing.png
0a76a366dfcdec90a594cc47d628dd9d6b6521ced369d02fbc99c0f7523aecf9  evidenceops-ready.png
```

These images prove local deterministic behavior only. They do not prove Cloud
Run, Firestore, or live Gemini execution.
