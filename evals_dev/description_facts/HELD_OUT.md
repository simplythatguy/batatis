# Description check on the five demo texts

Agent-labelled, not human-verified. These five texts were not in the 38-description tuning set. Fact gold is only numbers and occupancy words written in the text.

| id | source |
| --- | --- |
| script-c-homebuilder | PR #20 `docs/demo/script.md`, Case C homebuilder paste |
| script-a-manufacturer | PR #20 `docs/demo/script.md`, Case A manufacturer paste |
| brief-a-manufacturer | PR #14 `evals/demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.md` |
| brief-b-contractor | PR #14 `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md` |
| brief-c-homebuilder | PR #14 `evals/demo-cases/c-homebuilder-infill-house/input/project-brief.md` |

## held-out, first run, agent-labelled

This block is the first blind run, before these texts were used to change the extractor. Do not replace it with a later score. `alternative_description` gold on that run was the non-question remainder under the old rule (a whole sentence with `?`, or one that starts with what/how/why/when/where/which/who, was left out).

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

### Misses on that run

Both variants missed the same three facts on the manufacturer brief. The pilot-house row (`2-storey`, `single-family`, `about 190 m²`) sat in a markdown stretch that also contained `housewrap?`, so the question rule dropped the row. `factory-bonded` was then read as industrial occupancy. The two script pastes and the homebuilder brief matched the literal gold. The contractor brief matched the written `5 storeys` and did not invent area, span, or an occupancy category.

- `brief-a-manufacturer` `storeys`: gold 2, predicted null
- `brief-a-manufacturer` `building_area_m2`: gold 190, predicted null
- `brief-a-manufacturer` `occupancy`: gold "single_family", predicted "industrial"

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

## post-fix, no longer blind

The clause rule and the occupancy rule were changed because of these five texts. This score is not held-out. Fact gold is the same literal labels as the first run. `alternative_description` for `brief-a-manufacturer` was relabelled to the clause-rule remainder, so that field is not a blind score. The other four alternative strings were unchanged.

A `?` now drops only that clause. Splits are sentence ends, line breaks, and `;` or `—`. `factory-bonded` is a product word and does not set occupancy. One residential building-use category wins over another category; two residential categories, or two non-residential categories, stay empty.

| variant | field | precision | recall | tp | fp | fn | f1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| regex | storeys | 1.0000 | 1.0000 | 4 | 0 | 0 |  |
| regex | building_area_m2 | 1.0000 | 1.0000 | 3 | 0 | 0 |  |
| regex | span_m | 1.0000 | 1.0000 | 0 | 0 | 0 |  |
| regex | occupancy | 1.0000 | 1.0000 | 2 | 0 | 0 |  |
| regex | alternative_description | 1.0000 | 1.0000 | 5 | 0 | 0 |  |
| regex | micro | 1.0000 | 1.0000 | 14 | 0 | 0 | 1.0000 |
| normalised | storeys | 1.0000 | 1.0000 | 4 | 0 | 0 |  |
| normalised | building_area_m2 | 1.0000 | 1.0000 | 3 | 0 | 0 |  |
| normalised | span_m | 1.0000 | 1.0000 | 0 | 0 | 0 |  |
| normalised | occupancy | 1.0000 | 1.0000 | 2 | 0 | 0 |  |
| normalised | alternative_description | 1.0000 | 1.0000 | 5 | 0 | 0 |  |
| normalised | micro | 1.0000 | 1.0000 | 14 | 0 | 0 | 1.0000 |

No fact misses remain. The micro score counts the relabelled alternative string, so 14/0/0 is not a blind result.

```json
{
  "reports": {
    "regex": {
      "storeys": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 4,
        "fp": 0,
        "fn": 0
      },
      "building_area_m2": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 3,
        "fp": 0,
        "fn": 0
      },
      "span_m": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 0,
        "fp": 0,
        "fn": 0
      },
      "occupancy": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 2,
        "fp": 0,
        "fn": 0
      },
      "alternative_description": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 5,
        "fp": 0,
        "fn": 0
      },
      "micro": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 14,
        "fp": 0,
        "fn": 0,
        "f1": 1.0
      }
    },
    "normalised": {
      "storeys": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 4,
        "fp": 0,
        "fn": 0
      },
      "building_area_m2": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 3,
        "fp": 0,
        "fn": 0
      },
      "span_m": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 0,
        "fp": 0,
        "fn": 0
      },
      "occupancy": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 2,
        "fp": 0,
        "fn": 0
      },
      "alternative_description": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 5,
        "fp": 0,
        "fn": 0
      },
      "micro": {
        "precision": 1.0,
        "recall": 1.0,
        "tp": 14,
        "fp": 0,
        "fn": 0,
        "f1": 1.0
      }
    }
  },
  "misses": {
    "regex": [],
    "normalised": []
  }
}
```
