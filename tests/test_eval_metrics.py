import pytest

from src.eval_metrics import (
    LabelError,
    LabelRow,
    explain,
    failed_result,
    labels_outside_table,
    load_labels,
    render_summary_md,
    score_image,
    skipped_result,
    summarize,
    worst_n,
)
from src.foods import load_foods
from src.models import DetectedItem, VisionResponse
from src.nutrition import resolve_meal

FOODS = load_foods()


def meal(*items: tuple[str, float]):
    vision = VisionResponse(
        items=[DetectedItem(name=n, grams=g, confidence=0.9) for n, g in items]
    )
    return resolve_meal(vision, FOODS)


def label(image="a.jpg", items=("rice, white, cooked",), kcal=286.0, grams=None):
    grams = grams if grams is not None else tuple(100.0 for _ in items)
    return LabelRow(image=image, items=tuple(items), true_kcal=kcal, grams=tuple(grams))


def write_labels(tmp_path, text, images=("a.jpg", "b.jpg")):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for name in images:
        (images_dir / name).write_bytes(b"x")
    path = tmp_path / "labels.csv"
    path.write_text(text, encoding="utf-8")
    return path, images_dir


# --- scoring -----------------------------------------------------------------


def test_perfect_match_has_zero_error():
    result = score_image(label(), meal(("rice, white, cooked", 220)))
    assert result.kcal_error == pytest.approx(0.0)
    assert result.missed == () and result.extra == ()
    assert explain(result).startswith("ok")


def test_calorie_error_formula():
    # 100 g rice = 130 kcal; true 200 -> |130-200|/200 = 0.35
    result = score_image(label(kcal=200), meal(("rice, white, cooked", 100)))
    assert result.kcal_error == pytest.approx(0.35)
    assert result.signed_kcal_error == pytest.approx(-0.35)


def test_missed_and_extra_items():
    result = score_image(
        label(items=("rice, white, cooked", "chicken breast, grilled"), kcal=432),
        meal(("rice, white, cooked", 220), ("ayran", 150)),
    )
    assert result.found == ("rice, white, cooked",)
    assert result.missed == ("chicken breast, grilled",)
    assert result.extra == ("ayran",)
    reason = explain(result)
    assert "missed_item: chicken breast, grilled" in reason
    assert "extra_item: ayran" in reason


def test_unknown_name_is_wrong_and_explained():
    result = score_image(label(), meal(("pilav", 200)))
    assert result.found == ()
    assert result.unknown == ("pilav",)
    assert result.predicted_kcal == 0
    assert "unknown_name" in explain(result)


def test_portion_estimate_reason_when_names_are_right():
    result = score_image(label(kcal=286), meal(("rice, white, cooked", 100)))
    reason = explain(result)
    assert reason.startswith("portion_estimate")
    assert "under" in reason


def test_failed_photo_counts_as_full_error_and_no_recognition():
    result = failed_result(label(), "invalid JSON")
    assert result.kcal_error == pytest.approx(1.0)
    assert result.found == ()
    assert explain(result) == "model_error: invalid JSON"


# --- summary -----------------------------------------------------------------


def test_recognition_rate_is_found_over_all_labeled_foods():
    results = [
        score_image(  # 1 of 2 found
            label("a.jpg", ("rice, white, cooked", "chicken breast, grilled"), 432),
            meal(("rice, white, cooked", 220)),
        ),
        score_image(label("b.jpg", ("bread, white",), 212), meal(("bread, white", 80))),
    ]
    summary = summarize(results)
    assert (summary.found_items, summary.labeled_items) == (2, 3)
    assert summary.recognition_rate == pytest.approx(2 / 3)
    assert summary.precision == pytest.approx(1.0)


def test_skipped_photos_are_excluded_from_every_metric():
    scored = score_image(label("a.jpg"), meal(("rice, white, cooked", 220)))
    skipped = skipped_result(label("b.jpg", ("bread, white",), 212), "no fixture")
    summary = summarize([scored, skipped])
    assert summary.n_skipped == 1 and summary.n_scored == 1
    assert summary.labeled_items == 1
    assert summary.recognition_rate == pytest.approx(1.0)
    assert skipped not in worst_n([scored, skipped])


def test_worst_n_orders_by_error_and_limits_to_three():
    results = [
        score_image(label(f"{i}.jpg", kcal=286), meal(("rice, white, cooked", grams)))
        for i, grams in enumerate([220, 100, 50, 10, 200])
    ]
    worst = worst_n(results)
    assert [r.image for r in worst] == ["3.jpg", "2.jpg", "1.jpg"]


def test_summary_with_no_scored_photos_does_not_divide_by_zero():
    summary = summarize([skipped_result(label(), "no fixture")])
    assert summary.recognition_rate is None
    assert summary.mean_kcal_error is None
    assert summary.worst == ()


def test_summary_markdown_contains_metrics_and_worst_section():
    results = [score_image(label(), meal(("rice, white, cooked", 100)))]
    text = render_summary_md(results, summarize(results), "mock", "labels.csv")
    assert "Recognition rate" in text
    assert "Worst 3 photos" in text
    assert "portion_estimate" in text


# --- gram analysis (auxiliary) ------------------------------------------------


def test_gram_error_uses_found_foods_only_and_does_not_change_main_metrics():
    lab = label(
        items=("rice, white, cooked", "chicken breast, grilled"),
        kcal=432,
        grams=(180, 120),
    )
    result = score_image(lab, meal(("rice, white, cooked", 225)))  # chicken missed
    assert result.gram_errors == (("rice, white, cooked", 180, 225, pytest.approx(0.25)),)
    summary = summarize([result])
    assert summary.gram_pairs == 1
    assert summary.mean_gram_error == pytest.approx(0.25)
    # Main metrics are computed from names and kcal only.
    assert summary.recognition_rate == pytest.approx(0.5)
    assert result.kcal_error == pytest.approx(abs(225 * 1.3 - 432) / 432)


def test_gram_summary_is_none_when_nothing_was_found():
    summary = summarize([failed_result(label(), "boom")])
    assert summary.gram_pairs == 0
    assert summary.mean_gram_error is None


def test_summary_markdown_lists_gram_section():
    results = [score_image(label(grams=(200,)), meal(("rice, white, cooked", 220)))]
    text = render_summary_md(results, summarize(results), "mock", "labels.csv")
    assert "Portion accuracy (auxiliary" in text
    assert "| a.jpg | rice, white, cooked | 200 | 220 | 10.0% |" in text


# --- labels.csv --------------------------------------------------------------


def test_load_labels_reads_names_with_commas_and_grams(tmp_path):
    path, images = write_labels(
        tmp_path,
        "image,items,true_kcal\n"
        'a.jpg,"rice, white, cooked:180",234\n'
        'b.jpg,"rice, white, cooked:180; chicken breast, grilled:120",432\n',
    )
    rows = load_labels(path, images)
    assert rows[1].items == ("rice, white, cooked", "chicken breast, grilled")
    assert rows[1].grams == (180.0, 120.0)
    assert rows[1].gram_by_item["chicken breast, grilled"] == 120.0
    assert rows[1].true_kcal == 432


def test_load_labels_reports_all_problems(tmp_path):
    path, images = write_labels(
        tmp_path,
        "image,items,true_kcal\n"
        'a.jpg,"rice, white, cooked",286\n'  # no grams
        "b.jpg,pilav:100,abc\n"  # bad kcal
        "missing.jpg,banana:100,89\n"  # no such file
        "c.jpg,rice,grilled,salad,600\n",  # unquoted commas
        images=("a.jpg", "b.jpg", "c.jpg"),
    )
    with pytest.raises(LabelError) as exc:
        load_labels(path, images)
    text = str(exc.value)
    assert "must be written name:grams" in text
    assert "is not in foods.csv" not in text  # foods.csv membership is not validated
    assert "true_kcal must be a number" in text
    assert "image 'missing.jpg': file not found" in text
    assert "too many columns" in text


@pytest.mark.parametrize("grams", ["0", "-5", "abc", "", "nan", "inf"])
def test_load_labels_rejects_non_positive_or_invalid_grams(tmp_path, grams):
    path, images = write_labels(tmp_path, f"image,items,true_kcal\na.jpg,banana:{grams},89\n")
    with pytest.raises(LabelError, match="grams for 'banana' must be a positive number"):
        load_labels(path, images)


@pytest.mark.parametrize("kcal", ["0", "-10", "nan", "inf", "", "NEEDS_VALUE"])
def test_load_labels_rejects_bad_true_kcal(tmp_path, kcal):
    path, images = write_labels(tmp_path, f"image,items,true_kcal\na.jpg,banana:100,{kcal}\n")
    with pytest.raises(LabelError, match="true_kcal must be"):
        load_labels(path, images)


def test_load_labels_accepts_names_that_are_not_in_foods_csv(tmp_path):
    """labels.csv is ground truth; foods.csv membership is not a validation rule."""
    path, images = write_labels(
        tmp_path,
        "image,items,true_kcal\n"
        "a.jpg,orange juice:200,100\n"
        'b.jpg,"chips:60;banana:100",389\n',
    )
    rows = load_labels(path, images)
    assert rows[0].items == ("orange juice",)
    assert rows[1].items == ("chips", "banana")
    assert rows[1].gram_by_item == {"chips": 60.0, "banana": 100.0}


def test_labels_outside_table_is_a_note_not_an_error(tmp_path):
    path, images = write_labels(
        tmp_path,
        "image,items,true_kcal\n"
        "a.jpg,orange juice:200,100\n"
        'b.jpg,"banana:100;Chips:60",389\n'
        "c.jpg,banana:100,89\n",
        images=("a.jpg", "b.jpg", "c.jpg"),
    )
    outside = labels_outside_table(load_labels(path, images), FOODS)
    assert outside == {"a.jpg": ("orange juice",), "b.jpg": ("Chips",)}


def test_load_labels_rejects_empty_food_name(tmp_path):
    path, images = write_labels(tmp_path, "image,items,true_kcal\na.jpg,:100,89\n")
    with pytest.raises(LabelError, match="empty food name"):
        load_labels(path, images)


def test_load_labels_image_name_must_match_exactly_including_case(tmp_path):
    path, images = write_labels(
        tmp_path, "image,items,true_kcal\nA.JPG,banana:100,89\n", images=("a.jpg",)
    )
    # Path("A.JPG").is_file() is true on macOS; the label must still be rejected.
    with pytest.raises(LabelError, match="does not match the real file name exactly.*'a.jpg'"):
        load_labels(path, images)


def test_load_labels_rejects_unsupported_image_type(tmp_path):
    path, images = write_labels(
        tmp_path, "image,items,true_kcal\nnote.txt,banana:100,89\n", images=("note.txt",)
    )
    with pytest.raises(LabelError, match="unsupported image type"):
        load_labels(path, images)


def test_load_labels_rejects_wrong_header(tmp_path):
    path, images = write_labels(tmp_path, "file,foods,kcal\na.jpg,banana:100,89\n")
    with pytest.raises(LabelError, match="header"):
        load_labels(path, images)


def test_load_labels_enforces_minimum_photo_count(tmp_path):
    path, images = write_labels(tmp_path, "image,items,true_kcal\na.jpg,banana:100,89\n")
    with pytest.raises(LabelError, match="at least 15"):
        load_labels(path, images, min_rows=15)
    assert len(load_labels(path, images, min_rows=1)) == 1


def test_load_labels_rejects_duplicates(tmp_path):
    path, images = write_labels(
        tmp_path,
        "image,items,true_kcal\n"
        "a.jpg,banana:100,89\n"
        "a.jpg,banana:100,89\n"
        'b.jpg,"banana:100;Banana:50",133\n',
    )
    with pytest.raises(LabelError) as exc:
        load_labels(path, images)
    assert "duplicate image" in str(exc.value)
    assert "duplicate item names" in str(exc.value)


def test_load_labels_missing_images_folder_is_reported(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text("image,items,true_kcal\na.jpg,banana:100,89\n", encoding="utf-8")
    with pytest.raises(LabelError, match="images folder not found"):
        load_labels(path, tmp_path / "nope")


# --- ground truth vs prediction ----------------------------------------------


def test_recognition_matches_labeled_name_even_when_not_in_foods_csv():
    """Model reports the labeled food as free text: recognized, but foods.csv cannot price it."""
    lab = label(items=("orange juice",), kcal=100, grams=(200,))
    result = score_image(lab, meal(("orange juice", 200)), FOODS)
    assert result.found == ("orange juice",)
    assert result.unknown == ("orange juice",)
    assert result.predicted_kcal == 0
    assert result.kcal_error == pytest.approx(1.0)
    assert "recognized_but_not_in_foods_csv" in explain(result)
    summary = summarize([result])
    assert summary.recognition_rate == pytest.approx(1.0)
    assert summary.outside_table_items == 1


def test_labeled_food_outside_table_is_missed_when_model_picks_another_name():
    lab = label(items=("yogurt",), kcal=149, grams=(250,))
    result = score_image(lab, meal(("yogurt, plain", 250)), FOODS)
    assert result.missed == ("yogurt",)
    assert result.extra == ("yogurt, plain",)
    assert result.predicted_kcal == pytest.approx(152.5)  # priced from foods.csv
    reason = explain(result)
    assert "missed_item: yogurt" in reason
    assert "label_not_in_foods_csv" in reason


def test_name_comparison_ignores_case_and_spacing_only():
    lab = label(items=("Banana", "chicken  breast, grilled"), kcal=254, grams=(100, 100))
    result = score_image(lab, meal(("banana", 100), ("chicken breast, grilled", 100)), FOODS)
    assert result.found == ("Banana", "chicken  breast, grilled")
    assert result.missed == () and result.extra == ()
    assert result.gram_errors[0][:3] == ("Banana", 100, 100)


def test_calorie_error_compares_prediction_with_labels_true_kcal_not_the_table():
    # True kcal (196) differs from the table (312 per 100 g); the label still wins.
    lab = label(items=("french fries",), kcal=196, grams=(100,))
    result = score_image(lab, meal(("french fries", 100)), FOODS)
    assert result.predicted_kcal == pytest.approx(312)
    assert result.kcal_error == pytest.approx(abs(312 - 196) / 196)
