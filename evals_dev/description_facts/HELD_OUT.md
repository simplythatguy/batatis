# Held-out description check

Agent-labelled, not human-verified. These five texts were not in the 38-description tuning set. Gold facts are only numbers and occupancy words written in the text. `alternative_description` gold is the non-question remainder under the published rule (a sentence with `?`, or one that starts with what/how/why/when/where/which/who, is left out).

| id | source |
| --- | --- |
| script-c-homebuilder | PR #20 `docs/demo/script.md`, Case C homebuilder paste |
| script-a-manufacturer | PR #20 `docs/demo/script.md`, Case A manufacturer paste |
| brief-a-manufacturer | PR #14 `evals/demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.md` |
| brief-b-contractor | PR #14 `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md` |
| brief-c-homebuilder | PR #14 `evals/demo-cases/c-homebuilder-infill-house/input/project-brief.md` |

## Scores

| variant | field | precision | recall | tp | fp | fn | f1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| regex | storeys | 1.0000 | 0.7500 | 3 | 0 | 1 |  |
| regex | building_area_m2 | 1.0000 | 0.6667 | 2 | 0 | 1 |  |
| regex | span_m | 1.0000 | 1.0000 | 0 | 0 | 0 |  |
| regex | occupancy | 0.5000 | 0.5000 | 1 | 1 | 1 |  |
| regex | alternative_description | 1.0000 | 1.0000 | 5 | 0 | 0 |  |
| regex | micro | 0.9167 | 0.7857 | 11 | 1 | 3 | 0.8462 |
| normalised | storeys | 1.0000 | 0.7500 | 3 | 0 | 1 |  |
| normalised | building_area_m2 | 1.0000 | 0.6667 | 2 | 0 | 1 |  |
| normalised | span_m | 1.0000 | 1.0000 | 0 | 0 | 0 |  |
| normalised | occupancy | 0.5000 | 0.5000 | 1 | 1 | 1 |  |
| normalised | alternative_description | 1.0000 | 1.0000 | 5 | 0 | 0 |  |
| normalised | micro | 0.9167 | 0.7857 | 11 | 1 | 3 | 0.8462 |

## Misses

### regex

- `brief-a-manufacturer` `storeys`: gold 2, predicted null
- `brief-a-manufacturer` `building_area_m2`: gold 190, predicted null
- `brief-a-manufacturer` `occupancy`: gold "single_family", predicted "industrial"

### normalised

- `brief-a-manufacturer` `storeys`: gold 2, predicted null
- `brief-a-manufacturer` `building_area_m2`: gold 190, predicted null
- `brief-a-manufacturer` `occupancy`: gold "single_family", predicted "industrial"

Both variants miss the same three facts on the manufacturer brief. The pilot-house row (`2-storey`, `single-family`, `about 190 m²`) sits in a markdown sentence that also contains `housewrap?`, so the question rule drops it. `factory-bonded` is then read as industrial occupancy. The two script pastes and the homebuilder brief match the literal gold. The contractor brief matches the written `5 storeys` and does not invent area, span, or an occupancy category.

```json
{
  "reports": {
    "regex": {
      "storeys": {
        "precision": 1.0,
        "recall": 0.75,
        "tp": 3,
        "fp": 0,
        "fn": 1
      },
      "building_area_m2": {
        "precision": 1.0,
        "recall": 0.6667,
        "tp": 2,
        "fp": 0,
        "fn": 1
      },
      "span_m": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 0,
        "fp": 0,
        "fn": 0
      },
      "occupancy": {
        "precision": 0.5,
        "recall": 0.5,
        "tp": 1,
        "fp": 1,
        "fn": 1
      },
      "alternative_description": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 5,
        "fp": 0,
        "fn": 0
      },
      "micro": {
        "precision": 0.9167,
        "recall": 0.7857,
        "tp": 11,
        "fp": 1,
        "fn": 3,
        "f1": 0.8462
      }
    },
    "normalised": {
      "storeys": {
        "precision": 1.0,
        "recall": 0.75,
        "tp": 3,
        "fp": 0,
        "fn": 1
      },
      "building_area_m2": {
        "precision": 1.0,
        "recall": 0.6667,
        "tp": 2,
        "fp": 0,
        "fn": 1
      },
      "span_m": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 0,
        "fp": 0,
        "fn": 0
      },
      "occupancy": {
        "precision": 0.5,
        "recall": 0.5,
        "tp": 1,
        "fp": 1,
        "fn": 1
      },
      "alternative_description": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 5,
        "fp": 0,
        "fn": 0
      },
      "micro": {
        "precision": 0.9167,
        "recall": 0.7857,
        "tp": 11,
        "fp": 1,
        "fn": 3,
        "f1": 0.8462
      }
    }
  },
  "misses": {
    "regex": [
      {
        "id": "brief-a-manufacturer",
        "field": "storeys",
        "gold": 2,
        "predicted": null
      },
      {
        "id": "brief-a-manufacturer",
        "field": "building_area_m2",
        "gold": 190,
        "predicted": null
      },
      {
        "id": "brief-a-manufacturer",
        "field": "occupancy",
        "gold": "single_family",
        "predicted": "industrial"
      }
    ],
    "normalised": [
      {
        "id": "brief-a-manufacturer",
        "field": "storeys",
        "gold": 2,
        "predicted": null
      },
      {
        "id": "brief-a-manufacturer",
        "field": "building_area_m2",
        "gold": 190,
        "predicted": null
      },
      {
        "id": "brief-a-manufacturer",
        "field": "occupancy",
        "gold": "single_family",
        "predicted": "industrial"
      }
    ]
  }
}
```
