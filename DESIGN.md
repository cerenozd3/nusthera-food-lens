# Design

## Architecture

Python 3.14 + FastAPI, one HTML page served by the same app, SQLite for saved meals. No build step,
no front-end framework, no database server — the fastest stack for a one-day prototype, and small
enough that I can explain every line.

The rule the whole design is built around: **the model recognises, our code calculates.**

```
src/vision.py     prompt + Gemini call + JSON parse + one retry
src/mock.py       same contract, read from fixtures/ instead of the network
src/models.py     Pydantic: items[{name, grams, confidence}] + notes
src/foods.py      data/foods.csv, exact-name lookup, name search
src/nutrition.py  grams x per-100g / 100, unknown handling, meal totals
src/storage.py    SQLite: saved rows and daily totals
src/main.py       endpoints
```

Three decisions worth defending:

- **Nutrition never comes from the model.** `models.py` has no field for calories or macros, so an
  invented number cannot even be parsed. The numbers stay reproducible and auditable against a cited
  table.
- **The food list goes into the prompt and matching is exact.** A name that is not an exact CSV row
  becomes `unknown` with no macros, and the user picks the real food. No fuzzy matching: a wrong match
  is a silently wrong calorie count, which is worse than an honest `unknown`.
- **Mock mode is opt-in only.** A live failure shows an error and never falls back to a recorded
  response. Otherwise a dead API key would look like a working app, and the evaluation would score
  fixtures instead of the model.

## Data flow

```
photo (browser, in memory)
  -> POST /analyze  -> Gemini  (or fixtures/<name>.json when MOCK_MODE=true)
  -> Pydantic validation; invalid or empty -> retry once -> user-facing error
  -> exact-name match against data/foods.csv -> no match = unknown
  -> our code: grams x per-100g / 100, per item and per meal
  -> user edits food or grams -> POST /recalculate (CSV again, model not called)
  -> POST /save -> recompute from CSV -> SQLite -> daily total
```

The server recalculates from `foods.csv` on both `/recalculate` and `/save` and ignores any nutrition
values in the request body, so a tampered or stale client cannot write a wrong calorie number into
the database.

## Safety and privacy

**No health claims.** Food Lens estimates, it does not advise. A fixed line sits above every screen:
*"Values are estimates only; not medical or dietary advice; allergens cannot be detected."* The app
never calls a meal healthy or unhealthy, sets no targets, recommends nothing, and shows no reference
daily intake a user could read as a pass or fail. Portion weights are tagged `estimated`, because the
evaluation shows the model's guess can be off by 60 %.

**Allergens.** Deliberately out of scope, and stated rather than silently omitted. A photo cannot show
what is inside a sauce, which oil was used, or whether a shared kitchen cross-contaminated the plate.
An allergen answer that is right most of the time is dangerous in the one case that matters, so the
app refuses the question. The model's `notes` field ("sauce not visible clearly") is context, not a
safety feature.

**Photos.** The upload lives in memory for one request: never written to disk, never logged, never
stored. Only the resulting rows (food, grams, macros, timestamp) are saved, and nothing links them to
a person — no account, no user id. The photos in `eval/images/` are our own, contain no faces, and are
committed on purpose as the evaluation set.

**Where data goes.** In live mode the image bytes and the prompt (which contains the 55 `foods.csv`
names) go to the Google Gemini API and nowhere else: no analytics, no error reporting, no third party.
In mock mode nothing leaves the machine. `MOCK_MODE` is the single switch deciding whether a photo
leaves the device, and it defaults to `true`. The key lives in gitignored `.env`; only a placeholder
`.env.example` is committed.

**Not built, and honest about it:** no auth, rate limiting, encryption at rest, retention policy or
audit log. This is a prototype, not something to point real users at.

## If Nusthera builds a medication app

The Food Lens image-recognition approach should not be applied directly to medication. The risk is
substantially higher because an incorrect medication identification can lead to harmful use.

**What changes.** When a user scans a medicine or its package, the application should first
establish and verify the medication identity from a trusted source before displaying definitive
medication information. The verification step should include the medicine name and, where relevant,
dosage/form and the user's context, such as whether this is a medication they have previously saved
as a regular medicine or whether they have a prescription. If the image is unclear, unreadable, or
the medication cannot be reliably identified, the application should not display definitive
medication information and should ask for a clearer image or additional information.

Identification should therefore stop being a single confident answer and become a verified result.
Box photos, including barcode or other identifying information where available, should be preferred
over loose-pill identification. The reference data should be a licensed, versioned medicines source
rather than a small manually curated table, so the information can be traced to a trusted source and
its version/date. Below the required confidence or verification threshold, the application should
say that it cannot reliably identify the medicine instead of presenting its best guess.

**What information can be shown.** Once the medicine has been verified, general informational
content about that medicine can be displayed. The fixed health and safety warnings should remain
visible. However, the application should not infer or recommend a personal dosage, treatment, or
medication schedule from the image. Dosage and usage instructions should only be shown as
user-specific information when they have previously been reliably saved by the user as part of
their regular medication record; they should not be inferred from the photograph or invented from a
model prediction.

**What I would refuse to build.** The application should not provide personalized treatment
recommendations, infer a dosage from a photograph, or tell a user to start, stop, skip, or change a
medicine based on an image. It should also refuse to give definitive identification of an unclear or
unverified loose pill. Medication interaction or safety information should not be presented as a
personalized medical decision without an appropriate verified data source and safety layer.

**What must be in place before shipping.** A trusted, licensed and versioned medication data source
with a documented update process; verification of medication identity and relevant information
before anything definitive is shown; a safe fallback and clear user warnings for unclear images;
security and privacy controls appropriate for medication/health information; clearly defined
permitted and prohibited use cases; and comprehensive testing and risk assessment before release
with real users. The system should also have a documented approach for consent, data retention and
deletion, and should be reviewed by appropriately qualified professionals before being used for
real medication decisions.

If these requirements cannot be met, the safer product scope is narrower: verify the medicine from
its package or barcode, provide general information from the trusted source, and refuse to identify
an unclear loose pill or provide personalized dosage or treatment advice.
