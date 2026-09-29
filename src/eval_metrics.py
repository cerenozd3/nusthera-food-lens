"""Pure evaluation logic: label loading, scoring, summary, report rendering.

No network, no file writes. eval/run_eval.py wires this to the vision layer.

Metrics (assignment definitions):
- recognition rate = correctly found labeled foods / total labeled foods
- calorie error    = |predicted_kcal - true_kcal| / true_kcal
- worst 3 photos by calorie error, each with a reason

labels.csv is the ground truth. Its food names are whatever the person on the
plate actually ate, so they do NOT have to exist in foods.csv. foods.csv is only
used to turn the model's prediction into kcal. Labeled foods missing from
foods.csv are reported as a note (they can never contribute kcal), not as an error.
"""

import csv
import math
import statistics
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .foods import FoodRow
from .nutrition import ResolvedMeal

ITEM_SEPARATOR = ";"
GRAM_SEPARATOR = ":"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
REQUIRED_COLUMNS = ("image", "items", "true_kcal")
# With every name right, an error above this is blamed on the gram estimate.
PORTION_TOLERANCE = 0.10
WORST_N = 3

STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


class LabelError(ValueError):
    """labels.csv is unusable. Carries every problem found, not just the first."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class LabelRow:
    """One labeled photo.

    items are the ground-truth food names (free text, not required to be in
    foods.csv); grams[i] is the reference weight of items[i].
    Recognition and calorie error use items and true_kcal only. grams feed the
    auxiliary portion analysis.
    """

    image: str
    items: tuple[str, ...]
    true_kcal: float
    grams: tuple[float, ...] = ()

    @property
    def gram_by_item(self) -> dict[str, float]:
        return dict(zip(self.items, self.grams))


def _positive_number(text: str) -> float | None:
    try:
        value = float(text.strip())
    except ValueError:
        return None
    return value if math.isfinite(value) and value > 0 else None


def _check_image_name(image: str, dir_names: set[str]) -> str | None:
    """Exact, case-sensitive match against the real directory listing.

    Path.is_file() is not enough: macOS ignores case, so a label that works here
    would fail after a clone on Linux.
    """
    if Path(image).suffix.lower() not in IMAGE_SUFFIXES:
        return "unsupported image type (use .jpg, .jpeg, .png or .webp)"
    if image in dir_names:
        return None
    folded = {unicodedata.normalize("NFC", n).casefold(): n for n in dir_names}
    near = folded.get(unicodedata.normalize("NFC", image).casefold())
    if near:
        return f"does not match the real file name exactly (case/Unicode); the file is '{near}'"
    return "file not found in the images folder"


def name_key(name: str) -> str:
    """Comparison key for food names: ignores case and extra whitespace only."""
    return " ".join(name.split()).casefold()


def load_labels(
    path: Path,
    images_dir: Path,
    min_rows: int = 0,
) -> list[LabelRow]:
    """Read and validate labels.csv (image,items,true_kcal).

    items is 'name:grams' entries joined by ';', e.g.
    "rice, white, cooked:180;chicken breast, grilled:120" (quote the field: names
    may contain commas). Names are ground truth and are NOT checked against
    foods.csv. Raises LabelError listing all problems.
    """
    problems: list[str] = []
    rows: list[LabelRow] = []
    seen_images: set[str] = set()
    if images_dir.is_dir():
        dir_names = {p.name for p in images_dir.iterdir() if p.is_file()}
    else:
        dir_names = set()
        problems.append(f"images folder not found: {images_dir}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [col for col in REQUIRED_COLUMNS if col not in (reader.fieldnames or [])]
        if missing:
            raise LabelError(
                [f"{path.name}: header must be image,items,true_kcal (missing: {', '.join(missing)})"]
            )
        for row in reader:
            line = reader.line_num
            where = f"{path.name} line {line}"
            if None in row:
                problems.append(
                    f"{where}: too many columns. Quote fields that contain commas "
                    '(e.g. "rice, white, cooked").'
                )
                continue

            image = (row.get("image") or "").strip()
            if not image:
                problems.append(f"{where}: image is empty.")
                continue
            if image in seen_images:
                problems.append(f"{where}: duplicate image '{image}'.")
            seen_images.add(image)
            image_problem = _check_image_name(image, dir_names)
            if image_problem:
                problems.append(f"{where}: image '{image}': {image_problem}.")

            parts = [p.strip() for p in (row.get("items") or "").split(ITEM_SEPARATOR)]
            parts = [p for p in parts if p]
            if not parts:
                problems.append(f"{where} ({image}): items is empty.")
            items: list[str] = []
            grams: list[float] = []
            for part in parts:
                name, sep, gram_text = part.rpartition(GRAM_SEPARATOR)
                name = name.strip()
                if not sep:
                    problems.append(
                        f"{where} ({image}): '{part}' must be written name:grams "
                        '(e.g. "banana:120").'
                    )
                    continue
                gram_value = _positive_number(gram_text)
                if gram_value is None:
                    problems.append(
                        f"{where} ({image}): grams for '{name}' must be a positive number, "
                        f"got '{gram_text.strip()}'."
                    )
                if not name:
                    problems.append(f"{where} ({image}): '{part}' has an empty food name.")
                items.append(name)
                grams.append(gram_value if gram_value is not None else 0.0)
            if len({name_key(n) for n in items}) != len(items):
                problems.append(f"{where} ({image}): duplicate item names.")

            kcal_text = (row.get("true_kcal") or "").strip()
            try:
                true_kcal = float(kcal_text)
            except ValueError:
                problems.append(f"{where} ({image}): true_kcal must be a number, got '{kcal_text}'.")
                continue
            if not math.isfinite(true_kcal) or true_kcal <= 0:
                problems.append(f"{where} ({image}): true_kcal must be greater than 0.")
                continue

            rows.append(
                LabelRow(image=image, items=tuple(items), true_kcal=true_kcal, grams=tuple(grams))
            )

    if not problems and len(rows) < min_rows:
        problems.append(f"{path.name}: need at least {min_rows} labeled photos, found {len(rows)}.")
    if problems:
        raise LabelError(problems)
    return rows


@dataclass(frozen=True)
class ImageResult:
    image: str
    status: str
    expected: tuple[str, ...]
    true_kcal: float
    predicted: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    predicted_kcal: float | None = None
    detail: str = ""
    # Auxiliary portion analysis only; never used for recognition or calorie error.
    expected_grams: tuple[float, ...] = ()
    predicted_grams: tuple[tuple[str, float], ...] = ()
    # Labeled foods that are not in foods.csv: kcal for them can never be computed.
    outside_table: tuple[str, ...] = ()

    @property
    def gram_errors(self) -> tuple[tuple[str, float, float, float], ...]:
        """(food, reference g, predicted g, |pred - ref| / ref) for each correctly found food."""
        predicted: dict[str, float] = {}
        for name, grams in self.predicted_grams:
            predicted[name_key(name)] = predicted.get(name_key(name), 0.0) + grams
        rows = []
        for name, reference in zip(self.expected, self.expected_grams):
            guess = predicted.get(name_key(name))
            if guess is not None and reference > 0:
                rows.append((name, reference, guess, abs(guess - reference) / reference))
        return tuple(rows)

    @property
    def _predicted_keys(self) -> set[str]:
        return {name_key(n) for n in self.predicted}

    @property
    def found(self) -> tuple[str, ...]:
        """Labeled foods the model named (compared by name, ignoring case/spacing)."""
        keys = self._predicted_keys
        return tuple(name for name in self.expected if name_key(name) in keys)

    @property
    def missed(self) -> tuple[str, ...]:
        keys = self._predicted_keys
        return tuple(name for name in self.expected if name_key(name) not in keys)

    @property
    def extra(self) -> tuple[str, ...]:
        keys = {name_key(n) for n in self.expected}
        return tuple(name for name in self.predicted if name_key(name) not in keys)

    @property
    def kcal_error(self) -> float | None:
        """|predicted - true| / true, as a fraction (0.25 = 25 %)."""
        if self.predicted_kcal is None:
            return None
        return abs(self.predicted_kcal - self.true_kcal) / self.true_kcal

    @property
    def signed_kcal_error(self) -> float | None:
        if self.predicted_kcal is None:
            return None
        return (self.predicted_kcal - self.true_kcal) / self.true_kcal


def labels_outside_table(
    labels: list[LabelRow], foods: dict[str, FoodRow]
) -> dict[str, tuple[str, ...]]:
    """image -> labeled foods that are not in foods.csv (informational, not an error)."""
    keys = {name_key(n) for n in foods}
    found: dict[str, tuple[str, ...]] = {}
    for label in labels:
        missing = tuple(n for n in label.items if name_key(n) not in keys)
        if missing:
            found[label.image] = missing
    return found


def score_image(
    label: LabelRow, meal: ResolvedMeal, foods: dict[str, FoodRow] | None = None
) -> ImageResult:
    """Score one photo against its ground-truth label.

    Predicted nutrition comes from our code (foods.csv), never from the model.
    foods is only used to note which labeled foods the table cannot price.
    """
    outside = ()
    if foods is not None:
        outside = labels_outside_table([label], foods).get(label.image, ())
    predicted = tuple(dict.fromkeys(item.detected_name for item in meal.items))
    unknown = tuple(dict.fromkeys(item.detected_name for item in meal.items if item.unknown))
    grams: dict[str, float] = {}
    for item in meal.items:
        grams[item.detected_name] = grams.get(item.detected_name, 0.0) + item.grams
    return ImageResult(
        image=label.image,
        status=STATUS_OK,
        expected=label.items,
        true_kcal=label.true_kcal,
        predicted=predicted,
        unknown=unknown,
        predicted_kcal=meal.totals.kcal,
        expected_grams=label.grams,
        predicted_grams=tuple(grams.items()),
        outside_table=outside,
    )


def failed_result(label: LabelRow, message: str) -> ImageResult:
    """The model gave no usable answer: nothing recognized, 0 kcal predicted (100 % error)."""
    return ImageResult(
        image=label.image,
        status=STATUS_FAILED,
        expected=label.items,
        true_kcal=label.true_kcal,
        predicted_kcal=0.0,
        detail=message,
    )


def skipped_result(label: LabelRow, message: str) -> ImageResult:
    """Not evaluated (e.g. --mock without a fixture). Excluded from every metric."""
    return ImageResult(
        image=label.image,
        status=STATUS_SKIPPED,
        expected=label.items,
        true_kcal=label.true_kcal,
        detail=message,
    )


def explain(result: ImageResult) -> str:
    """Automatic first-pass reason for the calorie error. A human should confirm it."""
    if result.status == STATUS_SKIPPED:
        return f"skipped: {result.detail}"
    if result.status == STATUS_FAILED:
        return f"model_error: {result.detail}"

    parts: list[str] = []
    expected_keys = {name_key(n) for n in result.expected}
    unknown_matched = tuple(n for n in result.unknown if name_key(n) in expected_keys)
    unknown_extra = tuple(n for n in result.unknown if name_key(n) not in expected_keys)
    extra_known = tuple(
        n for n in result.extra if name_key(n) not in {name_key(u) for u in result.unknown}
    )
    if result.missed:
        parts.append("missed_item: " + ", ".join(result.missed))
    if unknown_matched:
        parts.append(
            "recognized_but_not_in_foods_csv (0 kcal counted): " + ", ".join(unknown_matched)
        )
    if unknown_extra:
        parts.append("unknown_name (not in foods.csv, 0 kcal counted): " + ", ".join(unknown_extra))
    if extra_known:
        parts.append("extra_item: " + ", ".join(extra_known))
    matched_keys = {name_key(n) for n in unknown_matched}
    unpriceable = tuple(n for n in result.outside_table if name_key(n) not in matched_keys)
    if unpriceable:
        parts.append(
            "label_not_in_foods_csv (kcal cannot be computed even if recognized): "
            + ", ".join(unpriceable)
        )

    error = result.signed_kcal_error or 0.0
    direction = "over" if error > 0 else "under"
    if not parts:
        if abs(error) > PORTION_TOLERANCE:
            parts.append(
                f"portion_estimate: all names correct but gram estimate {direction} by {abs(error):.0%}"
            )
        else:
            parts.append("ok: names correct, calories within 10 %")
    else:
        parts.append(f"total {direction} by {abs(error):.0%}")
    return "; ".join(parts)


@dataclass(frozen=True)
class Summary:
    n_images: int
    n_scored: int
    n_failed: int
    n_skipped: int
    labeled_items: int
    found_items: int
    recognition_rate: float | None
    predicted_items: int
    extra_items: int
    precision: float | None
    mean_kcal_error: float | None
    median_kcal_error: float | None
    mean_signed_kcal_error: float | None
    worst: tuple[ImageResult, ...]
    # Auxiliary portion analysis (not an assignment metric).
    gram_pairs: int = 0
    mean_gram_error: float | None = None
    median_gram_error: float | None = None
    # Labeled foods that foods.csv cannot price (they still count in recognition rate).
    outside_table_items: int = 0


def worst_n(results: list[ImageResult], n: int = WORST_N) -> list[ImageResult]:
    """Highest calorie error first; skipped photos are never ranked."""
    scored = [r for r in results if r.kcal_error is not None]
    return sorted(scored, key=lambda r: (-r.kcal_error, r.image))[:n]


def summarize(results: list[ImageResult]) -> Summary:
    scored = [r for r in results if r.status != STATUS_SKIPPED]
    labeled = sum(len(r.expected) for r in scored)
    found = sum(len(r.found) for r in scored)
    predicted = sum(len(r.predicted) for r in scored)
    extra = sum(len(r.extra) for r in scored)
    errors = [r.kcal_error for r in scored if r.kcal_error is not None]
    signed = [r.signed_kcal_error for r in scored if r.signed_kcal_error is not None]
    gram_errors = [row[3] for r in scored for row in r.gram_errors]
    return Summary(
        n_images=len(results),
        n_scored=len(scored),
        n_failed=sum(1 for r in results if r.status == STATUS_FAILED),
        n_skipped=sum(1 for r in results if r.status == STATUS_SKIPPED),
        labeled_items=labeled,
        found_items=found,
        recognition_rate=(found / labeled) if labeled else None,
        predicted_items=predicted,
        extra_items=extra,
        precision=((predicted - extra) / predicted) if predicted else None,
        mean_kcal_error=statistics.fmean(errors) if errors else None,
        median_kcal_error=statistics.median(errors) if errors else None,
        mean_signed_kcal_error=statistics.fmean(signed) if signed else None,
        worst=tuple(worst_n(results)),
        gram_pairs=len(gram_errors),
        mean_gram_error=statistics.fmean(gram_errors) if gram_errors else None,
        median_gram_error=statistics.median(gram_errors) if gram_errors else None,
        outside_table_items=sum(len(r.outside_table) for r in scored),
    )


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _kcal(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def render_summary_md(
    results: list[ImageResult],
    summary: Summary,
    mode: str,
    labels_name: str,
) -> str:
    lines = [
        "# Evaluation summary",
        "",
        f"- Mode: **{mode}**",
        f"- Labels: `{labels_name}`",
        f"- Photos: {summary.n_images} "
        f"(scored {summary.n_scored}, failed {summary.n_failed}, skipped {summary.n_skipped})",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Recognition rate (found labeled foods / all labeled foods) | "
        f"{_pct(summary.recognition_rate)} ({summary.found_items}/{summary.labeled_items}) |",
        f"| Precision (predicted foods that are labeled) | {_pct(summary.precision)} "
        f"({summary.predicted_items - summary.extra_items}/{summary.predicted_items}) |",
        f"| Calorie error, mean | {_pct(summary.mean_kcal_error)} |",
        f"| Calorie error, median | {_pct(summary.median_kcal_error)} |",
        f"| Calorie bias (negative = underestimates) | {_pct(summary.mean_signed_kcal_error)} |",
        "",
        "Calorie error = |predicted_kcal - true_kcal| / true_kcal. "
        "A failed photo counts as 0 predicted kcal (100%). Skipped photos are excluded.",
        "",
        f"Ground truth comes from labels.csv. {summary.outside_table_items} of "
        f"{summary.labeled_items} labeled foods are not in foods.csv: they count in the "
        "recognition rate, but their kcal cannot be computed.",
        "",
        f"## Worst {WORST_N} photos by calorie error",
        "",
        "| Photo | True kcal | Predicted kcal | Error | Reason (automatic; confirm by hand) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in summary.worst:
        lines.append(
            f"| {_cell(r.image)} | {_kcal(r.true_kcal)} | {_kcal(r.predicted_kcal)} | "
            f"{_pct(r.kcal_error)} | {_cell(explain(r))} |"
        )
    if not summary.worst:
        lines.append("| - | - | - | - | no scored photos |")

    lines += [
        "",
        "## Portion accuracy (auxiliary; not an assignment metric)",
        "",
        "Gram error = |predicted g - reference g| / reference g, for correctly found foods only.",
        "",
        f"- Mean: {_pct(summary.mean_gram_error)}, median: {_pct(summary.median_gram_error)} "
        f"over {summary.gram_pairs} found foods",
    ]
    if summary.gram_pairs:
        lines += [
            "",
            "| Photo | Food | Reference g | Predicted g | Error |",
            "| --- | --- | --- | --- | --- |",
        ]
        for r in results:
            for name, reference, predicted, error in r.gram_errors:
                lines.append(
                    f"| {_cell(r.image)} | {_cell(name)} | {reference:g} | {predicted:g} | {_pct(error)} |"
                )

    lines += [
        "",
        "## All photos",
        "",
        "| Photo | Status | Labeled | Predicted | True kcal | Predicted kcal | Error |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| {_cell(r.image)} | {r.status} | {_cell('; '.join(r.expected))} | "
            f"{_cell('; '.join(r.predicted) or '-')} | {_kcal(r.true_kcal)} | "
            f"{_kcal(r.predicted_kcal)} | {_pct(r.kcal_error)} |"
        )
    lines.append("")
    return "\n".join(lines)
