import pytest

from src.foods import load_foods
from src.models import DetectedItem, VisionResponse
from src.nutrition import nutrients_for_grams, resolve_item, resolve_meal


def test_nutrients_use_csv_formula():
    foods = load_foods()
    rice = foods["rice, white, cooked"]
    nutrition = nutrients_for_grams(rice, 180)
    assert nutrition.kcal == 234
    assert nutrition.protein_g == pytest.approx(4.86)
    assert nutrition.carbs_g == pytest.approx(50.76)
    assert nutrition.fat_g == pytest.approx(0.54)


def test_pdf_example_meal_totals_432_kcal():
    foods = load_foods()
    vision = VisionResponse.model_validate(
        {
            "items": [
                {"name": "rice, white, cooked", "grams": 180, "confidence": 0.86},
                {"name": "chicken breast, grilled", "grams": 120, "confidence": 0.74},
            ],
            "notes": "",
        }
    )
    meal = resolve_meal(vision, foods)
    assert meal.totals.kcal == 432
    assert meal.totals.protein_g == pytest.approx(4.86 + 37.2)
    assert all(not item.unknown for item in meal.items)


def test_unmatched_name_is_unknown_and_excluded_from_totals():
    foods = load_foods()
    item = DetectedItem(name="white rice", grams=180, confidence=0.9)
    resolved = resolve_item(item, foods)
    assert resolved.unknown is True
    assert resolved.name == "unknown"
    assert resolved.detected_name == "white rice"
    assert resolved.nutrition is None

    vision = VisionResponse(
        items=[
            DetectedItem(name="white rice", grams=180, confidence=0.9),
            DetectedItem(name="chicken breast, grilled", grams=120, confidence=0.74),
        ],
        notes="",
    )
    meal = resolve_meal(vision, foods)
    assert meal.items[0].unknown is True
    assert meal.items[1].unknown is False
    assert meal.totals.kcal == 198


def test_empty_items_yield_zero_totals():
    foods = load_foods()
    meal = resolve_meal(VisionResponse(items=[], notes="nothing detected"), foods)
    assert meal.items == []
    assert meal.totals.kcal == 0
    assert meal.totals.protein_g == 0
