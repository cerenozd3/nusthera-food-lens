import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import VisionResponse
from src import vision
from src.vision import (
    VisionError,
    analyze_image,
    build_prompt,
    parse_vision_json,
    strip_json_fences,
)

VALID_PAYLOAD = {
    "items": [
        {"name": "rice, white, cooked", "grams": 180, "confidence": 0.86},
    ],
    "notes": "sauce not visible clearly",
}
VALID_JSON = json.dumps(VALID_PAYLOAD)


def test_prompt_includes_csv_names_grams_and_confidence_range():
    prompt = build_prompt(["rice, white, cooked", "egg, boiled"])
    assert "- rice, white, cooked" in prompt
    assert "- egg, boiled" in prompt
    assert "grams" in prompt
    assert "confidence" in prompt
    assert "0.0" in prompt and "1.0" in prompt
    assert "Do not return calories" in prompt


def test_strip_json_fences_unwraps_markdown_block():
    wrapped = "```json\n" + VALID_JSON + "\n```"
    assert json.loads(strip_json_fences(wrapped)) == VALID_PAYLOAD


def test_parse_vision_json_uses_existing_models():
    parsed = parse_vision_json("```JSON\n" + VALID_JSON + "\n```")
    assert isinstance(parsed, VisionResponse)
    assert parsed.items[0].name == "rice, white, cooked"
    assert parsed.items[0].grams == 180
    assert parsed.items[0].confidence == 0.86


def test_parse_invalid_json_raises_vision_error():
    with pytest.raises(VisionError, match="invalid JSON"):
        parse_vision_json("not json at all")


def test_parse_wrong_schema_raises_vision_error():
    with pytest.raises(VisionError, match="items/notes"):
        parse_vision_json(json.dumps({"foods": [], "notes": ""}))


def test_invalid_json_retries_once_then_succeeds(monkeypatch):
    monkeypatch.setattr(vision, "VISION_API_KEY", "test-key")
    mock_gen = MagicMock(side_effect=["not-json", VALID_JSON])
    monkeypatch.setattr(vision, "_generate_content", mock_gen)
    parsed = analyze_image(b"img", "image/jpeg", ["rice, white, cooked"])
    assert parsed.items[0].name == "rice, white, cooked"
    assert mock_gen.call_count == 2


def test_empty_items_retries_then_fails(monkeypatch):
    monkeypatch.setattr(vision, "VISION_API_KEY", "test-key")
    empty = json.dumps({"items": [], "notes": "nothing"})
    mock_gen = MagicMock(side_effect=[empty, empty])
    monkeypatch.setattr(vision, "_generate_content", mock_gen)
    with pytest.raises(VisionError, match="No foods were detected"):
        analyze_image(b"img", "image/jpeg", ["rice, white, cooked"])
    assert mock_gen.call_count == 2


def test_empty_items_then_valid_does_not_need_a_third_call(monkeypatch):
    monkeypatch.setattr(vision, "VISION_API_KEY", "test-key")
    empty = json.dumps({"items": [], "notes": "nothing"})
    mock_gen = MagicMock(side_effect=[empty, VALID_JSON])
    monkeypatch.setattr(vision, "_generate_content", mock_gen)
    parsed = analyze_image(b"img", "image/jpeg", ["rice, white, cooked"])
    assert parsed.notes == "sauce not visible clearly"
    assert mock_gen.call_count == 2


def test_live_api_error_retries_then_raises_without_mock_fallback(monkeypatch):
    monkeypatch.setattr(vision, "VISION_API_KEY", "test-key")
    mock_gen = MagicMock(side_effect=RuntimeError("quota"))
    monkeypatch.setattr(vision, "_generate_content", mock_gen)
    with pytest.raises(VisionError, match="could not be reached"):
        analyze_image(b"img", "image/jpeg", ["rice, white, cooked"])
    assert mock_gen.call_count == 2
    source = open("src/vision.py", encoding="utf-8").read()
    assert "FIXTURES_DIR" not in source
    assert "MOCK_MODE" not in source
    assert not hasattr(vision, "load_fixture")


def test_missing_api_key_does_not_call_gemini(monkeypatch):
    monkeypatch.setattr(vision, "VISION_API_KEY", "")
    mock_gen = MagicMock()
    monkeypatch.setattr(vision, "_generate_content", mock_gen)
    with pytest.raises(VisionError, match="VISION_API_KEY"):
        analyze_image(b"img", "image/jpeg", ["rice, white, cooked"])
    mock_gen.assert_not_called()


def test_analyze_endpoint_calculates_nutrition_from_csv(monkeypatch):
    parsed = VisionResponse.model_validate(VALID_PAYLOAD)
    monkeypatch.setattr("src.main.analyze_image", lambda *args, **kwargs: parsed)
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("meal.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["kcal"] == 234
    assert body["items"][0]["unknown"] is False


def test_analyze_endpoint_returns_user_facing_error(monkeypatch):
    monkeypatch.setattr(
        "src.main.analyze_image",
        MagicMock(side_effect=VisionError("The vision model returned invalid JSON. Please try another photo.")),
    )
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("meal.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 422
    assert "invalid JSON" in response.json()["detail"]
