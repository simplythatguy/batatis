# Labeler (GPT Luna) diagnostic — pool = gold + context + hard negatives

DIAGNOSTIC: pools always contain every gold article, so this measures the labeler, not the pipeline. `complete_surfaced` = every gold article labelled applies or check; precision is a lower bound (gold + context only).

Pool size 25, model gpt-6-luna, tune cases 57, test cases 34. Unit spend $0.812709 (this run $0.8067).

## Tune

| config | cases | complete_surfaced | complete_applies | recall_surfaced | recall_applies | applies_prec_lb | mean_applies | mean_check | errors | missing/unknown/dup | quote_downgraded | $/case | latency s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| medium (20) | 20 | 1.0 | 1.0 | 1.0 | 1.0 | 0.3906 | 3.2 | 6.7 | 0 | 0/0/0 | 0 | 0.00414 | 29.2 |
| high (20) | 20 | 0.85 | 0.85 | 0.85 | 0.85 | 0.3898 | 2.95 | 5.65 | 3 | 0/0/0 | 0 | 0.00583 | 96.6 |
| xhigh (20) | 20 | 0.75 | 0.7 | 0.75 | 0.7 | 0.3519 | 2.7 | 4.25 | 5 | 0/0/0 | 1 | 0.00731 | 77.2 |
| medium (all) | 57 | 1.0 | 0.7368 | 1.0 | 0.8 | 0.3793 | 3.05 | 7.35 | 0 | 0/0/0 | 1 | 0.00376 | 25.8 |
| medium two-pass (all) | 57 | 1.0 | 0.8246 | 1.0 | 0.8667 | 0.2939 | 4.3 | 8.89 | 0 | 0/0/0 | 4 | 0.00752 | 56.0 |

Best (recall-first: complete_surfaced, then applies precision, then cost): **medium (all)**

## Position bias

Same pools reversed, 10 cases at medium single pass: label agreement 0.784 over 250 articles; reversed complete_surfaced 1.0 vs forward 1.0.

## Test (once, best config)

| config | cases | complete_surfaced | complete_applies | recall_surfaced | recall_applies | applies_prec_lb | mean_applies | mean_check | errors | missing/unknown/dup | quote_downgraded | $/case | latency s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| medium (all) | 34 | 1.0 | 0.8235 | 1.0 | 0.8298 | 0.3739 | 3.38 | 7.26 | 0 | 0/0/0 | 2 | 0.00387 | 26.3 |

## Gold articles labelled unlikely (the misses that matter)

### tune medium (all)

None.

### test medium (all)

None.
