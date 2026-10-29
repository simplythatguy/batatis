# Jurisdiction packs

A jurisdiction pack says where an application goes and what that office has published: the
authority, process notes, forms, standing packages, guides and notices. Packs are data, not code.
Adding an office is adding one JSON file; no engine code changes.

A pack never says a design complies. A standing package, a guide or a checklist is never a
determination; the safety codes officer decides.

## Files

| Path | Model (`engine/models_jurisdictions.py`) | What it holds |
|---|---|---|
| `engine/data/jurisdictions/packs/<id>.json` | `JurisdictionPack` | One office. The file name is the pack id. |
| `engine/data/jurisdictions/provinces/<XX>.json` | `ProvinceShared` | Items every pack in the province shares: the SCC variance form, SCC information bulletins, province-wide process notes. |
| `engine/data/jurisdictions/coverage.json` | `CoverageFile` | Coverage label for every province and territory, the label meanings, and `default_province`. |
| `engine/data/jurisdictions/places/<group>.json` | `PlacesFile` | Generated places: `alberta.json` (390 rows of the research table plus Maskwacis and Stoney Nakoda) and `outside-alberta.json` (12 provinces and territories, 31 cities). Each place names the office that reviews building work there, with sources. |
| `engine/data/jurisdictions/place_inputs.json` | input | Hand-entered facts the generator adds: park and airport names, places outside Alberta with their code and source, everyday names (First Nations, Fort McMurray, Sherwood Park). |
| `engine/data/jurisdictions/place_index.json` | generated | The compact list the web picker reads (`web/src/config.ts`). |
| `engine/data/jurisdictions/pack.schema.json` | generated | JSON Schema for the four file kinds. Every object has `additionalProperties: false`. |

Regenerate the schema after a model change: `python -m engine.jurisdictions.schema`
(`--check` exits 1 when it is stale; `test_jurisdictions_schema.py` runs the check). Regenerate the places after a
research or input change: `python -m engine.jurisdictions.places_build` (`--check` exits 1 when a committed file
differs; `test_every_place.py` runs the check).

`BATATIS_JURISDICTIONS_DIR` points the loader at another directory with the same layout. Tests use
it to add a synthetic fourth pack.

### Packs today

| Pack | Coverage | Authority | Local forms | Standing packages | Guides | Notices |
|---|---|---|---|---|---|---|
| `calgary` | full | City of Calgary (reviewer code `calgary`) | Request for Specific Variance, R2014-06 (export not yet) | SPV-001 (Rev. 5, 2026-03-05), SPV-006 (2025-06-19) | Guide to Applying for an Alternative Solution (2023-11-23) | `calgary_variance_form` (from PR #40) |
| `edmonton` | full | City of Edmonton (reviewer code `edmonton`) | none found | B23-01 (2024-07-30), B14-01 **historical** (cites ABC 2014) | Point Access Block guide (2025-02-28), emergency-services guideline (2025-04-15) | none |
| `alberta-other` | full, `fallback: true` | accredited municipality or Alberta Safety Codes Authority | none | none | none | none |

Generated place packs: 433, one for every place that no hand-written pack names (Calgary and Edmonton keep theirs).

| Kind (`authority.kind`) | Packs | Coverage | What the pack says |
|---|---:|---|---|
| `accredited_municipality` | 259 | full | The municipality or Metis settlement is accredited for building (its Safety Codes Council number); three airport-land places name the municipality after the airport authority |
| `alberta_safety_codes_authority` | 73 | full | Not accredited for building: the Alberta Safety Codes Authority oversees permits; the owner picks one of its agencies |
| `first_nation` | 50 | preview | Reserve land: the Nation may set its own building rules (Indian Act s.81(1)(h)) |
| `federal` | 6 | preview | Parks Canada issues the building permit (five park districts and the Jasper townsite) |
| `unconfirmed` | 2 | preview | Lloydminster (own bylaw, code not confirmed) and Redwood Meadows (office not confirmed) |
| `outside_alberta` | 43 | preview | The place is outside Alberta; names the code it uses |

The loader also rejects a place alias that another pack claims as its id, and a `first_nation`, `federal`,
`outside_alberta` or `unconfirmed` pack with full coverage.

Alberta shared items (`provinces/AB.json`): the SCC Variance Form for Proposed Alternative Solution
(`scc_2026-10`, sha256 pinned, ported from PR #12's `forms.json`), bulletins IB-2026-10-01,
IB-2025-11-18 and IB-2026-10-16 (ported from PR #11's `bulletins.py`), and six province-wide process notes.

### Sources

Every process note, authority, form, standing package, guide, bulletin and notice carries a
`PackSource`: `title`, `url` (https), `retrieved` (the date the URL was fetched or checked),
optional `pages`, `sha256` of the fetched file, and `status`. `status: unverified` means the claim
could not be checked against the source; it always has a `note` saying why. All URLs in the three
packs were fetched on 2026-10-21; where a local copy exists, each PDF's SHA-256 matched the copy under the git-excluded
`reference/` folder.

## Resolution

A case resolves to a pack in this order (`Registry.resolve`):

1. `jurisdiction.id` equals a pack id or one of its `match.ids` → `matched_by: id`.
2. `jurisdiction.name` or `jurisdiction.authority` equals the pack name or one of its `match.names` → `name`.
   Then the same for the part before a comma ("Toronto, ON", "Red Deer, AB") → `name`.
   Comparisons ignore case, accents, curly apostrophes and spacing. A generated place pack's `match.names` are the
   place's short and everyday names ("Red Deer", "Siksika", "Fort McMurray"); a name two places share is kept only
   by the one municipality among them, else dropped (so "Taber" alone falls back).
3. `case.authority` (the reviewer code) equals a pack's `authority.reviewer_code` → `reviewer_code`.
4. The case names some jurisdiction but nothing matched → the `fallback` pack of `default_province` → `fallback`.
5. Otherwise no pack.

The loader rejects two packs claiming the same id or name, a second fallback in a province, a
`reviewer_code` that is not an account `Authority`, and a pack whose province has no coverage entry.

## Routes

All three are reads. The first two are public; the third follows the case access policy (owner, or
a reviewer of the case's authority once submitted; others get `404 case not found`).

### `GET /jurisdictions`

`JurisdictionsResult`:

```json
{
  "jurisdictions": [
    {"id": "calgary", "name": "City of Calgary", "province": "AB", "coverage": "full", "fallback": false,
     "authority": "City of Calgary", "reviewer_code": "calgary", "standing_packages": 2, "forms": 2}
  ],
  "coverage": [{"id": "BC", "name": "British Columbia", "coverage": "preview", "note": "...", "roadmap": "Province packs, wave 2"}],
  "levels": {"full": "...", "code_only": "...", "preview": "..."},
  "disclaimer": "Process notes say where an application goes ... The safety codes officer decides.",
  "meta": {"notice": "..."}
}
```

Rows are ordered by province, local packs before the fallback, then name.

### `GET /jurisdictions/{id}`

`JurisdictionDetail`: the pack with province items merged in. `forms[]` and `process_notes[]` carry
`scope` (`province` or `local`); province items come first. `bulletins[]` are the province's
bulletins. `404` detail `jurisdiction not found`.

### `GET /cases/{case_id}/jurisdiction/pack`

`CaseJurisdictionPack`: `{ "case_id", "matched_by": "id" | "name" | "reviewer_code" | "fallback" | null, "pack": JurisdictionDetail | null }`.

## Where packs change behaviour

| Surface | What reads the pack |
|---|---|
| `GET /cases/{id}/gaps` and `check_completeness` | Each notice with surface `gaps` becomes a gap `id: info:<notice id>`, `field: <notice id>`, `severity: info`. Info never blocks export or submit. |
| `GET /cases/{id}/gaps`, export | A case whose pack is not `full` coverage gets `coverage:jurisdiction` (`severity: blocking`): "<place>: <pack summary>", with the pack's contact as the fix. A final export is refused (409); a draft still opens. |
| `POST /cases/{id}/export` (draft and final) | Notices with surface `export_header` are sent as `X-Batatis-Jurisdiction-Notice` (joined by a space). `X-Batatis-Notice` keeps the standard privacy notice. Messages are ASCII so they fit a header. |
| Export appendix | Notices with surface `export_appendix` print under their `heading` (Calgary: "Local variance form"). |
| `POST /cases/{id}/submit` | The "choose a reviewing authority" message names the packs that have a reviewer code. |

## Coverage labels

| Label | Meaning |
|---|---|
| `full` | Code database, Section C lookup, and jurisdiction packs. Alberta only. |
| `code_only` | Code lookup for the adopted code, but no pack. No region has this today. |
| `preview` | Roadmap only. Neither the adopted code nor a pack. Every other province and territory, and the Alberta places Batatis does not cover (reserve land, national parks, places not confirmed). |

## The one allowed city literal

`test_no_jurisdiction_literals.py` fails when `calgary` or `edmonton` appears in engine Python
outside `engine/data/`, `engine/tests/` and `fixtures/` folders. The single exception is the
account type `Authority = Literal['calgary', 'edmonton']` in `engine/account_models.py`: PR #48
restricts reviewer accounts to those two offices for now. A schema test checks that every reviewer
code has a pack. When reviewer accounts open to more offices, derive `Authority` from the packs and
remove the exception.

## Checklists

`standing_packages[].checklist` names the checklist file for SPV-001, SPV-006 and B23-01 (WP-32);
it is `null` for B14-01, which is historical. Routes and data: [`checklists.md`](checklists.md).

## Not in this package

- Filling Calgary's form (WP-44). The form entry is `export: not_yet`.
- The picker and process-notes panel (WP-35).
