from fastapi.testclient import TestClient

from src.main import DISCLAIMER, app


def test_home_page_is_html_with_disclaimer_and_estimated_grams():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert DISCLAIMER in html
    assert "Estimated weight" in html
    assert "Calories" in html
    assert "Protein" in html
    assert "Carbs" in html
    assert "Fat" in html
    assert 'type="file"' in html
    assert "/analyze" in html
    assert "/recalculate" in html
    assert "Search food" in html
    assert "suggestFoodNames" in html
    assert "Hazırlama" not in html
    assert ">Renk<" not in html and 'textContent = "Renk"' not in html
    assert "parse_food_name" not in html
    assert "isExactCsvName" in html
    assert "edited" in html
    assert "estimated" in html
    assert "Mod: mock" not in html
    assert "Gemini" not in html
    assert "foods.csv" not in html
    assert "fixture" not in html.lower()
    assert "API anahtarı" not in html
    assert "Not:" not in html
    assert "Güven" not in html


def test_home_page_ui_text_is_english():
    html = TestClient(app).get("/").text
    assert '<html lang="en">' in html
    for turkish in ("Analiz", "Kaydet", "Yemek fotoğrafı", "Günlük", "Toplam", "Yiyecek", "Kalori", "Tahmini", "tahmini", "düzenlendi", "Bilinmeyen"):
        assert turkish not in html
    for english in ("Analyze", "Save", "Clear", "Meal total", "Daily total", "Food"):
        assert english in html


def test_home_page_starts_with_empty_analysis():
    html = TestClient(app).get("/").text
    # Refresh (and bfcache restore) resets the file input and the analysis view.
    assert "function resetPage()" in html
    assert "form.reset();" in html
    assert "event.persisted" in html
    assert '<section id="result" hidden>' in html
    assert '<tbody id="rows"></tbody>' in html


def test_home_page_has_meal_totals_save_and_daily_total():
    html = TestClient(app).get("/").text
    for element_id in ("total-kcal", "total-protein", "total-carbs", "total-fat"):
        assert f'id="{element_id}"' in html
    assert 'id="save"' in html
    assert "Daily total" in html
    assert "/save" in html and "/daily" in html
    # Totals refresh from the server response, which excludes unknown items.
    assert "renderTotals(payload.totals)" in html


def test_home_page_clears_previous_results_for_a_new_file():
    html = TestClient(app).get("/").text
    assert "function clearResults()" in html
    assert 'rowsEl.innerHTML = "";' in html
    # Runs when a new file is chosen and again when analysis starts.
    assert html.count("clearResults();") >= 2
    # Stale analyze/recalculate responses must not repaint cleared results.
    assert html.count("if (gen !== renderGen) return;") >= 3


def test_health_still_reports_mock_mode():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["food_count"] == 55
    assert "mock_mode" in body
