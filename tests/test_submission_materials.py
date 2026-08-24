from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).parents[1]


def test_async_runtime_is_visible_across_judge_materials() -> None:
    architecture = ROOT / "assets" / "architecture.svg"
    ElementTree.parse(architecture)
    architecture_text = architecture.read_text()
    assert "Cloud Tasks queue" in architecture_text
    assert "Firestore receipts" in architecture_text
    assert "transactional execution lease" in architecture_text
    assert "5 attempts / 15 minutes" in architecture_text
    assert "GitHub CI adapter" in architecture_text

    required_phrases = {
        "README.md": ("Cloud Tasks", "transactional five-minute execution lease"),
        "DEMO_SCRIPT.md": ("shows queued", "five-minute execution lease"),
        "SUBMISSION_DRAFT.md": ("durable operation receipt", "transactional execution lease"),
        "CLOUD_EVIDENCE.md": (
            "Cloud Tasks queue/location",
            "5 attempts",
            "900-second retry window",
            "worker_guard=secret",
            "operation_runtime=cloud-tasks",
            "misconfigured",
            "terminal state",
        ),
        "TRACK_FIT.md": (
            "deterministic per-attempt Cloud Tasks dispatch",
            "failed-attempt recovery",
            "live proof pending",
        ),
    }
    for filename, phrases in required_phrases.items():
        contents = (ROOT / filename).read_text()
        assert all(phrase in contents for phrase in phrases), filename


def test_github_autonomous_evidence_claim_matches_implementation() -> None:
    main = (ROOT / "evidenceops_fleet" / "main.py").read_text()
    adapter = (ROOT / "evidenceops_fleet" / "github_evidence.py").read_text()
    assert '"/integrations/github/operations"' in main
    assert "https://api.github.com" in adapter
    assert "EVIDENCEOPS_GITHUB_TOKEN" in adapter
    verifier = (ROOT / "scripts" / "verify_public_deployment.py").read_text()
    assert '"GitHub autonomous evidence"' in verifier
    assert '"--github-repository"' in verifier
    assert '"--github-commit"' in verifier
    assert "--github-repository ILoveBuns/evidenceops-fleet" in (
        ROOT / "DEMO_SCRIPT.md"
    ).read_text()
    for filename in ("README.md", "SUBMISSION_DRAFT.md", "TRACK_FIT.md"):
        assert "GitHub" in (ROOT / filename).read_text(), filename


def test_governed_agent_catalog_claim_matches_schema_and_api() -> None:
    models = (ROOT / "evidenceops_fleet" / "models.py").read_text()
    main = (ROOT / "evidenceops_fleet" / "main.py").read_text()
    for field in (
        "owner_department",
        "approved_consumers",
        "data_classifications",
        "allowed_regions",
    ):
        assert field in models
    assert "department:" in main
    assert "capability:" in main
    assert '"/workflow"' in main
    for filename in ("README.md", "SUBMISSION_DRAFT.md", "TRACK_FIT.md"):
        assert "cross-department" in (ROOT / filename).read_text(), filename


def test_cross_session_memory_claim_matches_schema_and_api() -> None:
    models = (ROOT / "evidenceops_fleet" / "models.py").read_text()
    main = (ROOT / "evidenceops_fleet" / "main.py").read_text()
    assert "class CaseMemorySnapshot" in models
    assert '"/cases/{case_id}/memory"' in main
    assert "raw_evidence_included" in models
    for filename in ("README.md", "SUBMISSION_DRAFT.md", "TRACK_FIT.md"):
        contents = (ROOT / filename).read_text()
        assert "cross-session" in contents, filename
        assert "TTL" in contents, filename


def test_submission_audit_is_documented() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "scripts/audit_submission_readiness.py" in readme
    assert "submission-readiness.json" in readme
    assert "scripts/preflight_google_cloud.py" in readme
    assert "cloud-preflight.json" in readme


def test_weighted_judging_scorecard_maps_evidence_and_risk() -> None:
    scorecard = (ROOT / "JUDGING_SCORECARD.md").read_text()
    for criterion in (
        "Innovation & Operational Utility (40%)",
        "Architectural Discipline & Tech Stack (30%)",
        "Demo & Production Readiness (30%)",
    ):
        assert criterion in scorecard
    assert scorecard.count("Evidence location") == 3
    assert scorecard.count("Remaining risk") == 3
    assert "synthetic examples as customer use" in scorecard
    assert "Cloud evidence remains pending" in scorecard


def test_optional_contribution_drafts_are_truthful_and_rule_aligned() -> None:
    drafts = (ROOT / "BONUS_DRAFTS.md").read_text()
    assert "I created this article for the purpose of entering" in drafts
    assert "#AllThingsAgenticHackathon" in drafts
    assert "ADD_PUBLIC_BUILD_STORY_URL" in drafts
    assert "ADD_PUBLIC_SOCIAL_POST_URL" in drafts
    assert "not customer, revenue, or production evidence" in drafts


def test_demo_requires_public_video_visibility() -> None:
    demo = (ROOT / "DEMO_SCRIPT.md").read_text()
    assert "Video is public, not unlisted" in demo
    assert "public or unlisted" not in demo


def test_submission_leads_with_specific_competitive_wedge() -> None:
    submission = (ROOT / "SUBMISSION_DRAFT.md").read_text()
    readme = (ROOT / "README.md").read_text()
    demo = (ROOT / "DEMO_SCRIPT.md").read_text()
    for contents in (submission, readme, demo):
        assert "GitHub" in contents
        assert "approval" in contents
        assert "deterministic" in contents
    assert "No operator copies check text" in submission
    assert "tiny release" in submission
