# AI session history

Raw export of the Cursor agent sessions used to build this project, in chronological order.

- `raw/*.jsonl` — the unedited session transcripts as Cursor stores them: one JSON record per line,
  every user message, assistant message and tool call with its full arguments.
- `*.md` — the same sessions rendered for reading. User prompts and assistant messages in full; tool
  calls collapsed to name and target, because their arguments and outputs are long and already in the
  JSONL.

All of the work was done in Cursor agent mode on 29 Sep 2026, in Turkish. The prompts quoted verbatim
in [`../AI_USAGE.md`](../AI_USAGE.md) come from these files.

| Session | Time (UTC+3) | User turns | Tool calls | What happened |
| --- | --- | --- | --- | --- |
| [`01-stages-1-to-5b`](01-stages-1-to-5b.md) | 15:53–18:26 | 21 | 257 | Repo inventory and a staged plan (the plan that contained the `foods` schema, the mock fallback and the "don't put the CSV names in the prompt" advice), then correcting it against the PDF and building stages 1–5b: skeleton and config, nutrition from `foods.csv`, live Gemini with validation and one retry, fixtures and mock mode, the analysis screen, and the first (over-engineered) correction UI. Ends with the `unknown` bug unresolved. |
| [`02-stage-5b-fix-5c-save-ui`](02-stage-5b-fix-5c-save-ui.md) | 18:24–18:50 | 4 | 119 | Root-causing the `unknown` bug, deleting the colour/preparation layer, the searchable food box, `/recalculate` on edit, stage 5c save + daily total, and the UI cleanup. |
| [`03-stage-6-evaluation`](03-stage-6-evaluation.md) | 19:00–21:13 | 10 | 91 | Evaluation: `src/eval_metrics.py`, `eval/run_eval.py`, label validation, the ground-truth correction, four live runs, the `cips.png` diagnosis, and the lahmacun label fix. |
| [`04-stage-7-documentation`](04-stage-7-documentation.md) | 21:28– | 4 | 104 | `README.md`, `DESIGN.md`, `AI_USAGE.md` and this export; then dropping the three throwaway kickoff chats and renumbering; Windows PowerShell copy-paste commands in the README; and replacing the medication-app answer in `DESIGN.md` with the author's own text. The later prompts in this session are turns 2–4. |

A few short throwaway chats from the same afternoon are not included: they repeated the same kickoff
prompt that session 01 already contains verbatim, and produced no code.

## Sanitisation

Two automated substitutions were applied to every file, and nothing else was edited:

- Local absolute paths `/Users/<my username>/...` → `/Users/<user>/...`
- Any API-key-shaped string → `<REDACTED_API_KEY>`

A scan of the exported files confirmed no key material and no home paths survive. No API key was
present in the transcripts to begin with: the sessions read `.env` only to check that the variable was
set, never to print its value, and `.env` has never been committed to this repository (only
`.env.example` with a placeholder is tracked). The transcripts contain no email addresses, phone
numbers or third-party personal data.

The exporter itself was a throwaway script run from `/tmp`; it is not part of the application.
