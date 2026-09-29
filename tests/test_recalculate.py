import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import DetectedItem

INDEX_HTML = Path("src/static/index.html").read_text(encoding="utf-8")


def test_routes_the_editor_calls_are_registered():
    """A stale server without these routes makes every edit fail with 404 'Not Found'."""
    routes = {(route.path, method) for route in app.routes for method in route.methods}
    assert ("/recalculate", "POST") in routes
    assert ("/foods", "GET") in routes


def test_frontend_recalculate_payload_matches_detected_item():
    """The keys index.html POSTs must be exactly the fields DetectedItem requires."""
    body = re.search(
        r"function editorPayload\(\).*?editorRows\.map\(\(row\) => \(\{(.*?)\}\)\)",
        INDEX_HTML,
        re.DOTALL,
    )
    assert body is not None, "could not find editorPayload() in index.html"
    sent_keys = set(re.findall(r"(\w+):", body.group(1)))
    assert sent_keys == set(DetectedItem.model_fields)
    # /recalculate and /save must both send that same payload.
    assert INDEX_HTML.count("JSON.stringify(editorPayload())") == 2


def test_foods_endpoint_lists_csv_names():
    client = TestClient(app)
    response = client.get("/foods")
    assert response.status_code == 200
    names = response.json()["names"]
    assert len(names) >= 50
    assert "bread, white" in names
    assert "unknown" not in names
    assert "catalog" not in response.json()


def test_recalculate_uses_csv_not_gemini(monkeypatch):
    live = MagicMock()
    monkeypatch.setattr("src.main.analyze_image", live)
    client = TestClient(app)
    response = client.post(
        "/recalculate",
        json={
            "items": [
                {"name": "bread, white", "grams": 80, "confidence": 1},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["unknown"] is False
    assert body["items"][0]["nutrition"]["kcal"] == 212
    assert body["items"][0]["nutrition"]["protein_g"] == 7.2
    live.assert_not_called()


def test_recalculate_unknown_has_no_nutrition():
    client = TestClient(app)
    response = client.post(
        "/recalculate",
        json={"items": [{"name": "unknown", "grams": 80, "confidence": 1}]},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["unknown"] is True
    assert item["nutrition"] is None


def test_recalculate_after_name_correction():
    client = TestClient(app)
    response = client.post(
        "/recalculate",
        json={"items": [{"name": "chicken breast, grilled", "grams": 120, "confidence": 1}]},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["nutrition"]["kcal"] == 198


def test_recalculate_grams_change_uses_csv_formula():
    client = TestClient(app)
    response = client.post(
        "/recalculate",
        json={"items": [{"name": "bread, white", "grams": 100, "confidence": 1}]},
    )
    assert response.status_code == 200
    nutrition = response.json()["items"][0]["nutrition"]
    assert nutrition["kcal"] == 265
    assert nutrition["protein_g"] == 9.0
    assert nutrition["carbs_g"] == 49.0
    assert nutrition["fat_g"] == 3.2


@pytest.mark.parametrize(
    "name",
    [
        "rice, white, cooked",
        "chicken breast, grilled",
        "chickpeas, boiled",
        "ayran",
    ],
)
def test_recalculate_keeps_exact_csv_names(name):
    client = TestClient(app)
    response = client.post(
        "/recalculate",
        json={"items": [{"name": name, "grams": 100, "confidence": 1}]},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["unknown"] is False
    assert item["name"] == name
    assert item["nutrition"] is not None
