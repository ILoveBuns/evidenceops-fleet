import struct
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCREENSHOTS = ROOT / "assets" / "screenshots"


def png_size(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()[:24]
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert raw[12:16] == b"IHDR"
    return struct.unpack(">II", raw[16:24])


def test_submission_screenshots_are_high_resolution_pngs() -> None:
    expected = {
        "evidenceops-ready.png",
        "evidenceops-approved.png",
        "evidenceops-missing.png",
        "evidenceops-conflict.png",
    }
    assert {path.name for path in SCREENSHOTS.glob("*.png")} == expected
    for name in expected:
        width, height = png_size(SCREENSHOTS / name)
        assert width >= 1200
        assert height >= 1000


def test_media_guide_names_every_asset_and_discloses_synthetic_scope() -> None:
    guide = (ROOT / "MEDIA.md").read_text()
    normalized = " ".join(guide.split())
    for path in SCREENSHOTS.glob("*.png"):
        assert str(path.relative_to(ROOT)) in guide
    assert "synthetic fixtures" in guide
    assert "do not prove Cloud Run, Firestore, or live Gemini execution" in normalized
