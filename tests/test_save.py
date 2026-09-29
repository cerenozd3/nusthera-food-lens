import sqlite3
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from src.foods import load_foods
from src.main import app
from src.nutrition import resolve_item
from src.models import DetectedItem
from src.storage import daily_totals, save_items


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr("src.main.DB_PATH", path)
    return path


def rows(path):
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT saved_date, food, grams, kcal, protein_g, carbs_g, fat_g FROM entries ORDER BY id"
        ).fetchall()


def test_save_stores_date_food_grams_and_nutrition(db):
    client = TestClient(app)
    response = client.post(
        "/save",
        json={"items": [{"name": "bread, white", "grams": 80, "confidence": 1}]},
    )
    assert response.status_code == 200
    assert response.json()["saved"] == 1
    assert rows(db) == [(date.today().isoformat(), "bread, white", 80.0, 212.0, 7.2, 39.2, 2.56)]


def test_save_nutrition_comes_from_csv_not_client(db):
    client = TestClient(app)
    client.post(
        "/save",
        json={"items": [{"name": "ayran", "grams": 200, "confidence": 1, "kcal": 99999}]},
    )
    assert rows(db)[0][3] == 72.0  # 36 kcal/100g * 200g


def test_save_rejects_unknown_and_stores_nothing(db):
    client = TestClient(app)
    response = client.post(
        "/save",
        json={
            "items": [
                {"name": "ayran", "grams": 200, "confidence": 1},
                {"name": "unknown", "grams": 50, "confidence": 1},
            ]
        },
    )
    assert response.status_code == 422
    assert not db.exists() or rows(db) == []


def test_save_rejects_empty_items(db):
    response = TestClient(app).post("/save", json={"items": []})
    assert response.status_code == 422


def test_save_items_refuses_unknown_directly(tmp_path):
    foods = load_foods()
    item = resolve_item(DetectedItem(name="sushi", grams=10, confidence=1), foods)
    with pytest.raises(ValueError):
        save_items(tmp_path / "x.db", [item])


def test_daily_total_sums_today_and_ignores_other_days(db):
    foods = load_foods()
    rice = resolve_item(DetectedItem(name="rice, white, cooked", grams=100, confidence=1), foods)
    ayran = resolve_item(DetectedItem(name="ayran", grams=100, confidence=1), foods)
    yesterday = datetime.now() - timedelta(days=1)
    save_items(db, [rice], now=yesterday)

    client = TestClient(app)
    assert client.get("/daily").json()["totals"]["kcal"] == 0

    client.post("/save", json={"items": [{"name": "rice, white, cooked", "grams": 200, "confidence": 1}]})
    response = client.post("/save", json={"items": [{"name": "ayran", "grams": 100, "confidence": 1}]})
    assert response.json()["daily"]["kcal"] == pytest.approx(260 + 36)

    totals = client.get("/daily").json()["totals"]
    assert totals["kcal"] == pytest.approx(296)
    assert totals["protein_g"] == pytest.approx(5.4 + 1.8)
    assert totals["carbs_g"] == pytest.approx(56.4 + 2.6)
    assert totals["fat_g"] == pytest.approx(0.6 + 2.0)

    # Storage keeps other days intact; they just don't count toward today.
    assert daily_totals(db, yesterday.date()).kcal == pytest.approx(130)
    assert daily_totals(db, date.today()).kcal == pytest.approx(296)
    assert ayran.nutrition.kcal == 36


def test_daily_total_keeps_todays_meals_across_server_restart(db):
    foods = load_foods()
    rice = resolve_item(DetectedItem(name="rice, white, cooked", grams=100, confidence=1), foods)
    ayran = resolve_item(DetectedItem(name="ayran", grams=100, confidence=1), foods)
    midnight = datetime.combine(date.today(), time(0, 0, 1))

    save_items(db, [rice], now=midnight)  # saved earlier today, before this server process
    client = TestClient(app)
    assert client.get("/daily").json()["totals"]["kcal"] == pytest.approx(130)

    save_items(db, [ayran], now=midnight + timedelta(minutes=2))
    assert client.get("/daily").json()["totals"]["kcal"] == pytest.approx(166)
    assert len(rows(db)) == 2


def test_meal_totals_exclude_unknown_via_recalculate():
    response = TestClient(app).post(
        "/recalculate",
        json={
            "items": [
                {"name": "ayran", "grams": 100, "confidence": 1},
                {"name": "unknown", "grams": 500, "confidence": 1},
            ]
        },
    )
    assert response.json()["totals"]["kcal"] == 36
