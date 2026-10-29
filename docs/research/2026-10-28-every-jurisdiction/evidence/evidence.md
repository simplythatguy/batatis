# Proof: does Batatis work as well outside Calgary and Edmonton?

Tests run on 2026-10-28 against the engine at `origin/main` 268b7bc3, with the local code database (NBC(AE) 2023, 2nd printing). Nothing here was tested before this date: the research in the parent folder checked sources and designed the next step, but it did not run the app for other places.

## The answer

| Part of the result | Other Alberta places | Outside Alberta |
|---|---|---|
| The application itself: code references, Section C, completeness checks, PDF | **The same as Calgary and Edmonton.** Test 2 runs one application through the engine for 18 places and gets the same output | **Wrong.** The same Alberta application is produced, citing the Alberta code on the Alberta Council form |
| The reviewing office | **Worse.** Only Calgary and Edmonton are named. The other 329 places get a generic "Rest of Alberta" office that has the right rules but does not name the office | **Wrong.** Treated as "Rest of Alberta" |
| Local items (standing variances, guides, local form notices) | **Worse.** Calgary and Edmonton only | None |
| Sending the application to an officer inside Batatis | **Worse.** Calgary and Edmonton only; everyone else exports the PDF and sends it | Not possible |
| First Nations, national parks, airport lands, Lloydminster | **Wrong.** Told to use a Safety Codes Act office, which does not decide there | Not applicable |

So for every Alberta municipality the drafting is as good as Calgary and Edmonton, but the office side is not. Outside Alberta, and on federal and First Nations land, Batatis gives the wrong answer today. It should say "not covered" instead.

## Test 1: what the app says for each place

`place_parity.py` asks the engine's jurisdiction lookup (`Registry.resolve`, the same lookup the app uses) about each of the 390 rows in `alberta-jurisdictions.csv` and the 31 cities in the research. It tries the legal name and the short name, which gives 705 lookups; the two names never gave different answers. The verdict compares the answer with the researched office.

| Kind of place | Places | App names the office | Right rules, office not named | Wrong kind of office |
|---|---:|---:|---:|---:|
| Accredited municipality | 255 | 2 | 253 | 0 |
| Safety Codes Authority area (68 municipalities, 5 Métis settlements) | 73 | 0 | 73 | 0 |
| Accredited Métis settlement | 3 | 0 | 3 | 0 |
| First Nation | 48 | 0 | 0 | 48 |
| National park, Jasper, airport lands | 9 | 0 | 0 | 9 |
| Lloydminster, Redwood Meadows | 2 | 0 | 0 | 2 |
| Major city outside Alberta | 31 | 0 | 0 | 31 |
| **Total** | **421** | **2** | **329** | **90** |

"Right rules, office not named" means the app says "Accredited municipality, or the Alberta Safety Codes Authority in unaccredited areas" and links the Council's search. That is true, but the applicant still has to find the office. The office picker in the app lists 23 of these 421 places by name; the rest are typed.

Why the 90 are wrong: `Registry.resolve` (`engine/jurisdictions/__init__.py`) sends any name it does not recognize to the fallback pack of the default province, which is Alberta. It has no "outside Alberta" or "not covered" answer.

## Test 2: the same application, only the place changed

`place_parity.py` takes the engine's synthetic sample application (`engine/export/sample.py`: continuous exterior insulation on a Part 9 house, 5 Division B provisions, complete facts, synthetic attachments). It stores the application once per place, setting the place the way the app does, then calls the real API routes: the office lookup, `/gaps`, `/export` (draft and final) and `/submit`.

| Place | Kind | Office the app shows | Same 34 code refs in PDF | Same Section C | Same 8 warnings | Final PDF | Local items | Send to officer in app |
|---|---|---|---|---|---|---|---|---|
| City of Calgary | accredited municipality | own pack: City of Calgary | yes | yes | yes | 200, 45 pages | 2 standing, 1 guide, 1 notice | yes |
| City of Edmonton | accredited municipality | own pack: City of Edmonton | yes | yes | yes | 200, 43 pages | 2 standing, 2 guides | yes |
| City of Red Deer | accredited municipality | "Rest of Alberta" | yes | yes | yes | 200, 43 pages | none | **no** |
| City of Lethbridge | accredited municipality | "Rest of Alberta" | yes | yes | yes | 200, 43 pages | none | **no** |
| Strathcona County | accredited municipality | "Rest of Alberta" | yes | yes | yes | 200, 43 pages | none | **no** |
| Town of Tofield | accredited, joint accreditation | "Rest of Alberta" | yes | yes | yes | 200, 43 pages | none | **no** |
| Lacombe County | Safety Codes Authority | "Rest of Alberta" | yes | yes | yes | 200, 43 pages | none | **no** |
| Kikino Metis Settlement | accredited Métis settlement | "Rest of Alberta" | yes | yes | yes | 200, 43 pages | none | **no** |
| East Prairie Metis Settlement | Safety Codes Authority | "Rest of Alberta" | yes | yes | yes | 200, 43 pages | none | **no** |
| Tsuut'ina Nation | First Nation | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| Municipality of Jasper | national park | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| City of Lloydminster | own charter | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| Vancouver | outside Alberta | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| Toronto | outside Alberta | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| Ottawa | outside Alberta | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| Montréal | outside Alberta | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| Winnipeg | outside Alberta | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |
| Iqaluit | outside Alberta | "Rest of Alberta" (wrong) | yes | yes | yes | 200, 43 pages | none | **no** |

How to read it:

- **The comparisons are not empty.** Every final PDF contains the same 34 code references, from 1.2.1.1.(1) to 9.38.1.1., including the Division C documentation sentences 2.3.1.1.(2) to (4). Every place gets the same 8 warnings from the completeness check. They come from the sample application, not the place: signatures, the professional's sign-off, four evidence-scope questions, emergency response and lapsed maintenance.
- **Calgary's extra 2 pages and 1 gap** come from its local pack: the "Local variance form" appendix, and an information notice that never blocks.
- **Submitting** works only for Calgary and Edmonton. Everywhere else the engine answers 409 with "Choose City of Calgary or City of Edmonton as the reviewing authority before submitting". Reviewer accounts exist only for those two offices (`Authority = Literal['calgary', 'edmonton']` in `engine/account_models.py`).
- **"Same" outside Alberta is a failure, not a success.** Vancouver gets an Alberta application on the Alberta Council form, citing the Alberta code.

Why the drafting cannot differ between Alberta places, from the code:

- Section C comes from `section_c_rows(provision_ids, codes)` (`engine/section_c.py`). It takes only the provision ids and the code database.
- Code identification uses the place only in `fingerprint()` (`engine/identify/case_input.py`), a hash that marks old results as stale. The text it reads (`compose()`) has no place in it.
- Completeness (`engine/completeness.py`) reads the place twice: a gap when no office is chosen, and the office pack's information notices, which never block.

## Test 3: real cases by place (historical run)

`benchmark_by_place.py` splits the only full run of the 653-case Data Prompts benchmark that is still on disk (`.dpe-cache/runs/baseline`, engine commit 8dbf2760, 2026-10-25, Sol judge at low effort, before the integrity repairs) by where each case comes from (`Data Prompts/index.csv`). Every case was matched to a place. The checks are the benchmark's own (`evals_dev/data_prompts/README.md`): facts, review points and article checks (A), plus boundary checks (B), which pass only when the output flags an outside-Alberta record, another discipline or an older edition.

| Place in the case | Cases | Checks | All checks passed | Article found (A) | Flags non-Alberta or other edition (B) | Safety guardrails, all 4 |
|---|---:|---:|---:|---:|---:|---:|
| Calgary | 17 | 161 | 18% | 71% (n=7) | 5% (n=20) | 100% |
| Edmonton | 21 | 233 | 15% | 100% (n=14) | 14% (n=7) | 100% |
| Alberta, other named place (Beaumont, Rocky View County) | 3 | 66 | 17% | 89% (n=9) | 0% (n=1) | 100% |
| Alberta, province-wide | 94 | 787 | 38% | 90% (n=51) | 3% (n=75) | 100% |
| Alberta, place not stated | 24 | 193 | 21% | 83% (n=12) | 7% (n=28) | 100% |
| British Columbia | 71 | 505 | 10% | none | 0% (n=71) | 100% |
| Ontario | 63 | 517 | 9% | none | 0% (n=74) | 100% |
| Saskatchewan | 16 | 88 | 11% | none | 0% (n=16) | 100% |
| Manitoba | 5 | 35 | 9% | none | 0% (n=5) | 100% |
| Quebec | 3 | 21 | 5% | none | 0% (n=3) | 100% |
| Canada, other or national | 75 | 652 | 17% | 100% (n=33) | 0% (n=137) | 100% |
| Outside Canada | 261 | 2,574 | 21% | none | 0% (n=261) | 100% |

The same case type in different places, inside Alberta:

| Case type | Place | Cases | Checks passed | Article found |
|---|---|---:|---:|---:|
| Appeal decision | Calgary | 6 | 16% | none |
| Appeal decision | Edmonton | 2 | 35% | none |
| Appeal decision | Alberta, place not stated | 24 | 21% | 83% (n=12) |
| Appeal decision | Alberta, other named place | 1 | 10% | 0% (n=1) |
| Issued variance | Calgary | 5 | 21% | 71% (n=7) |
| Issued variance | Alberta, province-wide | 61 | 43% | 88% (n=43) |
| Regulatory guidance | Edmonton | 2 | 31% | none |
| Regulatory guidance | Alberta, province-wide | 33 | 29% | 100% (n=8) |
| Documented design study | Calgary | 3 | 11% | none |
| Documented design study | Edmonton | 15 | 9% | 100% (n=13) |

What the numbers say, and what limits them:

- **Inside Alberta, place does not lower the result.** When the article is known, other Alberta cases find it as often as Calgary and Edmonton cases (83% to 90% against 71% and 100%). Within one case type, the spread between places is as large as the spread between cases, and the cells are small (1 to 61 cases).
- **Outside Alberta, the boundary check is 0% in every group (n=567).** In this run the engine never said a case was outside Alberta. That matches Test 1. The safety guardrails still held: no case committed an Alberta article outside Alberta, and no output claimed compliance.
- **Why the totals are low everywhere (15% to 38%).** The judge counts a fact or review point only when the output states it and quotes the report, and many cases ask for facts the input does not contain. The totals compare places with each other; they are not a product accuracy figure, and `docs/accuracy/report.md` says the same of older runs.
- **Limits.** This is one run of an older engine (8dbf2760), with one judge, so it gives no spread between runs. The province-wide group is mostly STANDATA variances and guidance, which are easier than appeals. Test 2 isolates the place, so it is the main evidence for Alberta. This table supports it.

## What would make the other places as good

From the research README's build order, smallest first:

1. **Answer "not covered" outside Alberta and on federal and First Nations land**, instead of falling back to Alberta. That needs a guard in `Registry.resolve` and the place picker, and the boundary data the research found.
2. **Name the office for all 329 Alberta places that get the generic answer.** Generate an office record per place from `alberta-jurisdictions.csv`: the municipality, or the Alberta Safety Codes Authority with its five agencies.
3. **Officer accounts for more offices**: derive `Authority` from office records instead of the two-city literal.
4. **Local packs** where offices publish their own steps: Lethbridge, Medicine Hat, Rocky View County, Airdrie, Chestermere first.

After each step, rerun `place_parity.py`. Step 1 should turn the 90 "wrong" rows into "not covered", and step 2 the 329 into "names the office".

## Rerun

From the repository root, with the git-excluded code database at `codedb/build/codedb.sqlite`:

```sh
.venv/bin/python docs/research/2026-10-28-every-jurisdiction/evidence/place_parity.py
python3 docs/research/2026-10-28-every-jurisdiction/evidence/benchmark_by_place.py /path/to/.dpe-cache/runs/baseline
```

Outputs: `place_parity.json` (705 lookups and 18 full runs) and `benchmark_by_place.json` (the table, the run's settings, and the sha256 of every input: `score-dev-gpt-6.1-sol-low.jsonl` 25a30f88..., `score-holdout-gpt-6.1-sol-low.jsonl` 841c8ea4..., `index.csv` 5c9526e3...). The run cache is git-ignored; on the machine that ran these tests it is in the `data-prompts-eval` worktree. No model or network call is made by either script.
