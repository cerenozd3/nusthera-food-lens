# AI usage

## Tools and what they were used for

- **Cursor agent mode** — all of the development work: repo analysis, staged planning, writing
  `src/`, `tests/` and `eval/`, debugging, and running the evaluation. The exported sessions are in
  [`ai-history/`](ai-history/) (readable Markdown per session, plus the raw JSONL in
  `ai-history/raw/`).
- **Gemini `gemini-3.5-flash-lite`** — the vision model *inside* the product. It only names foods and
  estimates grams; it never produces nutrition values.
- No AI was used to generate `data/foods.csv` values (USDA FoodData Central and TurKomp, sourced per
  row) or `eval/labels.csv` (labeled by hand from the photos).

I worked in Turkish and the prompts below are copied verbatim, including typos. My working rule,
stated in the prompt for stage 1 and kept for the rest of the project, was: **describe the change
first, write code only after I approve.** That gate is what caught most of the mistakes listed
further down.

| Session | What happened |
| --- | --- |
| `01` | Kickoff analysis and the staged plan, then stages 1–5b: skeleton, nutrition, Gemini, fixtures/mock, UI |
| `02` | The 5b correction bug, 5c save + daily total, UI cleanup |
| `03` | Stage 6: evaluation infrastructure, label validation, live runs |
| `04` | Stage 7: this documentation |

---

## Key prompts

### 1. Analysis only, no code (session 01)

> Projeyi tek seferde yazmanı istemiyorum.
>
> Ben projeyi aşamalara bölerek geliştireceğim ve her aşamadan sonra kodu kendim inceleyip
> çalıştıracağım ve commit atacağım.
>
> Şu anda SADECE analiz yap.
>
> KESİNLİKLE:
>
> * Kod yazma
> * Dosya oluşturma
> * Dosya değiştirme
> * Komut çalıştırma
> * Paket yükleme
> * Git işlemi yapma
>
> Ben sonraki mesajlarda sana her aşamayı tek tek vereceğim. O aşama için kod yazmanı o zaman
> isteyeceğim.

**Why.** A one-day assignment where I have to explain every line in a live interview is the worst
possible place to accept a large generated codebase. I wanted an inventory and a plan I had read
before a single file existed.

**Result.** A correct inventory of the repo (FastAPI with only `GET /`, `foods.csv` with 55 rows,
nothing else) and a staged plan — but with three architectural errors in it (see mistakes 1, 2 and 3
below).

**Kept / changed.** Kept the staging idea and the commit-per-stage plan. Changed the proposed order
(the AI wanted mock first, Gemini later; the PDF wants real responses recorded into fixtures, so live
had to come first) and rejected the three wrong decisions in the next prompt.

### 2. The PDF is the only source of truth (session 01)

> Analizinde ödev PDF'iyle çelişen yerler var, planı şöyle güncelle:
>
> 1. Gemini çıktı şeması: {"items":[{"name","grams","confidence"}],"notes":"..."} (foods değil, items + notes).
> 2. Prompt'a foods.csv'deki yalnızca name sütununu ekle, model bu listeden seçsin. Alias/normalize yalnızca yedek. Eşleşmeyen = "unknown", kullanıcı seçer.
> 3. Geçersiz/boş yanıtta bir kez tekrar dene, sonra kullanıcıya anlaşılır hata mesajı göster. Canlı modda hata olursa mock'a DÜŞME. Mock yalnızca MOCK_MODE=true ile açılır.
> 4. Mock mod: gerçek Gemini ham yanıtlarını fixtures/<görsel_adı>.json olarak kaydet, mock modda bu dosyaları oku. En az 3 örnek görsel + fixture. Sıra: Gemini → fixture kaydı → mock.
> 5. Klasörler: eval/images/, eval/labels.csv (image,items,true_kcal), eval/run_eval.py. Metrikler: tanıma oranı = doğru bulunan ÷ tüm etiketli yiyecekler; kalori hatası = ortalama |tahmin-gerçek|/gerçek yüzde; ayrıca en kötü 3 fotoğraf ve nedenleri.
> 6. Gerçek pytest testleri yaz (hesaplama, eşleştirme, şema doğrulama), requirements.txt ekle.
> 7. DESIGN.md (max 1.5 sayfa): mimari, güvenlik/gizlilik (sağlık iddiası yok, alerjen, fotoğraf saklama, veri gönderimi), ilaç uygulaması sorusu. AI_USAGE.md için her aşamada önemli prompt'ları ve AI hatalarını kaydet.
> 8. Arayüzde gramajın "tahmini" olduğu görünsün.
>
> Güncellenmiş aşama planını yaz, kod yazma; ben onaylayınca 1. aşamaya başlarız.

**Why.** Three items in the AI's plan contradicted the assignment. Naming each one with the correct
replacement is much more reliable than saying "re-read the PDF".

**Result.** The plan came back matching the PDF, and all three decisions survived into the final
code: `src/models.py` uses `items` + `notes`, `src/vision.py` injects the CSV names into the prompt
and retries once, and there is no path from a live failure to a fixture.

**Kept / changed.** All eight points kept. Item 2 got tightened later: I dropped "alias/normalize as
a fallback" entirely, because the food list is in the prompt, so exact matching is enough and a fuzzy
match would silently produce a wrong calorie number.

### 3. Approval gate and per-stage constraints (session 01)

> Plan PDF'e uygun, ancak şu eklemelerle 1. aşamaya başla:
> - Her yeni env değişkeni (GEMINI_MODEL, MAX_UPLOAD_MB vb.) .env.example'a eklensin.
> - Arayüzde sabit uyarı: "Tahmini değerlerdir; tıbbi veya diyet tavsiyesi değildir; alerjen tespiti yapılamaz."
> - Her aşamada eklenen davranışa pytest ekle (retry, boş items, geçersiz JSON, canlıda mock'a düşmeme); Gemini çağrıları testte mocklansın.
> - Fixture görselleri eval/images/ içinden seçilir; fixture adı görsel adıyla eşleşir (meal_01.jpg -> fixtures/meal_01.json). run_eval.py canlı koşarken ham yanıtları fixtures/'a kaydetme bayrağı sunsun.
> - "Doğru bulunan yiyecek" = etiketteki yiyeceğin eşleştirme sonrası aynı CSV adıyla bulunması. labels.csv: image,items,true_kcal + opsiyonel category.
> - 5. aşamayı böl: 5a analiz ekranı, 5b düzeltme, 5c kayıt + günlük toplam.
> -Model çıktısı CSV'deki isimle exact eşleştirilir; eşleşmezse unknown yapılır ve kullanıcıya seçim imkânı verilir.
> -5. aşamada makroların/kalorinin foods.csv üzerinden kod tarafından hesaplandığını unutma!! -pdfte bulunan bonus kısımlarında bulunan görevleri şimdilik yapmayacağız. ben söylemediğim sürece orayı okuyup planını bonus görevlere göre yönlendirme. -----En önemli kural: her promptum ve aşamadan sonra kodda değişiklik yapmadan bana neler değiştireceğini söyle onaylarsam ilerle.----
> Başla: 5-6 satırlık özet, sonra yalnızca 1. aşama kodu.

**Why.** Two problems I wanted closed up front: scope creep into the bonus track, and code appearing
before I had read what it would do. Splitting stage 5 into 5a/5b/5c was to keep each commit small
enough to review.

**Result.** Every later stage started with a short summary I could reject. The disclaimer string, the
`.env.example` rule and the "estimated" gram tag all landed and are still in `src/static/index.html`.
The bonus track was never touched.

**Kept / changed.** Kept everything except two things: the optional `category` column in
`labels.csv` (never used — it belongs to the bonus tiered-evaluation item) and the flag for
`run_eval.py` to write fixtures during a live run. The live runner writes raw responses to
`eval/results/raw/` instead, so a live evaluation cannot quietly overwrite the fixtures that mock
mode depends on.

### 4. Reuse the existing schema (session 01, approving stage 3)

> Doğru, onaylıyorum. Yalnızca şunlara dikkat et:
> -src/models.py içindeki mevcut DetectedItem ve VisionResponse sınıflarını kullan, mükerrer model tanımlama.
> -Prompt'ta modelden CSV isimlerinin yanı sıra grams ve confidence (0.0-1.0) alanlarını üret.
> -Yanıtta olası ```json bloklarını temizleyecek defensive parsing ekle.
> -src/vision.py ve tests/test_vision.py dosyalarını yaz."

**Why.** The stage 3 plan described "validate items + notes" without saying *which* schema it would
validate against. Stage 1 had already created `DetectedItem` and `VisionResponse`, and a second copy
inside `vision.py` would mean two contracts drifting apart — exactly the kind of duplication that is
cheap to prevent and annoying to unwind.

**Result.** `src/vision.py` imports `VisionResponse` from `src/models.py`; there is still exactly one
definition of each model in the repo. The defensive parsing became `strip_json_fences`, which was
worth asking for: the model does sometimes wrap JSON in a markdown fence.

**Kept / changed.** All kept. Nothing was changed afterwards.

### 5. Green tests, broken browser (session 01 → session 02)

> Sorun hâlâ devam ediyor: 54 test geçiyor ama tarayıcıda analiz sonucu gelen tüm yiyecekler yine `unknown` görünüyor.
>
> Yeni özellik ekleme. Önce gerçek problemi bul ve düzelt.
>
> Şu akışı adım adım kontrol et:
> Gemini/fixture → `/analyze` → backend exact match → JSON response → index.html'deki JavaScript → tablo.
>
> Özellikle:
> - `/analyze` response içinde `name` gerçekten `rice, white, cooked` vb. olarak geliyor mu?
> - Backend doğru eşleştiği halde frontend bunu `unknown`a çeviriyor mu?
> - `renderResults`, state güncellemesi veya katalog eşleştirmesinde `unknown` yazan bir kod var mı?
> - `base`/renk/hazırlama parsing'i modelden gelen tam name üzerinde yanlışlıkla çalışıyor mu?
>
> Gerçek browser akışındaki hatayı bul, sadece gerekli kodu düzelt.
> Ardından mevcut 54 teste ek olarak UI tarafında gerçek `/analyze` response'undan gelen `rice, white, cooked` değerinin ekranda `unknown`a dönüşmediğini test et.
>
> Yeni özellik ekleme, 5c'ye geçme.

**Why.** The previous attempt had "fixed" the bug by adding a regression test that passed while the
browser was still broken. Naming each hop in the chain forces the answer to be a location, not
another guess, and "no new features" stops the AI from papering over a bug with a bigger abstraction.

**Result.** The bug was in the front end, not the backend: `/analyze` was returning the correct exact
CSV names and the page was rebuilding names from parsed fragments, turning every row into `unknown`.

**Kept / changed.** The real fix came in the next prompt (see #6) and was a deletion rather than a
patch. What I kept from this one was the requirement for a test that asserts on the actual
`/analyze` response shape — `tests/test_ui_analyze_display.py`.

### 6. Delete the over-engineering instead of fixing it (session 02)

> Bu projede sadece mevcut 5b bug'ını düzelt.
>
> PROBLEM:
> - İlk /analyze sonucu doğru çalışıyor.
> - Örneğin model `rice, white, cooked` döndürdüğünde nutrition doğru hesaplanıyor.
> - Ancak kullanıcı food adını veya gramajı değiştirdiğinde `/recalculate` response'u `not found` dönüyor.
> - Bu yüzden food değiştirilemiyor ve gramaj değişince nutrition güncellenmiyor.
>
> İSTEDİĞİM UX:
> 1. Food alanı searchable/typeable olacak.
> 2. Kullanıcı `ri` yazınca foods.csv içindeki gerçek `name` değerlerinden uygun seçenekler gösterilecek.
> 3. Seçilen değer doğrudan CSV'deki exact `name` olacak.
> 4. Renk/pişirme kategorisi olmayacak.
> 5. Food değişince nutrition yeniden hesaplanacak.
> 6. Gram değişince mevcut `/recalculate` endpoint'i otomatik çağrılacak ve kcal/protein/carbs/fat güncellenecek.
> 7. Hesaplama sadece foods.csv'den yapılacak.
> 8. Save ve daily total ekleme.
>
> ÖNEMLİ:
> - Önce mevcut kodu incele.
> - `/analyze` çalışan akışını değiştirme.
> - `foods.csv`yi değiştirme.
> - Yeni bir matching sistemi veya gereksiz abstraction ekleme.
> - Mevcut `/recalculate` endpoint'ini kullan.
> - Sorunun kaynağını bul ve minimum kod değişikliği yap.
> - parse_food_name / color / prep / match_csv_name gibi 5b için eklenmiş gereksiz kategorileştirme mantığını kaldırabilirsin.
> - Frontend'in `/recalculate` gönderdiği JSON ile backend'in beklediği JSON birebir uyumlu olsun.
> - Test ekle veya mevcut testleri güncelle.
> - En sonda sadece değiştirilen dosyaları ve test sonucunu kısa yaz.

**Why.** My earlier 5b prompt had asked for "colour and preparation dropdowns derived from
`foods.csv`", and the AI built it: `parse_food_name`, `color`, `prep`, `match_csv_name`. That was a
bad idea of mine — `foods.csv` has flat names like `rice, white, cooked`, not attributes — and it
broke the exact matching that already worked. The right move was to name the dead code and authorise
its removal, plus state the invariant that the front end and backend must agree on one JSON shape.

**Result.** The categorisation layer was deleted, the food box became a search over the real CSV
names, and `/recalculate` started working because both sides now send exactly the `DetectedItem`
fields. `editorPayload()` in `index.html` is the one function that builds that body, for both
`/recalculate` and `/save`.

**Kept / changed.** Kept the whole simplification. This is the change I would make earlier next
time — the fancier UI was mine, not the AI's, and it cost more than it gave.

### 7. `labels.csv` is ground truth, not a view of `foods.csv` (session 03)

> Stage 6 evaluation validationını düzelt.
>
> Önemli: PDF'deki evaluation mantığına göre labels.csv ground-truth kaynağıdır. Food name'lerin foods.csv'de bulunması validation için zorunlu OLMAMALI.
>
> - labels.csv gerçek food + gram + true_kcal değerlerini tutar.
> - foods.csv yalnızca model tahmininden nutrition/kcal hesaplamak için kullanılır.
> - foods.csv'ye yiyecek ekleme.
> - labels.csv'deki isimleri değiştirme.
> - true_kcal değerlerini değiştirme.
> - image, name:grams, pozitif gram, true_kcal ve minimum 15 fotoğraf kontrolleri devam etsin.
> - Recognition rate ve calorie error labels.csv'deki ground truth ile model tahminini karşılaştırsın.
> - Gram bilgisi ayrıca yardımcı analiz olarak korunabilir; ana PDF metriklerini değiştirmesin.
>
> Testleri güncelle ve pytest çalıştır.
> Live evaluation çalıştırma.

**Why.** The validator refused any label whose food was not a row in `foods.csv`, and the AI had
presented that as a PDF requirement. It is not. My plate is my plate: if I ate crisps and my table
has no crisps row, the honest outcome is a low recognition rate, not an edited label. Making
`labels.csv` legal by rewriting it would have been measuring the table instead of the model.

**Result.** `load_labels` stopped checking membership; `labels_outside_table()` reports those foods as
a note in the console and in `summary.md`. The structural checks (file name, `name:grams`, positive
numbers, 15-photo minimum) stayed. Recognition rate and calorie error were locked by a test that
proves the auxiliary gram analysis does not touch them.

**Kept / changed.** All kept. The visible cost is honest and documented: 7 of 18 labeled foods have
no row in the table, which caps recognition rate at about 61 %.

### 8. Diagnose the failing photo without touching anything (session 03)

> Stage 6 evaluation için sadece cips.png görselini tekrar çalıştır.
>
> Amaç yalnızca gerçek hatayı teşhis etmek.
>
> Kurallar:
> - Kod değiştirme.
> - labels.csv değiştirme.
> - foods.csv değiştirme.
> - Prompt değiştirme.
> - Evaluation metriklerini değiştirme.
> - Genel 15 fotoğraflık evaluation'ı tekrar çalıştırma.
>
> Mevcut live Gemini evaluation akışını kullanarak yalnızca cips.png'yi çalıştır.
>
> Özellikle:
> 1. Gemini API çağrısının gerçek exception/error mesajını göster.
> 2. HTTP status code varsa göster.
> 3. Response body varsa göster.
> 4. Hata modelden mi, API'den mi, image formatından mı, request boyutundan mı, validation'dan mı kaynaklanıyor belirle.
> 5. Eğer Gemini başarılı bir JSON döndürüyorsa ham response'u göster.
> 6. Eğer kod gerçek hatayı "vision model could not be reached" şeklinde genelliyorsa, sadece teşhis amacıyla gerçek exception'ın terminalde görünmesini sağla; kalıcı kod değişikliği yapma.
>
> Sonuçta cips.png'nin neden fail olduğunu kısa şekilde açıkla.

**Why.** One photo out of 15 was reported as 100 % error behind the app's generic "could not be
reached" message, and the AI's first explanation ("photo-specific error") was a guess. I wanted the
raw exception, explicitly one photo, one API call, and a hypothesis list to eliminate — without a
permanent code change that would pollute the evaluation.

**Result.** The single call succeeded. It ruled out image format (302×296 RGBA PNG), request size
(181 KB, ~1630 tokens), schema validation and safety blocking. The raw response was
`{"items": [{"name": "french fries", "grams": 85, "confidence": 0.45}], "notes": "The image shows
potato crisps/chips, but none of the available food types precisely match ridged potato chips;
'french fries' is used as the closest fried potato product approximation."}`. Remaining hypothesis:
a transient API failure on the last of 15 back-to-back calls, unproven because the real exception
was gone.

**Kept / changed.** Nothing was kept in the repo at all, which was the point — the diagnostic script
ran from `/tmp` and was deleted. What I kept was the finding, now a documented limitation: the
generic error message hides the cause, and it should log the exception type and HTTP status.

### 9. Test the hypothesis with a flag, not a code change (session 03)

> Final Stage 6 evaluation'ı mevcut kodla tekrar çalıştır.
>
> PDF'deki evaluation ve retry kurallarına aynen uy.
>
> Kurallar:
> - Kod değiştirme.
> - Prompt değiştirme.
> - Model değiştirme.
> - labels.csv değiştirme.
> - foods.csv değiştirme.
> - Uygulamadaki retry davranışını değiştirme.
> - Her görsel için PDF'de istenen maksimum 1 retry kuralı aynen korunmalı.
> - Ek retry ekleme.
> - Sadece evaluation sırasında görseller arasındaki Gemini çağrılarına 5 saniye bekleme ekle.
> - Mevcut evaluation script'inin desteklediği --delay 5 parametresini kullan.
> [...]
> Önemli:
> Bu bir kod değişikliği değildir. --delay 5 yalnızca evaluation çalıştırılırken çağrılar arasına bekleme koymalıdır.

**Why.** The obvious "fix" for a suspected rate limit is a backoff inside `analyze_image` — but the
assignment specifies at most one retry, and changing the retry policy would change what the numbers
mean. `run_eval.py` already had `--delay`, so the hypothesis could be tested from outside the app.

**Result.** The API error disappeared, which confirmed it came from back-to-back calls. And
`cips.png` failed *differently*: the model answered, with an empty `items` list, twice. That is the
real, reportable reason — and it is the opposite of what the diagnostic call in #8 returned for the
same photo, which is how I learned the model is not consistent on this image.

**Kept / changed.** No code change. `--delay 5` is documented in the README as the command that
produced the reported numbers.

### 10. Check the label against the photo (session 03)

> lahmacun için görselde bir adet domates gerçekten bulunuyor. bunu etiketli labels.csv'ye ekle ve summary.md bir defa daha yaz evaluation çalıştır

**Why.** `lahmacun.png` was in the worst 3 with a 78 % error, and the automatic reason said the model
had added a tomato that was not in the label. I opened the photo. There is a tomato. The label was
wrong, not the model.

**Result.** After adding `tomato:30`, that photo's calorie error fell from 78 % to 13.8 % — but the
recognition rate dropped from 58.8 % (10/17) to 50.0 % (9/18), because in *that* run the model did not
name the tomato at all, even though it had in the previous run. So the label fix was correct and the
headline metric got worse; both facts are in the README.

**Kept / changed.** Kept the corrected label. It also changed how I read the results: the same photo
gives different answers across runs, so a single run is a sample, not a measurement. That is now a
documented limitation instead of a number I quietly trusted.

---

## Where the AI was wrong, and how I caught it

**1. It invented a JSON schema.** The first plan specified `{"foods": [{name, grams, confidence}]}`.
The assignment specifies `items` plus `notes`. *Caught by* reading the plan against the PDF before
approving it. A schema mismatch would have failed validation on the very first live call — cheap to
catch on paper, expensive to catch at 2 a.m. *Fix:* prompt #2, item 1. `src/models.py` has used
`items` + `notes` from the first commit.

**2. It wanted live errors to fall back to mock.** The proposed stage was *"Gemini entegrasyonu —
gerçek çağrı, structured JSON, hata / timeout, mock’a düşme"* ("fall back to mock"). That is a
comfortable-looking failure mode and a dishonest one: a dead API key would look like a working app,
and an evaluation run would score fixtures instead of the model. *Caught by* recognising the pattern
from the PDF's separation of live and mock mode. *Fix:* prompt #2, item 3. `VisionError` carries a
user-facing message, `MOCK_MODE` is the only way into `src/mock.py`, and
`tests/test_vision.py` asserts that live mode never reads a fixture.

**3. It argued against putting the food list in the prompt.** *"CSV isimleri prompt’a birebir
kopyalanmamalı varsayılanı. Eşleştirme kodda olmalı."* — reasonable-sounding token-cost advice that
contradicts the assignment, which says to put the names in the prompt precisely to make matching
trivial. *Caught by* the PDF. *Fix:* prompt #2, item 2. `build_prompt()` lists all 55 names; matching
is exact and anything else is `unknown`.

**4. Its plan did not say which Pydantic models it would use.** Stage 1 had created `DetectedItem`
and `VisionResponse`; the stage 3 plan just said "validate items + notes", which is how you end up
with a second copy of a schema inside `vision.py`. *Caught by* the approval gate — I read the plan
and added the constraint (prompt #4) before any code was written, so no duplicate was ever committed.
There is still exactly one definition of each model in the repo. *Lesson:* the gate is worth the
round trip; this one cost one sentence instead of a refactor.

**5. It confused ground truth with prediction.** In stage 6 the AI made "every label name must exist
in `foods.csv`" a hard validation error, and wrote *"PDF, tabloda karşılığı olmayan yiyeceğin
`unknown` olmasını ve kullanıcının seçmesini istiyor. Yani etiketteki her ad `foods.csv` ile birebir
eşleşmeli"* — presenting its own inference as a PDF requirement. The PDF rule is about the *app*
handling an unmatched *model output*; it says nothing about labels. If I had accepted it I would have
rewritten my labels until the score improved, which measures nothing. *Caught by* noticing that the
proposed remedy was "edit your ground truth" — with ground truth, that is always the wrong direction.
*Fix:* prompt #7. `foods.csv` is now only used to price predictions, and unmatched labels are
reported as a note.

**6. It labelled a design decision as a PDF requirement.** Same incident as #5, but the failure mode
is worth separating, because it repeated: when the AI could not tell where an idea came from, it
attributed it to the PDF, which makes it sound non-negotiable. *Caught by* asking "which line of the
PDF says that?" and re-reading the section myself. *Fix:* for stage 7 I put the rule in the prompt
directly — *"PDF'de açıkça istenmeyen şeyleri PDF gereksinimi gibi yazma"* — and this file separates
what the assignment requires from what I chose.

**7. It fixed a bug by adding a passing test.** After the 5b regression, the AI reported 54 passing
tests including a new regression test for `rice, white, cooked`, while every row in the browser still
said `unknown`. The tests were exercising the backend, and the bug was in the front end.
*Caught by* using the app myself instead of trusting the test count. *Fix:* prompts #5 and #6 — name
every hop in the chain, forbid new features, and require a test against the real `/analyze` response
(`tests/test_ui_analyze_display.py`). *Lesson:* "116 tests pass" is not evidence that the product
works; it is evidence that what the tests cover works.

**8. It kept guessing at the `cips.png` failure.** Across two runs it offered "photo-specific error",
then a size or safety rejection, all from the app's generic "could not be reached" message.
*Caught by* refusing the guesses and demanding the raw exception for one photo, one call (prompt #8),
then testing the remaining hypothesis with `--delay 5` rather than a code change (prompt #9). The
real answer turned out to be two different problems stacked: a transient API failure that spacing the
calls fixed, and — underneath it — the model returning an empty `items` list because `chips` is not in
`foods.csv`. Only the second one is a real finding about the system, and it is what the README
reports.

**9. It mislabelled my own labels as the model's fault.** The automatic reason for `lahmacun.png`
blamed the model for adding a tomato. *Caught by* opening the photo: the tomato is there. The
generated "reason" column is a first pass, not a verdict — `summary.md` says so in the header, and
every worst-3 reason in the README was checked against the photo by hand.

---

## What I would prompt differently next time

- **Ask "which line of the PDF requires this?" before approving any plan item.** Mistakes 1, 2, 3, 5
  and 6 all had the same shape: a plausible decision presented as a requirement. One question would
  have caught all five.
- **Describe the UX I want, not the mechanism.** My 5b prompt asked for colour and preparation
  dropdowns derived from `foods.csv`. The AI built exactly that, and it was the wrong shape for a flat
  name table. "The user must be able to find the right CSV row quickly" would have produced the search
  box I ended up with, one prompt later instead of four.
- **Demand a failing reproduction before a fix.** "Show me the request and the response that prove
  the bug, then fix it" would have skipped the round where the bug was closed with a green test.
- **Ask for the real exception on the first failure, not the third.** The `cips.png` detour cost two
  evaluation runs of quota. "Never swallow an exception into a generic message during evaluation"
  belongs in the stage 6 prompt.
- **Separate label errors from model errors in the evaluation prompt.** I should have asked, up front,
  for a per-photo column saying whether the error comes from a missing `foods.csv` row, a portion
  estimate, or a genuine misrecognition. I ended up reconstructing that by hand for the worst 3.
- **Plan for run-to-run variance from the start.** Asking for three runs and a spread, on a smaller
  photo set if quota is tight, would have given a number I could defend instead of one I have to
  caveat.
