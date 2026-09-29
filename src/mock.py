from pathlib import Path

from .config import FIXTURES_DIR
from .vision import VisionError, parse_vision_json


def load_fixture(filename: str) -> VisionResponse:
    """Load a pre-recorded Gemini response from fixtures/ without network access.

    Guards against path traversal and returns a validated VisionResponse.
    Raises VisionError if the fixture is missing, so fake data is never invented.
    """
    clean_name = Path(filename).name
    stem = Path(clean_name).stem
    candidates = [
        FIXTURES_DIR / f"{stem}.json",
        FIXTURES_DIR / f"{clean_name}.json",
        FIXTURES_DIR / clean_name,
    ]
    target_path: Path | None = None
    for cand in candidates:
        if cand.is_file():
            target_path = cand
            break

    if target_path is None:
        available = sorted([p.stem for p in FIXTURES_DIR.glob("*.json")])
        avail_str = ", ".join(f"'{a}'" for a in available) if available else "none"
        raise VisionError(
            f"Mock fixture for '{clean_name}' was not found. "
            f"Available sample fixtures: {avail_str}."
        )

    try:
        content = target_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VisionError(f"Failed to read mock fixture: {exc}") from exc

    return parse_vision_json(content)
