import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from .nutrition import Nutrition, ResolvedItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saved_date TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    food TEXT NOT NULL,
    grams REAL NOT NULL,
    kcal REAL NOT NULL,
    protein_g REAL NOT NULL,
    carbs_g REAL NOT NULL,
    fat_g REAL NOT NULL
)
"""


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    return conn


def save_items(path: Path, items: list[ResolvedItem], now: datetime | None = None) -> int:
    """Store resolved items. Unknown items are never stored."""
    if any(item.unknown or item.nutrition is None for item in items):
        raise ValueError("Unknown items cannot be saved.")
    now = now or datetime.now()
    rows = [
        (
            now.date().isoformat(),
            now.isoformat(timespec="seconds"),
            item.name,
            item.grams,
            item.nutrition.kcal,
            item.nutrition.protein_g,
            item.nutrition.carbs_g,
            item.nutrition.fat_g,
        )
        for item in items
    ]
    with closing(_connect(path)) as conn, conn:
        conn.executemany(
            "INSERT INTO entries (saved_date, saved_at, food, grams, kcal, protein_g, carbs_g, fat_g)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def daily_totals(path: Path, day: date, since: datetime | None = None) -> Nutrition:
    """Sum entries saved on `day`; with `since`, only those saved at/after that moment."""
    query = (
        "SELECT COALESCE(SUM(kcal), 0), COALESCE(SUM(protein_g), 0),"
        " COALESCE(SUM(carbs_g), 0), COALESCE(SUM(fat_g), 0)"
        " FROM entries WHERE saved_date = ?"
    )
    params: list[str] = [day.isoformat()]
    if since is not None:
        query += " AND saved_at >= ?"
        params.append(since.isoformat(timespec="seconds"))
    with closing(_connect(path)) as conn:
        kcal, protein, carbs, fat = conn.execute(query, params).fetchone()
    return Nutrition(kcal=kcal, protein_g=protein, carbs_g=carbs, fat_g=fat)
