import io
import json

from fastapi.testclient import TestClient

from evidenceops_fleet.github_evidence import GitHubEvidenceAdapter
from evidenceops_fleet.main import app, get_github_adapter, get_store
from evidenceops_fleet.models import GitHubOperationCreate
from evidenceops_fleet.store import MemoryResultStore


class JsonResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def github_payload() -> dict:
    return {
        "case_id": "github-release-0001",
        "objective": "Verify the public GitHub commit and CI before release",
        "repository": "example/project",
        "commit_sha": "abcdef1",
    }


def test_adapter_collects_only_successful_source_attributed_checks() -> None:
    responses = iter(
        [
            {"sha": "abcdef1234567890", "html_url": "https://github.com/example/project/commit/abcdef1"},
            {
                "check_runs": [
                    {"name": "tests", "status": "completed", "conclusion": "success"},
                    {"name": "lint", "status": "completed", "conclusion": "success"},
                ]
            },
        ]
    )
    seen_urls: list[str] = []

    def opener(request, timeout):
        seen_urls.append(request.full_url)
        assert timeout == 10
        return JsonResponse(json.dumps(next(responses)).encode())

    evidence = GitHubEvidenceAdapter(opener).collect(
        GitHubOperationCreate.model_validate(github_payload())
    )

    assert [item.name for item in evidence.evidence] == ["commit", "tests"]
    assert evidence.evidence[1].value == "2 successful GitHub checks: lint, tests"
    assert all(url.startswith("https://api.github.com/repos/example/project/") for url in seen_urls)


def test_adapter_fails_closed_when_any_check_is_not_successful() -> None:
    responses = iter(
        [
            {"sha": "abcdef1234567890", "html_url": "https://github.com/example/project/commit/abcdef1"},
            {"check_runs": [{"name": "tests", "status": "completed", "conclusion": "failure"}]},
        ]
    )

    def opener(request, timeout):
        return JsonResponse(json.dumps(next(responses)).encode())

    evidence = GitHubEvidenceAdapter(opener).collect(
        GitHubOperationCreate.model_validate(github_payload())
    )

    assert [item.name for item in evidence.evidence] == ["commit"]


def test_github_integration_enters_the_same_async_operation_contract() -> None:
    class FakeAdapter:
        def collect(self, payload):
            return GitHubEvidenceAdapter(
                lambda request, timeout: JsonResponse(
                    json.dumps(
                        {"sha": "abcdef1234567890", "html_url": "https://github.com/example/project/commit/abcdef1"}
                        if request.full_url.endswith("/commits/abcdef1")
                        else {"check_runs": [{"name": "tests", "status": "completed", "conclusion": "success"}]}
                    ).encode()
                )
            ).collect(payload)

    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    app.dependency_overrides[get_github_adapter] = FakeAdapter
    try:
        response = TestClient(app).post(
            "/integrations/github/operations", json=github_payload()
        )
        fetched = TestClient(app).get(response.headers.get("location", "/operations/operation-github-release-0001"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["operation_id"] == "operation-github-release-0001"
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "ready"
