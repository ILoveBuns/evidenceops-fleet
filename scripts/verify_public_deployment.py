#!/usr/bin/env python3
"""Probe a public EvidenceOps Fleet deployment without sending secrets."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def request_json(base_url: str, path: str, method: str = "GET", payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = raw.decode(errors="replace")
        return error.code, detail


def request_text(base_url: str, path: str):
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read().decode()


def case_payload(case_id: str, mode: str):
    evidence = [
        {"name": "commit", "value": "abc123", "source": "https://example.test/commit"},
        {"name": "tests", "value": "17 passed", "source": "https://example.test/tests"},
        {"name": "artifact", "value": "sha256:123", "source": "https://example.test/artifact"},
    ]
    if mode == "missing":
        evidence = [item for item in evidence if item["name"] != "tests"]
    if mode == "conflict":
        evidence.append(
            {"name": "commit", "value": "different", "source": "https://example.test/review"}
        )
    return {
        "case_id": case_id,
        "objective": "Verify synthetic release evidence before publication",
        "required_evidence": ["commit", "tests", "artifact"],
        "evidence": evidence,
    }


def verify(base_url: str, require_gemini: bool, source_commit: str | None):
    checks = []

    def check(name: str, passed: bool, observed):
        checks.append({"name": name, "passed": bool(passed), "observed": observed})

    status, health = request_json(base_url, "/health")
    check("health", status == 200 and health == {"status": "ok", "service": "evidenceops-fleet"}, health)

    status, agents = request_json(base_url, "/agents")
    names = {item.get("name") for item in agents} if isinstance(agents, list) else set()
    models = {item.get("model") for item in agents} if isinstance(agents, list) else set()
    check(
        "agent registry",
        status == 200 and names == {"intake", "policy", "verifier", "supervisor"} and "gemini-3.5-flash" in models,
        {"names": sorted(names), "models": sorted(str(model) for model in models)},
    )

    status, dashboard = request_text(base_url, "/")
    check(
        "dashboard disclosure",
        status == 200 and all(text in dashboard for text in ("SYNTHETIC DEMO", "Missing test receipt", "Conflicting source commits")),
        {"status": status, "synthetic_label": "SYNTHETIC DEMO" in dashboard},
    )

    run_id = uuid4().hex[:12]
    results = {}
    for mode, expected in (("ready", "ready"), ("missing", "blocked"), ("conflict", "blocked")):
        case_id = f"demo-probe-{mode}-{run_id}"
        status, result = request_json(base_url, "/cases", "POST", case_payload(case_id, mode))
        passed = status == 201 and result.get("decision") == expected
        if mode == "missing":
            passed = passed and result.get("missing") == ["tests"]
        if mode == "conflict":
            passed = passed and bool(result.get("conflicts"))
        check(f"{mode} case", passed, {"status": status, "result": result})
        results[mode] = result

    ready_id = results["ready"].get("case_id", "")
    approval = {
        "approval_id": f"probe-approval-{run_id}",
        "actor_label": "synthetic-demo-reviewer",
        "note": "Synthetic public deployment verification receipt",
    }
    status, receipt = request_json(base_url, f"/cases/{ready_id}/approvals", "POST", approval)
    serialized = json.dumps(receipt)
    check(
        "ready approval redaction",
        status == 201 and approval["actor_label"] not in serialized and approval["note"] not in serialized,
        {"status": status, "receipt": receipt},
    )

    blocked_id = results["missing"].get("case_id", "")
    status, blocked_approval = request_json(
        base_url,
        f"/cases/{blocked_id}/approvals",
        "POST",
        {**approval, "approval_id": f"blocked-approval-{run_id}"},
    )
    check("blocked approval", status == 409, {"status": status, "result": blocked_approval})

    status, brief = request_json(base_url, f"/cases/{ready_id}/brief", "POST")
    if status == 200:
        brief_passed = (
            brief.get("source_decision") == results["ready"].get("decision")
            and brief.get("source_evidence_digest") == results["ready"].get("evidence_digest")
            and brief.get("model") == "gemini-3.5-flash"
        )
    else:
        brief_passed = not require_gemini and status == 503
    check("Gemini ADK brief", brief_passed, {"status": status, "result": brief})

    return {
        "schema": "evidenceops-deployment-receipt/v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url.rstrip("/"),
        "source_commit": source_commit,
        "require_gemini": require_gemini,
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--require-gemini", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(args.base_url, args.require_gemini, args.source_commit)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 2
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
