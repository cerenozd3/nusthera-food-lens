# Evaluation summary

- Mode: **live (gemini-3.5-flash-lite)**
- Labels: `labels.csv`
- Photos: 15 (scored 15, failed 1, skipped 0)

## Metrics

| Metric | Value |
| --- | --- |
| Recognition rate (found labeled foods / all labeled foods) | 50.0% (9/18) |
| Precision (predicted foods that are labeled) | 33.3% (9/27) |
| Calorie error, mean | 30.6% |
| Calorie error, median | 21.5% |
| Calorie bias (negative = underestimates) | 0.9% |

Calorie error = |predicted_kcal - true_kcal| / true_kcal. A failed photo counts as 0 predicted kcal (100%). Skipped photos are excluded.

Ground truth comes from labels.csv. 6 of 18 labeled foods are not in foods.csv: they count in the recognition rate, but their kcal cannot be computed.

## Worst 3 photos by calorie error

| Photo | True kcal | Predicted kcal | Error | Reason (automatic; confirm by hand) |
| --- | --- | --- | --- | --- |
| cips.png | 300 | 0 | 100.0% | model_error: No foods were detected in the photo. Try a closer, well-lit photo. |
| tomato souce pasta.png | 350 | 579 | 65.4% | missed_item: pasta, tomato sauce; extra_item: pasta, cooked, tomato, cheese, cheddar, olive oil; label_not_in_foods_csv (kcal cannot be computed even if recognized): pasta, tomato sauce; total over by 65% |
| bread.jpg | 530 | 212 | 60.0% | portion_estimate: all names correct but gram estimate under by 60% |

## Portion accuracy (auxiliary; not an assignment metric)

Gram error = |predicted g - reference g| / reference g, for correctly found foods only.

- Mean: 18.7%, median: 6.7% over 9 found foods

| Photo | Food | Reference g | Predicted g | Error |
| --- | --- | --- | --- | --- |
| grilled chic.jpg | chicken breast, grilled | 180 | 180 | 0.0% |
| frenchfires.jpg | french fries | 150 | 150 | 0.0% |
| banana.jpg | banana | 120 | 118 | 1.7% |
| lahmacun.png | lahmacun | 150 | 160 | 6.7% |
| izgara kofte.png | kofte, grilled meatballs | 200 | 160 | 20.0% |
| boiled egg.jpg | egg, boiled | 100 | 100 | 0.0% |
| bread.jpg | bread, white | 200 | 80 | 60.0% |
| baklava.png | baklava | 50 | 65 | 30.0% |
| ricegrilledcgicsalad.png | chicken breast, grilled | 120 | 180 | 50.0% |

## All photos

| Photo | Status | Labeled | Predicted | True kcal | Predicted kcal | Error |
| --- | --- | --- | --- | --- | --- | --- |
| grilled chic.jpg | ok | chicken breast, grilled | chicken breast, grilled | 306 | 297 | 2.9% |
| frenchfires.jpg | ok | french fries | french fries | 468 | 468 | 0.0% |
| banana.jpg | ok | banana | banana | 107 | 105 | 1.9% |
| yogurt.png | ok | yogurt | yogurt, plain | 90 | 122 | 35.6% |
| lahmacun.png | ok | lahmacun; tomato | lahmacun | 225 | 256 | 13.8% |
| izgara kofte.png | ok | kofte, grilled meatballs | kofte, grilled meatballs; french fries; tomato; cucumber | 420 | 663 | 57.9% |
| boiled egg.jpg | ok | egg, boiled | egg, boiled | 155 | 155 | 0.0% |
| bread.jpg | ok | bread, white | bread, white | 530 | 212 | 60.0% |
| salmon.png | ok | salmon | salmon, grilled; green salad with dressing; almonds | 515 | 579 | 12.4% |
| baklava.png | ok | baklava | baklava | 215 | 278 | 29.4% |
| ricegrilledcgicsalad.png | ok | rice, white, cooked; chicken breast, grilled; salad | chicken breast, grilled; bulgur pilaf, cooked; green salad with dressing | 600 | 568 | 5.2% |
| tomato souce pasta.png | ok | pasta, tomato sauce | pasta, cooked; tomato; cheese, cheddar; olive oil | 350 | 579 | 65.4% |
| chicken pasta.png | ok | chicken pasta | pasta, cooked; chicken breast, grilled; spinach, cooked; olive oil | 620 | 753 | 21.5% |
| orange juice.png | ok | orange juice | orange | 100 | 47 | 53.0% |
| cips.png | failed | chips | - | 300 | 0 | 100.0% |
