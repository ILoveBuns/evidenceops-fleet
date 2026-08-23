#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'EOF'
Usage: scripts/deploy_google_cloud.sh PROJECT_ID [--region REGION]
       [--firestore-location LOCATION] [--plan]

Requires pre-created Secret Manager secrets:
  gemini-api-key, approval-token, brief-token

The script never reads or prints secret payloads.
EOF
}

project_id="${1:-}"
if [[ -z "$project_id" || "$project_id" == -* ]]; then
  usage >&2
  exit 2
fi
shift

region="us-central1"
firestore_location="us-central1"
plan_only=false
while (($#)); do
  case "$1" in
    --region)
      region="${2:?missing region}"
      shift 2
      ;;
    --firestore-location)
      firestore_location="${2:?missing Firestore location}"
      shift 2
      ;;
    --plan)
      plan_only=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

service="evidenceops-fleet"
service_account_name="evidenceops-fleet-runtime"
service_account="${service_account_name}@${project_id}.iam.gserviceaccount.com"
source_commit="$(git rev-parse HEAD)"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing deployment from a dirty Git worktree." >&2
  exit 1
fi

cat <<EOF
EvidenceOps Fleet deployment plan
  project:             $project_id
  region:              $region
  Firestore location:  $firestore_location
  service account:     $service_account
  source commit:       $source_commit
  public dashboard:    enabled
  paid brief endpoint: secret-protected
  public Gemini demo:  disabled
  instance range:      0..2
EOF

if $plan_only; then
  exit 0
fi

if ! command -v gcloud >/dev/null; then
  echo "gcloud is required for deployment." >&2
  exit 1
fi

active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
if [[ -z "$active_account" ]]; then
  echo "No active gcloud account. Authenticate interactively before deployment." >&2
  exit 1
fi

gcloud projects describe "$project_id" --format='value(projectId)' >/dev/null

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  --project "$project_id"

if ! gcloud iam service-accounts describe "$service_account" \
  --project "$project_id" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$service_account_name" \
    --display-name="EvidenceOps Fleet runtime" \
    --project "$project_id"
fi

if [[ "$active_account" == *".gserviceaccount.com" ]]; then
  deployer_member="serviceAccount:${active_account}"
else
  deployer_member="user:${active_account}"
fi
gcloud iam service-accounts add-iam-policy-binding "$service_account" \
  --project "$project_id" \
  --member="$deployer_member" \
  --role='roles/iam.serviceAccountUser' >/dev/null

gcloud projects add-iam-policy-binding "$project_id" \
  --member="serviceAccount:${service_account}" \
  --role='roles/datastore.user' \
  --condition=None >/dev/null

for secret in gemini-api-key approval-token brief-token; do
  if ! gcloud secrets describe "$secret" --project "$project_id" >/dev/null 2>&1; then
    echo "Required secret is missing: $secret" >&2
    echo "Create it and add a version without placing its value in this repository." >&2
    exit 1
  fi
  gcloud secrets add-iam-policy-binding "$secret" \
    --project "$project_id" \
    --member="serviceAccount:${service_account}" \
    --role='roles/secretmanager.secretAccessor' >/dev/null
done

if ! gcloud firestore databases describe --database='(default)' \
  --project "$project_id" >/dev/null 2>&1; then
  gcloud firestore databases create \
    --database='(default)' \
    --location="$firestore_location" \
    --project "$project_id"
fi

gcloud run deploy "$service" \
  --source . \
  --project "$project_id" \
  --region "$region" \
  --service-account "$service_account" \
  --allow-unauthenticated \
  --set-env-vars='EVIDENCEOPS_STORE=firestore,EVIDENCEOPS_PUBLIC_DEMO_BRIEFS=false' \
  --set-secrets='GOOGLE_API_KEY=gemini-api-key:latest,EVIDENCEOPS_APPROVAL_TOKEN=approval-token:latest,EVIDENCEOPS_BRIEF_TOKEN=brief-token:latest' \
  --min-instances=0 \
  --max-instances=2 \
  --concurrency=20 \
  --cpu=1 \
  --memory=1Gi \
  --timeout=60 \
  --labels="source-commit=${source_commit}"

service_url="$(gcloud run services describe "$service" \
  --project "$project_id" --region "$region" --format='value(status.url)')"
revision="$(gcloud run services describe "$service" \
  --project "$project_id" --region "$region" \
  --format='value(status.latestReadyRevisionName)')"

cat <<EOF
Deployment completed.
  URL:       $service_url
  revision:  $revision
  commit:    $source_commit

Run the secret-bearing verifier from a trusted terminal before making cloud or
Gemini claims. Do not paste the brief token into chat or commit it to Git.
EOF
