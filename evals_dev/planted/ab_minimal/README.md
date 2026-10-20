# Constructed missing-field fixtures

These 10 files are constructed synthetic Part 1 A/B applications. Each JSON header
sets `"constructed": true`. They are not model gold labels and not a human key.
Ground truth is `removed_fields`.

`python evals_dev/deterministic_checks.py` prints `fixtures: constructed` for this set.

- `ab-clean.json` (clean control)
- `ab-missing-alternative_description.json`
- `ab-missing-application_date.json`
- `ab-missing-civic_address.json`
- `ab-missing-legal_description.json`
- `ab-missing-mailing_address.json`
- `ab-missing-owner_name-and-mailing_address.json`
- `ab-missing-owner_name.json`
- `ab-missing-representative.json`
- `ab-missing-scope.json`
