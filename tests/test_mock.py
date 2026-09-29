from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.mock import load_fixture
from src.vision import VisionError


def test_load_fixture_rice_matches_recorded_gemini_json():
    parsed = load_fixture("rice.jpg")
    assert parsed.items[0].name == "rice, white, cooked"
    assert parsed.items[0].grams == 220
    assert parsed.items[0].confidence == 0.95


def test_load_fixture_accepts_plus_in_filename():
    parsed = load_fixture("rice+chicken.jpg")
    names = [item.name for item in parsed.items]
    assert "rice, white, cooked" in names
    assert "chicken breast, grilled" in names
    assert "chickpeas, boiled" in names
    assert "ayran" in names


def test_load_fixture_missing_file_does_not_invent_json():
    with pytest.raises(VisionError, match="was not found"):
        load_fixture("unknown_meal.jpg")


def test_load_fixture_blocks_path_traversal():
    with pytest.raises(VisionError, match="was not found"):
        load_fixture("../../.env")


def test_analyze_mock_mode_reads_fixture_and_calculates_csv_nutrition(monkeypatch):
    monkeypatch.setattr("src.main.MOCK_MODE", True)
    live = MagicMock()
    monkeypatch.setattr("src.main.analyze_image", live)
    client = TestClient(app)
    image_bytes = Path("eval/images/rice.jpg").read_bytes()
    response = client.post(
        "/analyze",
        files={"file": ("rice.jpg", image_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["name"] == "rice, white, cooked"
    assert body["items"][0]["grams"] == 220
    # 220 g × 130 kcal / 100 g from foods.csv, not from Gemini
    assert body["totals"]["kcal"] == 286
    live.assert_not_called()


def test_analyze_rice_chicken_fixture_keeps_exact_csv_names(monkeypatch):
    monkeypatch.setattr("src.main.MOCK_MODE", True)
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("rice+chicken.jpg", b"fake", "image/jpeg")},
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == [
        "rice, white, cooked",
        "chicken breast, grilled",
        "chickpeas, boiled",
        "ayran",
    ]
    assert all(item["unknown"] is False for item in response.json()["items"])


def test_analyze_mock_mode_missing_fixture_returns_user_error(monkeypatch):
    monkeypatch.setattr("src.main.MOCK_MODE", True)
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("not_recorded.jpg", b"fake", "image/jpeg")},
    )
    assert response.status_code == 422
    assert "was not found" in response.json()["detail"]


def test_live_mode_error_does_not_call_load_fixture(monkeypatch):
    monkeypatch.setattr("src.main.MOCK_MODE", False)
    fixture = MagicMock()
    monkeypatch.setattr("src.main.load_fixture", fixture)
    monkeypatch.setattr(
        "src.main.analyze_image",
        MagicMock(side_effect=VisionError("The vision model could not be reached. Check VISION_API_KEY and try again.")),
    )
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("rice.jpg", b"fake", "image/jpeg")},
    )
    assert response.status_code == 422
    assert "could not be reached" in response.json()["detail"]
    fixture.assert_not_called()
