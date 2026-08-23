from evidenceops_fleet.models import EvidenceCaseCreate
from evidenceops_fleet.policy import canonical_digest, inspect_evidence


def payload(evidence):
    return EvidenceCaseCreate(
        case_id="case-0001",
        objective="Verify a release evidence package",
        required_evidence=["commit", "tests"],
        evidence=evidence,
    )


def test_policy_finds_missing_and_conflicting_evidence() -> None:
    case = payload(
        [
            {"name": "commit", "value": "abc", "source": "https://example.test/a"},
            {"name": "commit", "value": "def", "source": "https://example.test/b"},
        ]
    )
    assert inspect_evidence(case) == (["tests"], ["commit"])


def test_digest_is_independent_of_evidence_order() -> None:
    items = [
        {"name": "commit", "value": "abc", "source": "https://example.test/a"},
        {"name": "tests", "value": "17 passed", "source": "https://example.test/b"},
    ]
    assert canonical_digest(payload(items)) == canonical_digest(payload(list(reversed(items))))

