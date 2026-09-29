from fastapi import FastAPI, File, HTTPException, UploadFile

from .config import MAX_UPLOAD_MB, MOCK_MODE
from .foods import food_names, load_foods
from .mock import load_fixture
from .nutrition import resolve_meal
from .vision import VisionError, analyze_image

app = FastAPI(title="Nusthera Food Lens")

# Fail fast if the reference table is missing or unreadable.
FOODS = load_foods()
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.get("/")
def read_root():
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
