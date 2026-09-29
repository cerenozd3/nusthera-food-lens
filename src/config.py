import os
from pathlib import Path

from dotenv import load_dotenv

# Paths are rooted at the repo, not the process cwd, so tests and uvicorn agree.
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

FOODS_CSV_PATH = ROOT_DIR / "data" / "foods.csv"
FIXTURES_DIR = ROOT_DIR / "fixtures"
EVAL_IMAGES_DIR = ROOT_DIR / "eval" / "images"


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


VISION_API_KEY = os.getenv("VISION_API_KEY", "")
# Mock is opt-in only. Live mode never falls back to fixtures (phase 3+).
MOCK_MODE = _as_bool(os.getenv("MOCK_MODE"), default=True)
PORT = int(os.getenv("PORT", "8000"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "8"))
