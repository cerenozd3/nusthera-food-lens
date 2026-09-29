import csv
from pathlib import Path

from pydantic import BaseModel, Field

from .config import FOODS_CSV_PATH


class FoodRow(BaseModel):
    name: str = Field(min_length=1)
    kcal_per_100g: float
    protein_g: float
    carbs_g: float
    fat_g: float
    source: str


def load_foods(path: Path | None = None) -> dict[str, FoodRow]:
    """Load the reference table keyed by exact CSV name (the prompt list)."""
    csv_path = path or FOODS_CSV_PATH
    foods: dict[str, FoodRow] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            food = FoodRow.model_validate(row)
            foods[food.name] = food
    if not foods:
        raise ValueError(f"No foods loaded from {csv_path}")
    return foods


def food_names(foods: dict[str, FoodRow] | None = None) -> list[str]:
    table = foods if foods is not None else load_foods()
    return list(table.keys())


def get_food(name: str, foods: dict[str, FoodRow]) -> FoodRow | None:
    """Exact CSV name only. Callers mark a miss as unknown."""
    return foods.get(name)


def suggest_food_names(query: str, names: list[str], limit: int = 8) -> list[str]:
    """Return existing CSV names that start with or contain query. No invented names."""
    needle = query.strip().lower()
    if not needle:
        return []
    starts = [name for name in names if name.lower().startswith(needle)]
    contains = [
        name for name in names if needle in name.lower() and name not in starts
    ]
    return (starts + contains)[:limit]
