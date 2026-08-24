import os
import stat
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "preflight_google_cloud.py"


def fake_gcloud(tmp_path: Path, missing_secret: str | None = None) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    executable = fake_bin / "gcloud"
    executable.write_text(
        f"""#!/usr/bin/env bash
case "$*" in
  "auth list"*) echo "deployer@example.test" ;;
  "projects describe judge-project"*) echo "judge-project" ;;
  "billing projects describe judge-project"*) echo "True" ;;
  "secrets describe {missing_secret}"*) exit 1 ;;
  "services list"*) printf '%s\\n' run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com secretmanager.googleapis.com cloudtasks.googleapis.com ;;
esac
"""
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return fake_bin


def run_preflight(tmp_path: Path, fake_bin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), "judge-project"],
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
    )


def test_preflight_passes_without_mutating_cloud_state(tmp_path: Path) -> None:
    result = run_preflight(tmp_path, fake_gcloud(tmp_path))
    assert result.returncode == 0
    assert '"deployment_ready": true' in result.stdout
    assert '"blocking": []' in result.stdout
    assert "active identity available" in result.stdout
    assert "deployer@example.test" not in result.stdout


def test_preflight_fails_closed_on_missing_secret(tmp_path: Path) -> None:
    result = run_preflight(tmp_path, fake_gcloud(tmp_path, "task-token"))
    assert result.returncode == 1
    assert '"deployment_ready": false' in result.stdout
    assert '"required secrets"' in result.stdout
    assert "task-token" in result.stdout


def test_preflight_reports_missing_cli(tmp_path: Path) -> None:
    result = subprocess.run(
        ["/usr/bin/python3", str(SCRIPT), "judge-project"],
        env={"PATH": str(tmp_path)},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    assert "gcloud is not installed" in result.stdout
