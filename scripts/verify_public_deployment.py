#!/usr/bin/env python3
"""Probe a public EvidenceOps Fleet deployment without sending secrets."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def request_json(base_url: str, path: str, method: str = "GET", payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"content-type": "application/json", **(headers or {})},
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


def verify(
    base_url: str,
    require_gemini: bool,
    source_commit: str | None,
    github_repository: str | None = None,
    github_commit: str | None = None,
):
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

    status, workflow = request_json(base_url, "/workflow")
    workflow_nodes = {
        node.get("name"): node.get("kind") for node in workflow.get("nodes", [])
    }
    check(
        "workflow delegation",
        status == 200
        and workflow.get("framework") == "google-adk"
        and workflow.get("edges")
        == [
            ["START", "intake_agent"],
            ["intake_agent", "policy_agent"],
            ["policy_agent", "supervisor_agent"],
        ]
        and workflow_nodes
        == {
            "intake_agent": "llm-agent",
            "policy_agent": "llm-agent",
            "supervisor_agent": "llm-agent",
            "deterministic_verifier": "deterministic-authority",
        }
        and "cannot mutate" in workflow.get("decision_authority", ""),
        workflow,
    )

    status, runtime = request_json(base_url, "/runtime")
    check(
        "runtime disclosure",
        status == 200
        and set(runtime)
        == {
            "store",
            "gemini_ready",
            "approval_guard",
            "brief_guard",
            "worker_guard",
            "operation_runtime",
        }
        and runtime.get("store") in {"memory", "firestore"}
        and runtime.get("approval_guard") in {"demo-only", "secret"}
        and runtime.get("brief_guard") in {"public-demo", "secret"}
        and runtime.get("worker_guard") in {"local-only", "secret"}
        and (
            (
                runtime.get("store") == "memory"
                and runtime.get("operation_runtime") == "local-background"
                and runtime.get("worker_guard") in {"local-only", "secret"}
            )
            or (
                runtime.get("store") == "firestore"
                and runtime.get("operation_runtime") == "cloud-tasks"
                and runtime.get("worker_guard") == "secret"
            )
        )
        and (not require_gemini or runtime.get("gemini_ready") is True),
        runtime,
    )

    status, dashboard = request_text(base_url, "/")
    check(
        "dashboard disclosure",
        status == 200 and all(text in dashboard for text in ("SYNTHETIC DEMO", "Missing test receipt", "Conflicting source commits")),
        {"status": status, "synthetic_label": "SYNTHETIC DEMO" in dashboard},
    )

    run_id = uuid4().hex[:12]
    operation_case_id = f"demo-probe-operation-{run_id}"
    status, operation = request_json(
        base_url,
        "/operations",
        "POST",
        case_payload(operation_case_id, "ready"),
    )
    operation_id = operation.get("operation_id", "")
    terminal_operation = operation
    if status == 202 and operation_id:
        for _ in range(15):
            poll_status, terminal_operation = request_json(
                base_url, f"/operations/{operation_id}"
            )
            if poll_status == 200 and terminal_operation.get("status") in {
                "ready",
                "blocked",
                "failed",
            }:
                break
            time.sleep(2)
    serialized_operation = json.dumps(terminal_operation)
    check(
        "durable asynchronous operation",
        status == 202
        and terminal_operation.get("status") == "ready"
        and terminal_operation.get("decision") == "ready"
        and terminal_operation.get("attempt_count", 0) >= 1
        and terminal_operation.get("lease_expires_at") is None
        and "abc123" not in serialized_operation
        and "example.test" not in serialized_operation,
        {"create_status": status, "operation": terminal_operation},
    )

    if github_repository and github_commit:
        github_case_id = f"demo-probe-github-{run_id}"
        status, github_operation = request_json(
            base_url,
            "/integrations/github/operations",
            "POST",
            {
                "case_id": github_case_id,
                "objective": "Verify observed GitHub commit and CI evidence",
                "repository": github_repository,
                "commit_sha": github_commit,
            },
        )
        github_operation_id = github_operation.get("operation_id", "")
        terminal_github_operation = github_operation
        if status == 202 and github_operation_id:
            for _ in range(15):
                poll_status, terminal_github_operation = request_json(
                    base_url, f"/operations/{github_operation_id}"
                )
                if poll_status == 200 and terminal_github_operation.get("status") in {
                    "ready",
                    "blocked",
                    "failed",
                }:
                    break
                time.sleep(2)
        serialized_github_operation = json.dumps(terminal_github_operation)
        check(
            "GitHub autonomous evidence",
            status == 202
            and terminal_github_operation.get("status") == "ready"
            and terminal_github_operation.get("decision") == "ready"
            and terminal_github_operation.get("attempt_count", 0) >= 1
            and github_commit not in serialized_github_operation
            and "api.github.com" not in serialized_github_operation,
            {
                "repository": github_repository,
                "requested_commit": github_commit,
                "operation": terminal_github_operation,
            },
        )

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

    brief_token = os.getenv("EVIDENCEOPS_BRIEF_TOKEN")
    brief_headers = {"x-brief-token": brief_token} if brief_token else {}
    status, brief = request_json(
        base_url, f"/cases/{ready_id}/brief", "POST", headers=brief_headers
    )
    if status == 200:
        brief_passed = (
            brief.get("source_decision") == results["ready"].get("decision")
            and brief.get("source_evidence_digest") == results["ready"].get("evidence_digest")
            and brief.get("model") == "gemini-3.5-flash"
        )
    else:
        brief_passed = not require_gemini and status in {403, 503}
    check("Gemini ADK brief", brief_passed, {"status": status, "result": brief})

    status, memory = request_json(base_url, f"/cases/{ready_id}/memory")
    serialized_memory = json.dumps(memory)
    memory_types = {
        event.get("event_type") for event in memory.get("events", [])
    }
    expected_types = {"case", "approval"}
    if brief.get("source_evidence_digest"):
        expected_types.add("brief")
    check(
        "cross-session memory redaction",
        status == 200
        and memory.get("schema_name") == "evidenceops-case-memory/v1"
        and memory.get("retention_policy") == "no-ttl-configured"
        and memory.get("raw_evidence_included") is False
        and expected_types.issubset(memory_types)
        and approval["actor_label"] not in serialized_memory
        and approval["note"] not in serialized_memory
        and "abc123" not in serialized_memory,
        {"status": status, "memory": memory},
    )

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
    parser.add_argument("--github-repository")
    parser.add_argument("--github-commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if bool(args.github_repository) != bool(args.github_commit):
            parser.error("--github-repository and --github-commit must be provided together")
        receipt = verify(
            args.base_url,
            args.require_gemini,
            args.source_commit,
            args.github_repository,
            args.github_commit,
        )
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
