from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app


def food_label_from_analyze(item: dict) -> str:
    """Same rule as index.html foodLabelFromAnalyze: trust /analyze, do not reparse."""
    return "unknown" if item["unknown"] else item["name"]


def test_analyze_json_keeps_exact_rice_name(monkeypatch):
    monkeypatch.setattr("src.main.MOCK_MODE", True)
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("rice.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["unknown"] is False
    assert item["name"] == "rice, white, cooked"
    assert food_label_from_analyze(item) == "rice, white, cooked"
    assert food_label_from_analyze(item) != "unknown"


def test_html_displays_analyze_name_not_catalog_unknown():
    html = Path("src/static/index.html").read_text(encoding="utf-8")
    assert "function foodLabelFromAnalyze(item)" in html
    assert 'return item.unknown ? "unknown" : item.name;' in html
    assert "row.name && row.name !== \"unknown\" ? row.name : \"unknown\"" in html
    assert "setFoodInputValue" in html
    assert "if (next && list.contains(next)) return;" in html
    assert "if (gen !== renderGen) return;" in html
    assert "parse_food_name" not in html
    assert "match_csv_name" not in html
