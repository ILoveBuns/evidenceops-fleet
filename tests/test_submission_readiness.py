from pathlib import Path

from scripts.audit_submission_readiness import audit


ROOT = Path(__file__).parents[1]


def test_current_submission_audit_identifies_only_real_external_gates() -> None:
    receipt = audit(ROOT)
    checks = {item["name"]: item for item in receipt["checks"]}

    assert checks["required files"]["passed"] is True
    assert checks["public repository"]["passed"] is True
    assert checks["spin-up instructions"]["passed"] is True
    assert checks["required Google stack"]["passed"] is True
    assert checks["architecture diagram"]["passed"] is True
    assert checks["four-minute demo plan"]["passed"] is True
    assert checks["judging scorecard"]["passed"] is True
    assert checks["public demo video"]["passed"] is False
    assert checks["observed Google Cloud evidence"]["passed"] is False
    assert checks["clean published source"]["passed"] is False
    assert receipt["passed"] is False
    assert receipt["bonus_points_ready"] == 0
    bonus_checks = {item["name"]: item for item in receipt["bonus_checks"]}
    assert bonus_checks["public build story"]["passed"] is False
    assert bonus_checks["public social post"]["passed"] is False
    assert bonus_checks["additional Google AI model"]["passed"] is False


def test_readiness_receipt_has_stable_check_names() -> None:
    receipt = audit(ROOT)
    assert [item["name"] for item in receipt["checks"]] == [
        "required files",
        "public repository",
        "spin-up instructions",
        "required Google stack",
        "architecture diagram",
        "four-minute demo plan",
        "judging scorecard",
        "public demo video",
        "observed Google Cloud evidence",
        "clean published source",
    ]
    assert [item["name"] for item in receipt["bonus_checks"]] == [
        "public build story",
        "public social post",
        "additional Google AI model",
    ]
