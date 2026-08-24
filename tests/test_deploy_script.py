import os
import shutil
import stat
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "deploy_google_cloud.sh"


def initialize_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    deployed_script = scripts / SCRIPT.name
    shutil.copy2(SCRIPT, deployed_script)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


def test_deployment_executes_least_privilege_command_sequence(tmp_path: Path) -> None:
    repo = initialize_repo(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "gcloud.log"
    gcloud = fake_bin / "gcloud"
    gcloud.write_text(
        """#!/usr/bin/env bash
printf '%q ' "$@" >> "$GCLOUD_LOG"
printf '\\n' >> "$GCLOUD_LOG"
case "$*" in
  "auth list"*) echo "deployer@example.test" ;;
  "iam service-accounts describe"*) exit 1 ;;
  "firestore databases describe"*) exit 1 ;;
  "tasks queues describe"*) exit 1 ;;
  *"format=value(status.url)"*) echo "https://evidenceops.example.test" ;;
  *"format=value(status.latestReadyRevisionName)"*) echo "evidenceops-fleet-00001" ;;
esac
"""
    )
    gcloud.chmod(gcloud.stat().st_mode | stat.S_IXUSR)
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "GCLOUD_LOG": str(log),
    }
    result = subprocess.run(
        [str(repo / "scripts" / SCRIPT.name), "judge-project"],
        cwd=repo,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    commands = log.read_text()
    assert "iam service-accounts create evidenceops-fleet-runtime" in commands
    assert "roles/iam.serviceAccountUser" in commands
    assert "user:deployer@example.test" in commands
    assert "roles/datastore.user" in commands
    assert "roles/cloudtasks.enqueuer" in commands
    assert commands.count("roles/secretmanager.secretAccessor") == 4
    assert "firestore databases create" in commands
    assert "tasks queues create evidenceops-fleet" in commands
    assert "--max-concurrent-dispatches=2" in commands
    assert "--max-attempts=5" in commands
    assert "--max-retry-duration=900s" in commands
    assert "--min-backoff=5s" in commands
    assert "--max-backoff=60s" in commands
    assert "--max-doublings=3" in commands
    assert "tasks queues update evidenceops-fleet" in commands
    assert "run deploy evidenceops-fleet" in commands
    assert "--max-instances=2" in commands
    assert "EVIDENCEOPS_PUBLIC_DEMO_BRIEFS=false" in commands
    assert "EVIDENCEOPS_TASK_TOKEN=task-token:latest" in commands
    assert "run services update evidenceops-fleet" in commands
    assert "EVIDENCEOPS_TASKS_QUEUE=projects/judge-project/locations/us-central1/queues/evidenceops-fleet" in commands
    assert "EVIDENCEOPS_WORKER_URL=https://evidenceops.example.test" in commands
    assert "source-commit=" in commands
    assert "https://evidenceops.example.test" in result.stdout


def test_deployment_reconciles_existing_queue_retry_policy(tmp_path: Path) -> None:
    repo = initialize_repo(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "gcloud.log"
    gcloud = fake_bin / "gcloud"
    gcloud.write_text(
        """#!/usr/bin/env bash
printf '%q ' "$@" >> "$GCLOUD_LOG"
printf '\\n' >> "$GCLOUD_LOG"
case "$*" in
  "auth list"*) echo "deployer@example.test" ;;
  *"format=value(status.url)"*) echo "https://evidenceops.example.test" ;;
  *"format=value(status.latestReadyRevisionName)"*) echo "evidenceops-fleet-00001" ;;
esac
"""
    )
    gcloud.chmod(gcloud.stat().st_mode | stat.S_IXUSR)
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "GCLOUD_LOG": str(log),
    }

    subprocess.run(
        [str(repo / "scripts" / SCRIPT.name), "judge-project"],
        cwd=repo,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )

    commands = log.read_text()
    assert "tasks queues create evidenceops-fleet" not in commands
    assert "tasks queues update evidenceops-fleet" in commands
    assert "--max-attempts=5" in commands
    assert "--max-retry-duration=900s" in commands


def test_deployment_rejects_untracked_worktree(tmp_path: Path) -> None:
    repo = initialize_repo(tmp_path)
    (repo / "untracked.txt").write_text("not reviewed")
    result = subprocess.run(
        [str(repo / "scripts" / SCRIPT.name), "judge-project", "--plan"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    assert "Refusing deployment from a dirty Git worktree" in result.stderr
