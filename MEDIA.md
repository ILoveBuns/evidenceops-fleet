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
5dfa72b04a05f3eed4d41948b0c3d146c3fad5a03aa629f7c52a9632a3a2e73f  evidenceops-approved.png
4d838f50f232898ae270b4c32efb1713363690f92411ff54ca19c8b7681953ea  evidenceops-conflict.png
144836041d5a01b1708e866ae07c2212e7046b1ccea27f4cf80e6e19368b87ae  evidenceops-missing.png
8bf181bacd0252ad8137ba47286262dcc15d7505901001f6b1ced8f4c0e29930  evidenceops-ready.png
```

These images prove local deterministic behavior only. They do not prove Cloud
Run, Firestore, or live Gemini execution.
