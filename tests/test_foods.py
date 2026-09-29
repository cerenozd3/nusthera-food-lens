from src.foods import food_names, get_food, load_foods


def test_load_foods_has_at_least_50_rows():
    foods = load_foods()
    assert len(foods) >= 50
    rice = foods["rice, white, cooked"]
    assert rice.kcal_per_100g == 130
    assert rice.protein_g == 2.7
    assert rice.source == "USDA FDC"


def test_food_names_match_csv_keys():
    foods = load_foods()
    names = food_names(foods)
    assert names == list(foods.keys())
    assert "chicken breast, grilled" in names


def test_get_food_is_exact_match_only():
    foods = load_foods()
    assert get_food("rice, white, cooked", foods) is not None
    assert get_food("white rice", foods) is None
    assert get_food("Rice, White, Cooked", foods) is None
