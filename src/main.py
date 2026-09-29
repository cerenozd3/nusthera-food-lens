from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import DB_PATH, MAX_UPLOAD_MB, MOCK_MODE
from .foods import food_names, load_foods
from .mock import load_fixture
from .models import DetectedItem, VisionResponse
from .nutrition import resolve_meal
from .storage import daily_totals, save_items
from .vision import VisionError, analyze_image

app = FastAPI(title="Nusthera Food Lens")

# Fail fast if the reference table is missing or unreadable.
FOODS = load_foods()
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
INDEX_HTML = Path(__file__).resolve().parent / "static" / "index.html"
DISCLAIMER = (
    "Values are estimates only; not medical or dietary advice; allergens cannot be detected."
)


class RecalculateRequest(BaseModel):
    """User edits. Nutrition is recalculated from foods.csv; the vision model is not called."""

    items: list[DetectedItem]


@app.get("/")
def index():
    return FileResponse(INDEX_HTML)


@app.get("/health")
def health():
    return {
        "message": "Food Lens API is running",
        "food_count": len(FOODS),
        "mock_mode": MOCK_MODE,
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Please upload a JPEG, PNG, or WebP image.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    max_bytes = int(MAX_UPLOAD_MB * 1024 * 1024)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Image is larger than {MAX_UPLOAD_MB:g} MB.",
        )

    filename = file.filename or "uploaded.jpg"
    if MOCK_MODE:
        try:
            vision = load_fixture(filename)
        except VisionError as exc:
            raise HTTPException(status_code=422, detail=exc.message) from exc
    else:
        try:
            vision = analyze_image(data, content_type, food_names(FOODS))
        except VisionError as exc:
            raise HTTPException(status_code=422, detail=exc.message) from exc

    return resolve_meal(vision, FOODS)


@app.get("/foods")
def list_food_names():
    return {"names": food_names(FOODS)}


@app.post("/recalculate")
def recalculate(body: RecalculateRequest):
    return resolve_meal(VisionResponse(items=body.items, notes=""), FOODS)


@app.post("/save")
def save(body: RecalculateRequest):
    """Save corrected items. Nutrition is recomputed from foods.csv, never taken from the client."""
    meal = resolve_meal(VisionResponse(items=body.items, notes=""), FOODS)
    if not meal.items:
        raise HTTPException(status_code=422, detail="There are no items to save.")
    if any(item.unknown for item in meal.items):
        raise HTTPException(status_code=422, detail="Unknown foods cannot be saved.")
    saved = save_items(DB_PATH, meal.items)
    return {"saved": saved, "daily": daily_totals(DB_PATH, date.today())}


@app.get("/daily")
def daily(day: date | None = None):
    day = day or date.today()
    return {"date": day.isoformat(), "totals": daily_totals(DB_PATH, day)}
