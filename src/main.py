from fastapi import FastAPI

from .foods import load_foods

app = FastAPI(title="Nusthera Food Lens")

# Fail fast if the reference table is missing or unreadable.
FOODS = load_foods()


@app.get("/")
def read_root():
    return {
        "message": "Food Lens API is running",
        "food_count": len(FOODS),
    }
