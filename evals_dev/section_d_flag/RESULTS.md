# Section D development and model-constructed fixture receipt

Source commit: `99a376c68ffb2d58847076796a27ad95f2712a2a`. Generated: 2026-10-20T23:24:39.098663+00:00. The receipt commit may add these files; code/input hashes in metrics.json identify the measured source.

**In-sample, model-checked, not human-verified.** The 60 text-only development cases and 11 model-constructed no-ground-truth cases are already development fixtures. This is not blind, external, professional, or production evidence. Zero under-flags on the text-only set follows the shipped yes/ask behavior; it is not an observed real-world safety rate.

The receipt generator loaded only dev-*.json and ngt-*.json. Sealed/external holdouts were not read or rescored. The historical 7/8 pre-fix and 4/8 post-fix claims are outside this receipt. No paid provider calls, source changes, or classifier tuning occurred.

Separate regression verification passed eight existing tests. One headline-output test also reads the already committed eight-case legacy post-fix fixture set; those cases are no longer blind. That regression run does not add a held-out measurement to this receipt.

Reproduce from this source with the existing CodeDB built from the repository corpus:

```sh
python - <<'PY'
from pathlib import Path
from engine.section_d_flag_eval import load_codes, load_cases, load_ngt, score, report, ngt_report
from engine.section_d_issues import citation_resolution
codes, status = load_codes(Path('codedb/build/codedb.sqlite'))
assert status != 'missing'
dev = load_cases()
print(report(score(codes, dev), status))
print(ngt_report(score(codes, load_ngt())))
print('citation_resolution:', *citation_resolution(dev, codes))
PY
```

Lookup resolution below proves citation linkage only, not technical/legal correctness or approval. SHA256 input, source and private-CodeDB fingerprints plus raw confusion matrices are in metrics.json; private corpus/form bytes are not committed.

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
ngt rules_only: 10/11 correct, under-flags 0, over-flags 0, no 8, unknown 1 | model-constructed, model-checked, not human-verified
ngt misses rules_only: ngt-103 gold=yes system=depends | model-constructed, model-checked, not human-verified
ngt rules_plus_unknown: 10/11 correct, under-flags 0, over-flags 0, no 8, unknown 1 | model-constructed, model-checked, not human-verified
ngt misses rules_plus_unknown: ngt-103 gold=yes system=unknown | model-constructed, model-checked, not human-verified
ngt rules_plus_unknown_cf: 10/11 correct, under-flags 0, over-flags 0, no 8, unknown 1 | model-constructed, model-checked, not human-verified
ngt misses rules_plus_unknown_cf: ngt-103 gold=yes system=unknown | model-constructed, model-checked, not human-verified
ngt always_unknown: 0/11 correct, under-flags 0, over-flags 0, no 0, unknown 11 | model-constructed, model-checked, not human-verified
ngt misses always_unknown: ngt-001 gold=no system=unknown, ngt-002 gold=no system=unknown, ngt-003 gold=no system=unknown, ngt-004 gold=no system=unknown, ngt-005 gold=no system=unknown, ngt-006 gold=no system=unknown, ngt-007 gold=no system=unknown, ngt-008 gold=no system=unknown, ngt-101 gold=yes system=unknown, ngt-102 gold=yes system=unknown, ngt-103 gold=yes system=unknown | model-constructed, model-checked, not human-verified

citation_resolution: 56/56
```
