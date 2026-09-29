from eval import run_eval
from src.eval_metrics import LabelRow, STATUS_FAILED, STATUS_OK, STATUS_SKIPPED
from src.foods import load_foods

FOODS = load_foods()
IMAGES = run_eval.config.EVAL_IMAGES_DIR


def test_mock_uses_fixture_and_no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("live vision must not run in --mock")

    monkeypatch.setattr(run_eval, "analyze_image", boom)
    label = LabelRow("rice.jpg", ("rice, white, cooked",), 286.0)
    result = run_eval.evaluate_label(label, FOODS, IMAGES, mock=True)
    assert result.status == STATUS_OK
    assert result.predicted_kcal == 286.0  # 220 g x 130 / 100


def test_mock_without_fixture_is_skipped_not_invented():
    label = LabelRow("no-such-photo.jpg", ("banana",), 89.0)
    result = run_eval.evaluate_label(label, FOODS, IMAGES, mock=True)
    assert result.status == STATUS_SKIPPED
    assert result.predicted_kcal is None


def test_live_vision_error_becomes_failed_result_without_crashing(monkeypatch, tmp_path):
    (tmp_path / "x.jpg").write_bytes(b"not really a jpeg")

    def fail(*args, **kwargs):
        raise run_eval.VisionError("quota exceeded")

    monkeypatch.setattr(run_eval, "analyze_image", fail)
    label = LabelRow("x.jpg", ("banana",), 89.0)
    result = run_eval.evaluate_label(label, FOODS, tmp_path, mock=False)
    assert result.status == STATUS_FAILED
    assert "quota exceeded" in result.detail


def test_main_mock_writes_summary(tmp_path):
    out = tmp_path / "summary.md"
    code = run_eval.main(
        [
            "--mock",
            "--labels", str(run_eval.EVAL_DIR / "labels.smoke.csv"),
            "--min-photos", "3",
            "--output", str(out),
        ]
    )
    assert code == 0
    assert "Recognition rate" in out.read_text(encoding="utf-8")


def test_main_rejects_bad_labels_with_exit_code_2(tmp_path, capsys):
    bad = tmp_path / "labels.csv"
    bad.write_text("image,items,true_kcal\nrice.jpg,pilav,100\n", encoding="utf-8")
    code = run_eval.main(["--mock", "--labels", str(bad), "--min-photos", "1"])
    assert code == 2
    assert "must be written name:grams" in capsys.readouterr().err


def test_validate_only_accepts_labels_outside_foods_csv_and_reports_them(tmp_path, capsys):
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "image,items,true_kcal\nrice.jpg,orange juice:200,100\n", encoding="utf-8"
    )
    code = run_eval.main(["--validate-only", "--labels", str(labels), "--min-photos", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert "is valid: 1 labeled photos" in out
    assert "rice.jpg: orange juice" in out


def test_validate_only_checks_labels_without_vision_or_api_key(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise AssertionError("validate-only must not call vision")

    monkeypatch.setattr(run_eval, "analyze_image", boom)
    monkeypatch.setattr(run_eval.config, "VISION_API_KEY", "")
    code = run_eval.main(
        ["--validate-only", "--labels", str(run_eval.EVAL_DIR / "labels.smoke.csv"), "--min-photos", "3"]
    )
    assert code == 0
    assert "is valid: 3 labeled photos" in capsys.readouterr().out


def test_validate_only_fails_below_photo_minimum(capsys):
    code = run_eval.main(
        ["--validate-only", "--labels", str(run_eval.EVAL_DIR / "labels.smoke.csv")]
    )
    assert code == 2
    assert "at least 15" in capsys.readouterr().err


def test_smoke_labels_carry_reference_grams():
    label = run_eval.load_labels(
        run_eval.EVAL_DIR / "labels.smoke.csv", IMAGES, min_rows=3
    )[1]
    assert label.gram_by_item == {"rice, white, cooked": 180.0, "chicken breast, grilled": 120.0}
