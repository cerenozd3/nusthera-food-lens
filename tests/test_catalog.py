from src.foods import load_foods, food_names, suggest_food_names


def test_suggest_ri_returns_existing_rice_csv_name():
    names = food_names(load_foods())
    hits = suggest_food_names("ri", names)
    assert "rice, white, cooked" in hits
    assert all(name in names for name in hits)


def test_suggest_does_not_invent_names():
    names = food_names(load_foods())
    hits = suggest_food_names("sushi", names)
    assert hits == []
    assert "brown rice" not in suggest_food_names("rice", names)


def test_suggest_empty_query_is_empty():
    names = food_names(load_foods())
    assert suggest_food_names("  ", names) == []
