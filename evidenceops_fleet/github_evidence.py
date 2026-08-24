from __future__ import annotations

import json
from os import getenv
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import (
    EvidenceCaseCreate,
    EvidenceItem,
    GitHubOperationCreate,
)


class GitHubEvidenceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class GitHubEvidenceAdapter:
    def __init__(self, opener=urlopen) -> None:
        self._opener = opener

    def collect(self, request: GitHubOperationCreate) -> EvidenceCaseCreate:
        owner, repository = request.repository.split("/", 1)
        repository_path = f"{quote(owner)}/{quote(repository)}"
        commit_path = f"/repos/{repository_path}/commits/{quote(request.commit_sha)}"
        checks_path = f"{commit_path}/check-runs"
        commit = self._get(commit_path)
        checks = self._get(checks_path)
        observed_sha = str(commit.get("sha", ""))
        if not observed_sha.lower().startswith(request.commit_sha.lower()):
            raise GitHubEvidenceError("GitHub returned a different commit", 409)

        evidence = [
            EvidenceItem(
                name="commit",
                value=observed_sha,
                source=str(commit.get("html_url") or self._api_url(commit_path)),
            )
        ]
        check_runs = checks.get("check_runs", [])
        if isinstance(check_runs, list) and check_runs and all(
            isinstance(run, dict)
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            for run in check_runs
        ):
            names = sorted(str(run.get("name", "unnamed")) for run in check_runs)
            evidence.append(
                EvidenceItem(
                    name="tests",
                    value=f"{len(names)} successful GitHub checks: {', '.join(names)}",
                    source=self._api_url(checks_path),
                )
            )
        return EvidenceCaseCreate(
            case_id=request.case_id,
            objective=request.objective,
            required_evidence=["commit", "tests"],
            evidence=evidence,
        )

    def _get(self, path: str) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "evidenceops-fleet/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = getenv("EVIDENCEOPS_GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with self._opener(Request(self._api_url(path), headers=headers), timeout=10) as response:
                payload = json.load(response)
        except HTTPError as error:
            if error.code == 404:
                raise GitHubEvidenceError("GitHub repository or commit not found", 404) from error
            raise GitHubEvidenceError("GitHub evidence request failed") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise GitHubEvidenceError("GitHub evidence request failed") from error
        if not isinstance(payload, dict):
            raise GitHubEvidenceError("GitHub returned an invalid evidence response")
        return payload

    @staticmethod
    def _api_url(path: str) -> str:
        return f"https://api.github.com{path}"
