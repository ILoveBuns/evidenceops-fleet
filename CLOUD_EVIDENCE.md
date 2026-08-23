# Cloud deployment evidence

This file is a verification template, not a deployment claim. Fill it only from
observed Google Cloud state and a passing public probe.

## Deployment record

- Google Cloud project ID: `PENDING`
- Cloud Run service: `evidenceops-fleet`
- Region: `PENDING`
- Public service URL: `PENDING`
- Deployed revision: `PENDING`
- Source commit: `PENDING`
- Deployment timestamp (UTC): `PENDING`
- Firestore database/location: `PENDING`
- Gemini model observed in successful brief: `PENDING`

## Required evidence

- [ ] Cloud Run reports the submitted revision as ready.
- [ ] The source commit matches the public repository.
- [ ] Firestore contains probe cases and an approval receipt.
- [ ] No API key, approval token, raw reviewer identity, or raw note is exposed.
- [ ] `GET /health`, `GET /agents`, and the dashboard pass.
- [ ] Ready, missing, and conflicting cases return expected decisions.
- [ ] Ready synthetic approval succeeds and blocked approval fails.
- [ ] Live Gemini brief succeeds and remains bound to source decision/digest.
- [ ] JSON probe receipt is saved locally and reviewed.

## Verification command

```bash
EVIDENCEOPS_BRIEF_TOKEN='READ_FROM_SECRET_MANAGER' \
python scripts/verify_public_deployment.py \
  https://YOUR-SERVICE-URL \
  --require-gemini \
  --source-commit "$(git rev-parse HEAD)" \
  --output deployment-receipt.json
```

`deployment-receipt.json` is intentionally ignored by Git. Review it before
using it as submission evidence.

## Rollback

List ready revisions, then route all traffic to the last verified revision:

```bash
gcloud run revisions list --service=evidenceops-fleet \
  --project=YOUR_PROJECT_ID --region=us-central1
gcloud run services update-traffic evidenceops-fleet \
  --project=YOUR_PROJECT_ID --region=us-central1 \
  --to-revisions=LAST_VERIFIED_REVISION=100
```

Rollback changes serving traffic only. It does not delete Firestore evidence or
Secret Manager versions.
