# Section D development and model-constructed fixture receipt

Measured source commit: `d479e825487eb1c12efbfe469100fbf34ce90672`. Generated: 2026-10-21T00:40:41.360377+00:00. A later receipt commit changes only `RESULTS.md` and `metrics.json`; the six declared source files, all 17 imported engine/CodeDB Python modules and all 71 input hashes must remain byte-identical to this measured commit.

**In-sample, model-checked, not human-verified.** The 60 text-only development cases and 11 model-constructed no-ground-truth cases are development fixtures. Their model-supplied gold labels are not expert ground truth. Agreement and Wilson intervals below describe these fixed fixtures; they do not establish population accuracy, real-world safety, compliance, technical equivalence or professional approval.

The shipped `rules_plus_unknown` agrees on **50/60 dev cases** and **8/11 model-constructed cases**. The latter has **8 no outputs and 3 unknowns**: `ngt-101`, `ngt-102`, `ngt-103` are gold-yes misses/abstentions. Under-flag means **gold yes → system no only**. Gold yes → unknown/depends is a miss/abstention, not an under-flag. Zero under-flags is not full agreement. On dev the shipped variant produces no no answers, so its zero under-flags follows its yes/ask behavior.

| Population (in-sample, model-checked, not human-verified) | Variant | Agreement [95% Wilson] | Under | Over | No | Unknown | Skipped |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| dev60 | `rules_only` | 55/60 [0.8193, 0.9639] | 1 | 0 | 15 | 13 | 0 |
| dev60 | `rules_plus_unknown` | 50/60 [0.7197, 0.9069] | 0 | 0 | 0 | 27 | 0 |
| dev60 | `rules_plus_unknown_cf` | 50/60 [0.7197, 0.9069] | 0 | 0 | 0 | 27 | 0 |
| dev60 | `always_unknown` | 17/60 [0.1851, 0.4077] | 0 | 0 | 0 | 60 | 0 |
| model-constructed no-GT11 | `rules_only` | 8/11 [0.4344, 0.9025] | 0 | 0 | 8 | 3 | 0 |
| model-constructed no-GT11 | `rules_plus_unknown` | 8/11 [0.4344, 0.9025] | 0 | 0 | 8 | 3 | 0 |
| model-constructed no-GT11 | `rules_plus_unknown_cf` | 8/11 [0.4344, 0.9025] | 0 | 0 | 8 | 3 | 0 |
| model-constructed no-GT11 | `always_unknown` | 0/11 [0.0000, 0.2588] | 0 | 0 | 0 | 11 | 0 |

The prior measurement at `99a376c68ffb2d58847076796a27ad95f2712a2a`, delivered in receipt `5b34ab6e974ae9d5908edd0bafc622c3f91e2f9c`, is **historical**. Its first three no-GT variants had 10/11 agreement and one unknown. At the current source, `ngt-101` and `ngt-102` also abstain; their model-gold yes labels are unchanged. The dev counts are unchanged, but the old source hashes are stale. The only input-byte changes since that historical measurement are the authorized `ngt-007`/`ngt-008` reason and authoring-note corrections; engineering-required gold labels are unchanged.

**Historical legacy claims only, not renewed:** 7/8 pre-fix and 4/8 post-fix (no longer blind). No legacy eight-case, sealed, external, appeals or protected benchmark target was opened, inventoried or scored for this receipt. The old eight-regression-test statement is not a current independent test result. No eval main/headline, default fixture loader, heldout loader, model runner, paid provider call or classifier/gold edit was used.

The flag measurement calls the existing facts-only heuristic through `score(codes, explicit_cases)` and a separate `evaluate()` accounting pass. It does not exercise the full Case/API/export or file-ownership behavior. Citation resolution uses seed provisions in otherwise empty Cases and verifies unique citation bindings; **56/56 is linkage only**, not factual applicability, legal/technical correctness or approval.

Reproduction uses only the exact 71 input paths listed in `metrics.json`, never directory globs. Each of the eight dataclass records, including every matrix cell, miss, gold-yes abstention, under-flag explanation and skipped count, matches independent accounting. Forty independent Wilson calculations agree within 1e-14. `metrics.json` contains all records, intervals, six declared source hashes, 17 runtime-module hashes, 71 input hashes and the private CodeDB fingerprint. Private corpus/form bytes are not committed.

The audited local command was:

```sh
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  /tmp/batatis-deploy-venv-20261020/bin/python -I -B \
  /tmp/batatis-sectiond-receipt-r2-20261020.evidence/offline.py measure-d479 \
  /tmp/batatis-sectiond-receipt-r2-20261020.evidence/reproduce.py
```

The external evidence directory contains the copied immutable prior runner, adapted runner, exact allowlist, sanitized launch receipt, full predictions/accounting/output, source provenance and access audit. Application environment is replaced, HOME is empty, provider/credential imports and dotenv/keychain resolution are blocked, network/subprocesses and checkout writes are denied, and every SQLite connection is explicitly `mode=ro`. The audit records 71 unique allowed inputs, zero fixture-directory scans, zero prohibited accesses or network attempts, and 15,479 read-only connections to the actual authorized private CodeDB. No PostgreSQL, deployment, billing reconciliation or key activation was needed. The historical US$2.21 token estimate is not a billing receipt and is outside this numerical scope.

Complete existing report output follows. Its `correct` label means agreement with model gold. Any printed appeals path names a non-run source constant; it does not record a dataset access. All output remains **in-sample, model-checked, not human-verified**.

```text
variant                scored              agreement under_flag unknown skipped
note: rules_only abstains with depends; that label is counted in the unknown column
rules_only                 60 55/60 [0.8193, 0.9639]          1      13       0
unknown_rate rules_only: 13/60 [0.1312, 0.3362]
confident_wrong rules_only: 5/60 [0.0361, 0.1807]
confusion rules_only  rows=gold  columns=system yes unknown no
  yes      32    0    1
  depends   0   13    4
  no        0    0   10
gold_yes_as_unknown rules_only: none
under_flag rules_only: dev-050: occupancy=single_family; part4_design=false; span_m=18; rules_only does not apply the 12.20 m span, so part4_design stays false
over_flag rules_only: 0 (gold no, system yes)
dev rules_only: 55/60 correct, under-flags 1, over-flags 0, no 15, unknown 13
rules_plus_unknown         60 50/60 [0.7197, 0.9069]          0      27       0
unknown_rate rules_plus_unknown: 27/60 [0.3309, 0.5751]
confident_wrong rules_plus_unknown: 0/60 [0.0000, 0.0602]
confusion rules_plus_unknown  rows=gold  columns=system yes unknown no
  yes      33    0    0
  depends   0   17    0
  no        0   10    0
gold_yes_as_unknown rules_plus_unknown: none
under_flag rules_plus_unknown: none
over_flag rules_plus_unknown: 0 (gold no, system yes)
dev rules_plus_unknown: 50/60 correct, under-flags 0, over-flags 0, no 0, unknown 27
rules_plus_unknown_cf      60 50/60 [0.7197, 0.9069]          0      27       0
unknown_rate rules_plus_unknown_cf: 27/60 [0.3309, 0.5751]
confident_wrong rules_plus_unknown_cf: 0/60 [0.0000, 0.0602]
confusion rules_plus_unknown_cf  rows=gold  columns=system yes unknown no
  yes      33    0    0
  depends   0   17    0
  no        0   10    0
gold_yes_as_unknown rules_plus_unknown_cf: none
under_flag rules_plus_unknown_cf: none
over_flag rules_plus_unknown_cf: 0 (gold no, system yes)
dev rules_plus_unknown_cf: 50/60 correct, under-flags 0, over-flags 0, no 0, unknown 27
always_unknown             60 17/60 [0.1851, 0.4077]          0      60       0
unknown_rate always_unknown: 60/60 [0.9398, 1.0]
confident_wrong always_unknown: 0/60 [0.0000, 0.0602]
confusion always_unknown  rows=gold  columns=system yes unknown no
  yes       0   33    0
  depends   0   17    0
  no        0   10    0
gold_yes_as_unknown always_unknown: dev-002, dev-003, dev-013, dev-014, dev-016, dev-017, dev-018, dev-019, dev-026, dev-027, dev-028, dev-029, dev-030, dev-031, dev-032, dev-033, dev-034, dev-035, dev-036, dev-037, dev-038, dev-039, dev-040, dev-041, dev-042, dev-043, dev-044, dev-045, dev-046, dev-047, dev-050, dev-056, dev-058
under_flag always_unknown: none
over_flag always_unknown: 0 (gold no, system yes)
dev always_unknown: 17/60 correct, under-flags 0, over-flags 0, no 0, unknown 60
rules_plus_unknown on this dev table is in-sample and pending out-of-sample confirmation
winner: rules_plus_unknown
under_flag_target: 0
gold: model-checked
split: dev (in-sample; pending out-of-sample confirmation)
out_of_sample: evals_dev/appeals (built on another branch; not scored here)
codedb: present
scored: 60
skipped: 0

ngt-set: evals/fixtures/section_d_no_gt | model-constructed, model-checked, not human-verified
ngt-set tuning: in-sample once tuned against these cases | model-constructed, model-checked, not human-verified
ngt rules_only: 8/11 correct, under-flags 0, over-flags 0, no 8, unknown 3 | model-constructed, model-checked, not human-verified
ngt misses rules_only: ngt-101 gold=yes system=depends, ngt-102 gold=yes system=depends, ngt-103 gold=yes system=depends | model-constructed, model-checked, not human-verified
ngt rules_plus_unknown: 8/11 correct, under-flags 0, over-flags 0, no 8, unknown 3 | model-constructed, model-checked, not human-verified
ngt misses rules_plus_unknown: ngt-101 gold=yes system=unknown, ngt-102 gold=yes system=unknown, ngt-103 gold=yes system=unknown | model-constructed, model-checked, not human-verified
ngt rules_plus_unknown_cf: 8/11 correct, under-flags 0, over-flags 0, no 8, unknown 3 | model-constructed, model-checked, not human-verified
ngt misses rules_plus_unknown_cf: ngt-101 gold=yes system=unknown, ngt-102 gold=yes system=unknown, ngt-103 gold=yes system=unknown | model-constructed, model-checked, not human-verified
ngt always_unknown: 0/11 correct, under-flags 0, over-flags 0, no 0, unknown 11 | model-constructed, model-checked, not human-verified
ngt misses always_unknown: ngt-001 gold=no system=unknown, ngt-002 gold=no system=unknown, ngt-003 gold=no system=unknown, ngt-004 gold=no system=unknown, ngt-005 gold=no system=unknown, ngt-006 gold=no system=unknown, ngt-007 gold=no system=unknown, ngt-008 gold=no system=unknown, ngt-101 gold=yes system=unknown, ngt-102 gold=yes system=unknown, ngt-103 gold=yes system=unknown | model-constructed, model-checked, not human-verified

citation_resolution: 56/56
```
