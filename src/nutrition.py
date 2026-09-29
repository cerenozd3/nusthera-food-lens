from pydantic import BaseModel, Field

from .foods import FoodRow, get_food
from .models import DetectedItem, VisionResponse


class Nutrition(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class ResolvedItem(BaseModel):
    """Vision item after exact CSV match. Nutrition comes from foods.csv, never the model."""

    name: str
    detected_name: str
    grams: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    unknown: bool
    nutrition: Nutrition | None = None


class ResolvedMeal(BaseModel):
    items: list[ResolvedItem]
    notes: str = ""
    totals: Nutrition


def nutrients_for_grams(row: FoodRow, grams: float) -> Nutrition:
    # Assignment formula: amount = grams × per-100g value ÷ 100
    return Nutrition(
        kcal=row.kcal_per_100g * grams / 100,
        protein_g=row.protein_g * grams / 100,
        carbs_g=row.carbs_g * grams / 100,
        fat_g=row.fat_g * grams / 100,
    )


def resolve_item(item: DetectedItem, foods: dict[str, FoodRow]) -> ResolvedItem:
    row = get_food(item.name, foods)
    if row is None:
        return ResolvedItem(
            name="unknown",
            detected_name=item.name,
            grams=item.grams,
            confidence=item.confidence,
            unknown=True,
            nutrition=None,
        )
    return ResolvedItem(
        name=row.name,
        detected_name=item.name,
        grams=item.grams,
        confidence=item.confidence,
        unknown=False,
        nutrition=nutrients_for_grams(row, item.grams),
    )


def _add_nutrition(left: Nutrition, right: Nutrition) -> Nutrition:
    return Nutrition(
        kcal=left.kcal + right.kcal,
        protein_g=left.protein_g + right.protein_g,
        carbs_g=left.carbs_g + right.carbs_g,
        fat_g=left.fat_g + right.fat_g,
    )


def meal_totals(items: list[ResolvedItem]) -> Nutrition:
    totals = Nutrition(kcal=0, protein_g=0, carbs_g=0, fat_g=0)
    for item in items:
        if item.unknown or item.nutrition is None:
            continue
        totals = _add_nutrition(totals, item.nutrition)
    return totals


def resolve_meal(vision: VisionResponse, foods: dict[str, FoodRow]) -> ResolvedMeal:
    items = [resolve_item(item, foods) for item in vision.items]
    return ResolvedMeal(items=items, notes=vision.notes, totals=meal_totals(items))
