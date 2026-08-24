from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


REQUIRED_FILES = (
    "pyproject.toml",
    "README.md",
    "SUBMISSION_DRAFT.md",
    "DEMO_SCRIPT.md",
    "CLOUD_EVIDENCE.md",
    "TRACK_FIT.md",
    "JUDGING_SCORECARD.md",
    "BONUS_DRAFTS.md",
    "assets/architecture.svg",
    "scripts/deploy_google_cloud.sh",
    "scripts/verify_public_deployment.py",
)


def check(name: str, passed: bool, detail: str) -> dict[str, str | bool]:
    return {"name": name, "passed": passed, "detail": detail}


def git_output(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def audit(root: Path) -> dict:
    checks: list[dict[str, str | bool]] = []
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    checks.append(check("required files", not missing, f"missing={missing}"))

    readable = not missing
    submission = (root / "SUBMISSION_DRAFT.md").read_text() if readable else ""
    cloud = (root / "CLOUD_EVIDENCE.md").read_text() if readable else ""
    readme = (root / "README.md").read_text() if readable else ""
    demo = (root / "DEMO_SCRIPT.md").read_text() if readable else ""
    scorecard = (root / "JUDGING_SCORECARD.md").read_text() if readable else ""
    bonus_drafts = (root / "BONUS_DRAFTS.md").read_text() if readable else ""
    pyproject = (root / "pyproject.toml").read_text() if (root / "pyproject.toml").is_file() else ""

    checks.append(
        check(
            "public repository",
            "https://github.com/ILoveBuns/evidenceops-fleet" in submission,
            "public repository URL must be present",
        )
    )
    checks.append(
        check(
            "spin-up instructions",
            "pip install -e '.[test]'" in readme
            and "scripts/deploy_google_cloud.sh" in readme,
            "README must cover local and Google Cloud setup",
        )
    )
    stack_markers = (
        "gemini-3.5-flash",
        "google-adk==2.7.1",
        "google-cloud-firestore",
        "google-cloud-tasks",
    )
    checks.append(
        check(
            "required Google stack",
            all(marker in (readme + pyproject) for marker in stack_markers),
            "Gemini 3.5, ADK, Firestore, and Cloud Tasks must be declared",
        )
    )

    architecture_ok = False
    if not missing:
        try:
            ElementTree.parse(root / "assets/architecture.svg")
            architecture_ok = all(
                marker in (root / "assets/architecture.svg").read_text()
                for marker in ("Gemini 3.5 Flash", "Cloud Tasks queue", "Firestore receipts")
            )
        except ElementTree.ParseError:
            architecture_ok = False
    checks.append(
        check(
            "architecture diagram",
            architecture_ok,
            "SVG must parse and show Gemini, Cloud Tasks, and Firestore",
        )
    )

    timestamps = [
        (int(start_m) * 60 + int(start_s), int(end_m) * 60 + int(end_s))
        for start_m, start_s, end_m, end_s in re.findall(
            r"## (\d+):(\d{2})[–-](\d+):(\d{2})", demo
        )
    ]
    continuous = bool(timestamps) and timestamps[0][0] == 0
    continuous = continuous and all(
        current[1] == following[0]
        for current, following in zip(timestamps, timestamps[1:])
    )
    demo_seconds = timestamps[-1][1] if timestamps else 0
    checks.append(
        check(
            "four-minute demo plan",
            continuous and 1 <= demo_seconds <= 240,
            f"continuous={continuous} duration_seconds={demo_seconds}",
        )
    )
    scorecard_markers = (
        "Innovation & Operational Utility (40%)",
        "Architectural Discipline & Tech Stack (30%)",
        "Demo & Production Readiness (30%)",
        "Evidence location",
        "Remaining risk",
    )
    checks.append(
        check(
            "judging scorecard",
            all(marker in scorecard for marker in scorecard_markers),
            "scorecard must map every weighted criterion to evidence and risk",
        )
    )

    video_match = re.search(r"Demonstration video:\s*(\S+)", submission)
    video_url = video_match.group(1) if video_match else ""
    video_ready = video_url.startswith("https://") and "ADD_PUBLIC" not in video_url
    checks.append(
        check("public demo video", video_ready, video_url or "missing video URL")
    )

    cloud_placeholders = ("PENDING", "YOUR-SERVICE-URL")
    cloud_ready = not any(marker in cloud for marker in cloud_placeholders)
    cloud_ready = cloud_ready and "passed" in cloud.lower()
    checks.append(
        check(
            "observed Google Cloud evidence",
            cloud_ready,
            "CLOUD_EVIDENCE.md must contain observed values and a passing receipt",
        )
    )

    try:
        dirty = git_output(root, "status", "--porcelain")
        head = git_output(root, "rev-parse", "HEAD")
        remote = git_output(root, "rev-parse", "origin/main")
        git_ready = not dirty and head == remote
        git_detail = f"clean={not bool(dirty)} head_matches_origin={head == remote}"
    except subprocess.CalledProcessError:
        git_ready = False
        git_detail = "unable to verify Git state"
    checks.append(check("clean published source", git_ready, git_detail))

    bonus_checks = []
    for name, label in (
        ("public build story", "Public build story"),
        ("public social post", "Public social post"),
    ):
        match = re.search(rf"{label}:\s*(\S+)", bonus_drafts)
        url = match.group(1).strip("`<>") if match else ""
        ready = url.startswith("https://") and "ADD_PUBLIC" not in url
        bonus_checks.append(check(name, ready, url or "missing public URL"))
    model_match = re.search(r"Additional Google AI model:\s*(\S+)", cloud)
    model_name = model_match.group(1).strip("`<>") if model_match else ""
    model_ready = bool(model_name) and model_name != "PENDING"
    bonus_checks.append(
        check(
            "additional Google AI model",
            model_ready,
            model_name or "no additional model evidence",
        )
    )

    return {
        "schema": "evidenceops-submission-readiness/v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "blocking": [item["name"] for item in checks if not item["passed"]],
        "bonus_checks": bonus_checks,
        "bonus_points_ready": round(
            sum(0.2 for item in bonus_checks if item["passed"]), 1
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = audit(args.root.resolve())
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
