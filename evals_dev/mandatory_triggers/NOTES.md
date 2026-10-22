# Mandatory-trigger cases

Label: **model-checked, not human-verified**.

Source: Data Nerd, `mandatory-triggers-tests.json`, built 2026-10-20 (America/Edmonton) by `research/src/mtt_build.py` for Karen's rubric gap #5. That file checked every code quote as a substring of NBC(AE) 2023, 2nd printing, and the Safety Codes Act quotes against page 31 of the Act PDF. `cases.json` keeps the 12 tests (one fire and one near-miss for HR-02, HR-05, HR-06, HR-07, HR-30, and HR-32). It does not copy the code quotations.

## Caveats

- HR-05a is a synthetic boundary value (no listed Alberta location reaches 1.2 kPa).
- HR-06's Part 4 link via Div C 2.4.1.2.(1) is Data Nerd's inference. The same sentence is the lookup gate for HR-05 and HR-07. The shipped row cites the Division B sentence that sends the work to Part 4. The Div C sentence has to resolve or that row is omitted. It is not scored as a second cite.
- HR-30 and HR-32 are discretionary decisions where routing is required, so the engine routes and never decides. HR-32 stays off the human-review list. A 3.8 provision sets `routed_to` officer and does not push yes.

## How a case is scored

The shipped screen is `section_d_issues` on a case built from `input_facts`. An unset pathway stays on the alternative path, so a site variance row can appear beside another trigger. That extra row does not by itself fail HR-05, HR-06, or HR-07.

- HR-05, HR-06, HR-07 fire: the trigger id is present, its Division B provision is in that row's cite, the practice value is true, and the status is `needs_professional`.
- Those near-misses: the trigger id is absent, and the practice value is not true.
- HR-02 stays off the shipped list (mixed). The fire passes only when both Div C 2.4.1.1.(3) and Div C 2.4.2.2.(1) are cited and the status is `needs_professional`. The near-miss passes when neither the schedules sentence nor an HR-02 row is present.
- HR-30 fire: the statute cite is present, `routed_to` is officer, and the practice value is unknown. The near-miss (province-wide) passes only when Div C 2.2.1.2.(1) is cited and the site variance row is absent.
- HR-32 fire: `routed_to` is officer and the practice value is unknown. The near-miss passes when HR-32 is absent and the site variance cite is present.

`must_not` is separate. It fails on a compliance verdict, an officer-side yes or no, or `needs_professional` closed without a confirmed engineer or architect plus a seal or registration number.

## Measured on the shipped screen

Run: `python3 -m evals_dev.mandatory_triggers.score`. The screen was not retuned. Outcome 10/12. `must_not` 12/12.

| Trigger | Fire | Near-miss |
| --- | --- | --- |
| HR-02 | fail (2.4.2.2.(1) is not cited; HR-02 stays off the list) | pass |
| HR-05 | pass | pass |
| HR-06 | pass | pass |
| HR-07 | pass | pass |
| HR-30 | pass | fail (province-wide still gets the site row; 2.2.1.2.(1) is not cited) |
| HR-32 | pass | pass |

The two outcome misses still route and do not decide. `must_not` holds on both.
