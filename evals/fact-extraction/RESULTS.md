# Fact extraction metrics

Agent-authored, model-checked, not human-verified. Gold values are spans or direct readings of the pasted text. A field that is empty in both the gold and the prediction is not counted as a true positive.

The shipped extractor is the sentence classifier. The regex baseline keeps every non-question sentence. Word-number storeys and square-foot conversion run only in the classifier. Persona, negation, and cfx scores are in-sample checks of those rules. The held-out pair was written down before either extractor was tuned, and the rules were not changed after this score. cfx-001 through cfx-005 are regression slices of `evals/demo-cases/b-contractor-firestop-nonconformance/input/` at 914b8ec. They are not the held-out set used to pick the winner.

### Without cfx (persona and negation)

| Field | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| applicant_role | 3 | 0 | 0 | 1.000 | 1.000 |
| owner_name | 2 | 0 | 0 | 1.000 | 1.000 |
| municipal_address | 3 | 0 | 0 | 1.000 | 1.000 |
| legal_description | 1 | 0 | 0 | 1.000 | 1.000 |
| permit_number | 1 | 0 | 0 | 1.000 | 1.000 |
| municipality | 3 | 0 | 0 | 1.000 | 1.000 |
| jurisdiction_scope | 2 | 0 | 0 | 1.000 | 1.000 |
| occupancy | 2 | 0 | 0 | 1.000 | 1.000 |
| storeys | 2 | 0 | 0 | 1.000 | 1.000 |
| building_area_m2 | 2 | 0 | 0 | 1.000 | 1.000 |
| dwelling_units | 1 | 0 | 0 | 1.000 | 1.000 |
| sprinklered | 3 | 0 | 0 | 1.000 | 1.000 |
| product_or_assembly | 3 | 0 | 0 | 1.000 | 1.000 |
| installation_status | 3 | 0 | 0 | 1.000 | 1.000 |
| proposed_alternative | 2 | 0 | 0 | 1.000 | 1.000 |
| required_acceptable_solution | 1 | 0 | 0 | 1.000 | 1.000 |
| project_name | 1 | 0 | 0 | 1.000 | 1.000 |
| claimed_exemptions | 1 | 0 | 0 | 1.000 | 1.000 |
| claims | 1 | 0 | 0 | 1.000 | 1.000 |
| evidence_items | 3 | 0 | 0 | 1.000 | 1.000 |
| **micro** | 40 | 0 | 0 | 1.000 | 1.000 |

Micro F1 1.000.

### With cfx (persona, negation, and cfx-001–cfx-005)

| Field | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| applicant_role | 3 | 0 | 0 | 1.000 | 1.000 |
| owner_name | 3 | 0 | 0 | 1.000 | 1.000 |
| municipal_address | 4 | 0 | 0 | 1.000 | 1.000 |
| legal_description | 2 | 0 | 0 | 1.000 | 1.000 |
| permit_number | 2 | 0 | 0 | 1.000 | 1.000 |
| municipality | 4 | 0 | 0 | 1.000 | 1.000 |
| jurisdiction_scope | 3 | 0 | 0 | 1.000 | 1.000 |
| occupancy | 2 | 0 | 0 | 1.000 | 1.000 |
| storeys | 3 | 0 | 0 | 1.000 | 1.000 |
| building_area_m2 | 2 | 0 | 0 | 1.000 | 1.000 |
| dwelling_units | 2 | 0 | 0 | 1.000 | 1.000 |
| sprinklered | 4 | 0 | 0 | 1.000 | 1.000 |
| product_or_assembly | 5 | 0 | 0 | 1.000 | 1.000 |
| installation_status | 4 | 0 | 0 | 1.000 | 1.000 |
| proposed_alternative | 2 | 0 | 0 | 1.000 | 1.000 |
| required_acceptable_solution | 1 | 0 | 0 | 1.000 | 1.000 |
| project_name | 2 | 0 | 0 | 1.000 | 1.000 |
| claimed_exemptions | 3 | 0 | 0 | 1.000 | 1.000 |
| claims | 3 | 0 | 0 | 1.000 | 1.000 |
| evidence_items | 5 | 0 | 0 | 1.000 | 1.000 |
| **micro** | 59 | 0 | 0 | 1.000 | 1.000 |

Micro F1 1.000.

### Held-out, classifier

| Field | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| applicant_role | 1 | 0 | 0 | 1.000 | 1.000 |
| owner_name | 1 | 0 | 0 | 1.000 | 1.000 |
| municipal_address | 1 | 0 | 0 | 1.000 | 1.000 |
| legal_description | 1 | 0 | 0 | 1.000 | 1.000 |
| permit_number | 1 | 0 | 0 | 1.000 | 1.000 |
| municipality | 1 | 0 | 0 | 1.000 | 1.000 |
| jurisdiction_scope | 1 | 0 | 0 | 1.000 | 1.000 |
| occupancy | 2 | 0 | 0 | 1.000 | 1.000 |
| storeys | 2 | 0 | 0 | 1.000 | 1.000 |
| building_area_m2 | 2 | 0 | 0 | 1.000 | 1.000 |
| sprinklered | 2 | 0 | 0 | 1.000 | 1.000 |
| installation_status | 2 | 0 | 0 | 1.000 | 1.000 |
| proposed_alternative | 2 | 0 | 0 | 1.000 | 1.000 |
| required_acceptable_solution | 1 | 0 | 0 | 1.000 | 1.000 |
| evidence_items | 2 | 0 | 0 | 1.000 | 1.000 |
| **micro** | 22 | 0 | 0 | 1.000 | 1.000 |

Micro F1 1.000.

### Held-out, regex

| Field | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| applicant_role | 1 | 0 | 0 | 1.000 | 1.000 |
| owner_name | 1 | 0 | 0 | 1.000 | 1.000 |
| municipal_address | 1 | 0 | 0 | 1.000 | 1.000 |
| legal_description | 1 | 0 | 0 | 1.000 | 1.000 |
| permit_number | 1 | 0 | 0 | 1.000 | 1.000 |
| municipality | 1 | 0 | 0 | 1.000 | 1.000 |
| jurisdiction_scope | 1 | 0 | 0 | 1.000 | 1.000 |
| occupancy | 2 | 0 | 0 | 1.000 | 1.000 |
| storeys | 2 | 0 | 0 | 1.000 | 1.000 |
| building_area_m2 | 2 | 0 | 0 | 1.000 | 1.000 |
| sprinklered | 2 | 0 | 0 | 1.000 | 1.000 |
| installation_status | 2 | 0 | 0 | 1.000 | 1.000 |
| proposed_alternative | 0 | 2 | 2 | 0.000 | 0.000 |
| required_acceptable_solution | 1 | 0 | 0 | 1.000 | 1.000 |
| evidence_items | 2 | 0 | 0 | 1.000 | 1.000 |
| **micro** | 20 | 2 | 2 | 0.909 | 0.909 |

Micro F1 0.909.

Departure-only rate without cfx: 4/4.
Departure-only rate with cfx: 9/9.
Held-out departure-only, classifier: 2/2.
Held-out departure-only, regex: 0/2.

Winner: **classifier**. Chosen on held-out micro F1, then held-out departure-only rate.

Approach check (not in the tables above): "two-storey" and "2,000 sq ft". Classifier reads storeys 2 and area 185.81. Regex reads storeys None and area None.

cfx-005 records the exemption as applicant_asserted, asks for evidence, and opens an officer gap. It does not answer the exemption. The speaker on that slice is the words in the slice (`The sub`). cfx-004 lists the evidence as listed_not_reviewed with the label `evidence_listed (not reviewed)` and the missing items signature, tested system, job name and location, and issuer qualifications. The route asks for an EJ from a qualified issuer. The officer decides.
