#!/usr/bin/env python3
"""Read-only preflight for the EvidenceOps Fleet Google Cloud deployment."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_SECRETS = (
    "gemini-api-key",
    "approval-token",
    "brief-token",
    "task-token",
)
REQUIRED_APIS = (
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtasks.googleapis.com",
)


def run_gcloud(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gcloud", *args], capture_output=True, text=True, check=False
    )


def item(name: str, passed: bool, detail: str) -> dict[str, str | bool]:
    return {"name": name, "passed": passed, "detail": detail}


def receipt(project_id: str, checks: list[dict], observations: list[dict]) -> dict:
    return {
        "schema": "evidenceops-google-cloud-preflight/v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "deployment_ready": all(check["passed"] for check in checks),
        "checks": checks,
        "blocking": [check["name"] for check in checks if not check["passed"]],
        "observations": observations,
    }


def preflight(project_id: str) -> dict:
    checks: list[dict[str, str | bool]] = []
    observations: list[dict[str, str | bool]] = []
    if shutil.which("gcloud") is None:
        checks.append(item("gcloud CLI", False, "gcloud is not installed"))
        return receipt(project_id, checks, observations)

    checks.append(item("gcloud CLI", True, "available"))
    account = run_gcloud(
        "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"
    )
    account_ready = account.returncode == 0 and bool(account.stdout.strip())
    checks.append(
        item(
            "active gcloud account",
            account_ready,
            "active identity available" if account_ready else "no active identity",
        )
    )

    project = run_gcloud(
        "projects", "describe", project_id, "--format=value(projectId)"
    )
    project_ready = project.returncode == 0 and project.stdout.strip() == project_id
    checks.append(
        item(
            "project access",
            project_ready,
            "project is accessible" if project_ready else "project is unavailable",
        )
    )

    billing = run_gcloud(
        "billing", "projects", "describe", project_id, "--format=value(billingEnabled)"
    )
    billing_ready = (
        billing.returncode == 0 and billing.stdout.strip().lower() == "true"
    )
    checks.append(
        item(
            "billing enabled",
            billing_ready,
            "billing is enabled" if billing_ready else "billing is not enabled",
        )
    )

    missing_secrets = [
        secret
        for secret in REQUIRED_SECRETS
        if run_gcloud("secrets", "describe", secret, "--project", project_id).returncode
        != 0
    ]
    checks.append(
        item("required secrets", not missing_secrets, f"missing={missing_secrets}")
    )

    services = run_gcloud(
        "services",
        "list",
        "--enabled",
        "--project",
        project_id,
        "--format=value(config.name)",
    )
    enabled = set(services.stdout.splitlines()) if services.returncode == 0 else set()
    missing_apis = sorted(set(REQUIRED_APIS) - enabled)
    observations.append(
        item(
            "required APIs already enabled",
            not missing_apis,
            f"missing={missing_apis}; deploy script enables them",
        )
    )
    return receipt(project_id, checks, observations)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = preflight(args.project_id)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n")
    return 0 if result["deployment_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
