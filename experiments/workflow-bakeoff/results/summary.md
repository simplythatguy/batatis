| workflow | balanced quality | balanced questions | quality / question | path match | fabricated prompts | eligible |
|---|---:|---:|---:|---:|---:|---|
| BEFORE | 8.513 | 20.53 | 0.415 | 0.553 | 0 | True |
| FLOWCHART | 7.709 | 14.72 | 0.524 | 0.401 | 0 | True |
| FLOWCHART+LOOKUP | 8.709 | 10.98 | 0.793 | 0.401 | 0 | True |
| AFTER | 9.739 | 13.02 | 0.748 | 0.921 | 0 | True |

Winner by the frozen rule: AFTER
Inter-run max |Δ quality| = 0, |Δ questions| = 0. n = 152.

| workflow | application quality | rule quality | application questions | rule questions | redundant | fails |
|---|---:|---:|---:|---:|---:|---|
| BEFORE | 9.206 | 7.820 | 18.84 | 22.22 | 6.01 | admin_review 1, evidence_matches_path 87, no_judgment 1, path 68, process_fields 87 |
| FLOWCHART | 7.778 | 7.640 | 20.84 | 8.61 | 4.72 | evidence_matches_path 35, no_code_quiz 152, path 91, process_fields 72 |
| FLOWCHART+LOOKUP | 8.778 | 8.640 | 16.41 | 5.54 | 1.09 | evidence_matches_path 35, path 91, process_fields 72 |
| AFTER | 9.524 | 9.955 | 10.24 | 15.81 | 0.74 | evidence_matches_path 11, path 12, process_fields 11 |
