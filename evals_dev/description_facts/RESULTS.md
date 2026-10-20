# Description extractor comparison

Synthetic, in-sample labels in `labelled.json` (38 descriptions). Gold is the fact a person would confirm from the wording. Null against null is ignored. Area and span match within 0.02. This set was written for these two extractors; it is not a held-out filing.

Production extractor: `normalised` (`engine.description_facts.WINNER`). It folds number words, hyphens, thousands separators, and square feet or feet into metres. The regex variant keeps metric digits only.

| variant | field | precision | recall | tp | fp | fn | f1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| regex | storeys | 1.0000 | 1.0000 | 23 | 0 | 0 |  |
| regex | building_area_m2 | 1.0000 | 0.8824 | 15 | 0 | 2 |  |
| regex | span_m | 1.0000 | 0.7143 | 5 | 0 | 2 |  |
| regex | occupancy | 1.0000 | 1.0000 | 27 | 0 | 0 |  |
| regex | alternative_description | 1.0000 | 1.0000 | 35 | 0 | 0 |  |
| regex | micro | 1.0000 | 0.9633 | 105 | 0 | 4 | 0.9813 |
| normalised | storeys | 1.0000 | 1.0000 | 23 | 0 | 0 |  |
| normalised | building_area_m2 | 1.0000 | 1.0000 | 17 | 0 | 0 |  |
| normalised | span_m | 1.0000 | 1.0000 | 7 | 0 | 0 |  |
| normalised | occupancy | 1.0000 | 1.0000 | 27 | 0 | 0 |  |
| normalised | alternative_description | 1.0000 | 1.0000 | 35 | 0 | 0 |  |
| normalised | micro | 1.0000 | 1.0000 | 109 | 0 | 0 | 1.0000 |

```json
{
  "regex": {
    "storeys": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 23,
      "fp": 0,
      "fn": 0
    },
    "building_area_m2": {
      "precision": 1.0,
      "recall": 0.8824,
      "tp": 15,
      "fp": 0,
      "fn": 2
    },
    "span_m": {
      "precision": 1.0,
      "recall": 0.7143,
      "tp": 5,
      "fp": 0,
      "fn": 2
    },
    "occupancy": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 27,
      "fp": 0,
      "fn": 0
    },
    "alternative_description": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 35,
      "fp": 0,
      "fn": 0
    },
    "micro": {
      "precision": 1.0,
      "recall": 0.9633,
      "tp": 105,
      "fp": 0,
      "fn": 4,
      "f1": 0.9813
    }
  },
  "normalised": {
    "storeys": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 23,
      "fp": 0,
      "fn": 0
    },
    "building_area_m2": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 17,
      "fp": 0,
      "fn": 0
    },
    "span_m": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 7,
      "fp": 0,
      "fn": 0
    },
    "occupancy": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 27,
      "fp": 0,
      "fn": 0
    },
    "alternative_description": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 35,
      "fp": 0,
      "fn": 0
    },
    "micro": {
      "precision": 1.0,
      "recall": 1.0,
      "tp": 109,
      "fp": 0,
      "fn": 0,
      "f1": 1.0
    }
  }
}
```
