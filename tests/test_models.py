import pytest
from pydantic import ValidationError

from src.models import VisionResponse


def test_valid_vision_response():
    parsed = VisionResponse.model_validate(
        {
            "items": [
                {
                    "name": "rice, white, cooked",
                    "grams": 180,
                    "confidence": 0.86,
                }
            ],
            "notes": "sauce not visible clearly",
        }
    )
    assert len(parsed.items) == 1
    assert parsed.items[0].name == "rice, white, cooked"
    assert parsed.notes == "sauce not visible clearly"


def test_empty_items_is_valid_schema():
    parsed = VisionResponse.model_validate({"items": [], "notes": "nothing detected"})
    assert parsed.items == []


def test_missing_items_is_invalid():
    with pytest.raises(ValidationError):
        VisionResponse.model_validate({"notes": "no items key"})


def test_invalid_item_fields():
    with pytest.raises(ValidationError):
        VisionResponse.model_validate(
            {
                "items": [{"name": "rice, white, cooked", "grams": 0, "confidence": 0.5}],
                "notes": "",
            }
        )
    with pytest.raises(ValidationError):
        VisionResponse.model_validate(
            {
                "items": [{"name": "rice, white, cooked", "grams": 100, "confidence": 1.2}],
                "notes": "",
            }
        )
    with pytest.raises(ValidationError):
        VisionResponse.model_validate(
            {
                "items": [{"name": "", "grams": 100, "confidence": 0.5}],
                "notes": "",
            }
        )
