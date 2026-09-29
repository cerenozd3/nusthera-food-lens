"""Evaluate recognition and calorie error against eval/labels.csv.

Live (needs VISION_API_KEY):   python eval/run_eval.py
Keyless smoke test (fixtures): python eval/run_eval.py --mock

Nutrition is always computed from data/foods.csv by our code, never by the model.
"""

import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src import config  # noqa: E402
from src.eval_metrics import (  # noqa: E402
    ImageResult,
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
)
from src.foods import food_names, load_foods  # noqa: E402
from src.mock import find_fixture, load_fixture  # noqa: E402
from src.nutrition import resolve_meal  # noqa: E402
from src.vision import VisionError, analyze_image  # noqa: E402

EVAL_DIR = ROOT_DIR / "eval"
MIN_PHOTOS = 15
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mock", action="store_true", help="read fixtures/, no API calls")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="check labels.csv against foods.csv and eval/images, then stop (no vision calls)",
    )
    parser.add_argument("--labels", type=Path, default=EVAL_DIR / "labels.csv")
    parser.add_argument("--images-dir", type=Path, default=config.EVAL_IMAGES_DIR)
    parser.add_argument("--output", type=Path, default=EVAL_DIR / "results" / "summary.md")
    parser.add_argument(
        "--min-photos",
        type=int,
        default=MIN_PHOTOS,
        help=f"minimum labeled photos (default {MIN_PHOTOS}; lower it only for smoke tests)",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between live calls")
    return parser.parse_args(argv)


def _mime_type(path: Path) -> str | None:
    mime, _ = mimetypes.guess_type(path.name)
    return mime if mime in ALLOWED_MIME else None


def _save_raw(raw_dir: Path, label: LabelRow, payload: dict) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{Path(label.image).stem}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def evaluate_label(
    label: LabelRow,
    foods: dict,
    images_dir: Path,
    mock: bool,
    raw_dir: Path | None = None,
) -> ImageResult:
    """One photo -> ImageResult. Never raises for a model/fixture problem."""
    try:
        if mock:
            if find_fixture(label.image) is None:
                return skipped_result(label, "no fixture in fixtures/ for this photo")
            vision = load_fixture(label.image)
        else:
            image_path = images_dir / label.image
            mime = _mime_type(image_path)
            if mime is None:
                return failed_result(label, "unsupported image type (use JPEG, PNG or WebP)")
            vision = analyze_image(image_path.read_bytes(), mime, food_names(foods))
            if raw_dir is not None:
                _save_raw(raw_dir, label, vision.model_dump())
    except VisionError as exc:
        return failed_result(label, exc.message)
    except OSError as exc:
        return failed_result(label, f"could not read image: {exc}")
    return score_image(label, resolve_meal(vision, foods), foods)


def print_report(results: list[ImageResult], summary) -> None:
    print(f"{'photo':34} {'status':8} {'true':>6} {'pred':>6} {'error':>7}")
    for r in results:
        err = "-" if r.kcal_error is None else f"{r.kcal_error:.0%}"
        pred = "-" if r.predicted_kcal is None else f"{r.predicted_kcal:.0f}"
        print(f"{r.image[:34]:34} {r.status:8} {r.true_kcal:>6.0f} {pred:>6} {err:>7}")

    def pct(value):
        return "n/a" if value is None else f"{value:.1%}"

    print()
    print(
        f"Recognition rate : {pct(summary.recognition_rate)} "
        f"({summary.found_items}/{summary.labeled_items} labeled foods found)"
    )
    print(f"Precision        : {pct(summary.precision)}")
    print(f"Calorie error    : mean {pct(summary.mean_kcal_error)}, median {pct(summary.median_kcal_error)}")
    print(f"Photos           : {summary.n_scored} scored, {summary.n_failed} failed, {summary.n_skipped} skipped")
    print(
        f"Gram error (aux) : mean {pct(summary.mean_gram_error)}, "
        f"median {pct(summary.median_gram_error)} over {summary.gram_pairs} found foods"
    )
    print("\nWorst 3 by calorie error:")
    for r in summary.worst:
        print(f"  - {r.image}: {r.kcal_error:.0%}  <- {explain(r)}")


def print_outside_table(labels: list[LabelRow], foods: dict) -> None:
    """Labeled foods missing from foods.csv are ground truth, so this is a note, not an error."""
    outside = labels_outside_table(labels, foods)
    if not outside:
        return
    print("\nNote: labeled foods not in foods.csv (recognition still counts them; "
          "their kcal cannot be computed):")
    for image, names in outside.items():
        print(f"  - {image}: {', '.join(names)}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    foods = load_foods()

    try:
        labels = load_labels(args.labels, args.images_dir, min_rows=args.min_photos)
    except (LabelError, OSError) as exc:
        print(f"Cannot use {args.labels}:", file=sys.stderr)
        print(f"  {exc}".replace("\n", "\n  "), file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"{args.labels.name} is valid: {len(labels)} labeled photos (minimum {args.min_photos}).")
        print_outside_table(labels, foods)
        return 0

    if not args.mock and not config.VISION_API_KEY:
        print("VISION_API_KEY is missing. Set it in .env, or use --mock for fixtures.", file=sys.stderr)
        return 2

    raw_dir = None if args.mock else args.output.parent / "raw"
    results: list[ImageResult] = []
    for index, label in enumerate(labels):
        if index and not args.mock:
            time.sleep(args.delay)
        results.append(evaluate_label(label, foods, args.images_dir, args.mock, raw_dir))

    summary = summarize(results)
    print_report(results, summary)
    print_outside_table(labels, foods)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    mode = "mock (fixtures, no API)" if args.mock else f"live ({config.GEMINI_MODEL})"
    args.output.write_text(
        render_summary_md(results, summary, mode, args.labels.name), encoding="utf-8"
    )
    print(f"\nWrote {args.output.relative_to(ROOT_DIR) if args.output.is_relative_to(ROOT_DIR) else args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
