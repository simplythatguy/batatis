# Recovered Alberta cases for the Elephant identification benchmark

Recovery and bounded source audit: 2026-10-23 (America/Edmonton). Companion data: [cases-alberta.json](cases-alberta.json). Detailed evidence and Canadian spot checks: [source-audit.md](source-audit.md). The existing Canada report was left unchanged.

## Inventory and validation

The saved file contains **64 cases**, rather than the brief's “Alberta60”: 111 gold article slots covering 98 distinct NBC(AE) 2023, second-printing, Division B articles. This recovery retained the file as found; it did not reconstruct an earlier 60-case version or add cases.

| Saved type | Cases |
|---|---:|
| Variance | 24 |
| Interpretation | 22 |
| Bulletin | 6 |
| Appeal | 11 |
| Alternative-solution example | 1 |
| **Total** | **64** |

Source hosts: Alberta Open Government 33; Calgary 13; Safety Codes Council 11; Edmonton 4; Rocky View, Medicine Hat and Beaumont one each. The saved confidence labels are 54 high and 10 medium; those are dataset labels, not professional review conclusions.

Executed after reading the validator's help and implementation:

```sh
.venv/bin/python -m evals_dev.identify_bench.validate_web_cases docs/research/2026-10-23-elephant/cases-alberta.json
```

Result: `64 cases, 0 problems` (exit 0). All 117 saved Alberta mapping entries also have an exact title match and a whitespace-normalized, case-insensitive quote match in the private local code database. There are 111 gold mappings and six additional mapped context entries. The structural validator checks the existence of every listed gold/context article, required source fields, description length/number leakage, unique IDs and the presence of a mapping for each gold article. It does **not** fetch a source, validate the mapping explanation, compare editions or establish complete gold.

## Coverage

The cases cover window guards and bedroom escape; spatial separation, soffits, party walls and suite separations; fire ratings, door assemblies, fire alarms, occupant loads and exits; fire-service access, water and standpipes; ventilation and cooking exhaust; energy, insulation and HVAC; structural wood, foundations and cladding; and barrier-free facilities. The point-access-block report provides a city-published example of an alternative-solution submission concerning a single exit stair.

Cases touching each Part, with cross-Part cases counted in each applicable row: Part 9, 39; Part 3, 27; Part 6, five; Part 4, two; Parts 1 and 5, one each. This is a purposive precedent collection, with substantial residential/fire-safety coverage, rather than a representative sample of Alberta applications or all code Parts.

## Primary sources consulted in this recovery

These ten source documents were fetched publicly and read on 2026-10-23 MDT. Each source's gold targets and current-edition quote receipts are recorded in the audit. Other records retain their saved provenance; this recovery did not re-fetch every source or repeat the original search.

| Case | Live primary source |
|---|---|
| `ab-wocd-window-guards-egress` | [Alberta 23-BCV-001: window opening control devices](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf) |
| `ab-tall-wall-heights-guideline` | [Alberta 14-BCV-002R1: tall walls](https://open.alberta.ca/dataset/27900157-f850-4138-a964-b813f0921a3b/resource/ed820685-ee6e-46f7-83b0-44174268ce92/download/14-bcv-002r1-tallwall.pdf) |
| `ab-radon-pipe-labelling` | [Alberta 23-BCB-013 / 20-PCB-010R1: radon piping](https://open.alberta.ca/dataset/5cd7e000-4f7c-4188-b26f-11a16bbe43f8/resource/af31ca67-0db6-43ef-8df6-6da1f537f85e/download/ma-standata-bulletin-building-plumbing-23-bcb-013-20-pcb-010r1-2025-07.pdf) |
| `ab-calgary-side-yard-egress-widths` | [Calgary A19-004: exterior egress](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/Building-Advisory-A19-004-Exterior-Egress-Requirements-for-Single-Family-Dwellings-Final-August-31-2022.pdf) |
| `ab-edmonton-single-stair-point-access-block` | [Edmonton point-access-block example technical report](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Technical-Report.pdf) |
| `ab-appeal-stair-door-frame-foam-gap` | [Safety Codes Council order 0015442: door/frame assemblies](https://ebs.safetycodes.ab.ca/documents/webdocs/appeals/decisions-2014/Building_Exit_Stairwell_Door_and_FrameAssemblies_and_Compliance_with_ABC2006_and_NFPA80.pdf) |
| `ab-appeal-restaurant-kitchen-exhaust-nfpa96` | [Safety Codes Council order 0015408: cooking ventilation](https://ebs.safetycodes.ab.ca/documents/webdocs/appeals/decisions-2012/REDACTED_Bldg_Ventilation%20Control%20and%20Fire%20Protection%20of%20Commercial%20Cooking%20Operations%20March%202012_0015408.pdf) |
| `ab-appeal-dinner-theatre-platform-not-a-stage` | [Safety Codes Council order 0015421: theatrical stage](https://ebs.safetycodes.ab.ca/documents/webdocs/appeals/decisions-2012/REDACTED_Bldg_Performance%20Platform%20Classification%20and%20Requirement%20of%20Sprinkler%20Deluge%20System%20June%202012_0015421.pdf) |
| `ab-licensed-beverage-establishment-occupant-load` | [Alberta 23-BCI-003R1 / 23-FCI-002R1: occupant loads](https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/b7caed68-90ad-4798-8f1e-2c7e0a716590/download/ma-standata-interpretation-building-fire-23-bci-003r1-23-fci-002r1-2025-01.pdf) |
| `ab-overnight-child-care-smoke-and-fire-alarms` | [Alberta 23-BCI-002 / 23-FCI-009: overnight child care](https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/dbe79285-1847-4a1c-b62d-8343fe507f99/download/ma-standata-interpretation-building-fire-23-bci-002-23-fci-009-2024-04.pdf) |

## Edition and wording limits

Forty-two records label their source NBC(AE) 2023/current wording, including four whose edition label needs the qualification stored in the JSON. The other 22 comprise six NBC(AE) 2019, four ABC 2014, ten ABC 2006 (one also discusses 2014), and two advisories with a nonspecific ABC edition label. These labels describe the sources; only current-edition Division B article IDs are benchmark targets.

Verified historical locators include ABC 2006 temperature-rise doors `3.1.8.15.` → current `3.1.8.17.`, cooking equipment `6.2.2.6.` → `6.3.1.6.`, and theatrical stages `3.3.2.13.` → `3.3.2.14.`. A matching locator/quote does not establish identical exceptions, tables, referenced standards, continuing variance applicability or an approved transfer to a new project. The tall-wall table values were not checked. Calgary's historical landing sentence number also differs from the current sentence.

The Calgary egress description needs a qualifier: source PDF page 2 distinguishes 760 mm at the window from conditional 550 mm clearance along the window-only side-yard path. Its article targets are supported, but the description's blanket statement about fences/cantilevers omits that distinction. The saved JSON was not edited.

## Rewrites, exclusions and use in evaluation

**32 of the 64 records explicitly rewrite cases in the earlier 53-case precedent collection.** All 32 `rewrite_of` targets resolve. These are alternative descriptions of existing sources, not 32 independent new precedents. Raw ID hashing puts 14 rewrite/original pairs in opposite tune/test folds; evaluate with source/duplicate-group separation. Three rewrites change gold versus their originals: equipment-shelter energy exemption, licensed-establishment occupant load, and overnight child care. The audit lists the exact deltas.

Saved notes record exclusions of superseded/repeated local versions, including Edmonton's WOCD restatement, earlier exhaust-clearance and truss publications, older rowhouse-wall policies, and another municipal fire-access advisory. A separate Rocky View zero-lot-line case remains because it has a different authority, district and conditions. These are recovered exclusion notes, not a claim that this worker searched every alternative publication.

Targets exclude Division A/C process provisions, fire/plumbing-code citations and external standards; those may still matter to an application. Some old construction-classification articles and changed exceptions were deliberately left unmapped. The overnight-child-care description asks about bedroom egress, but its source-citation gold omits the egress article because the source does not name it. Thus source-citation recall cannot be presented as exhaustive identification of everything the description requires. Keep source type, edition, rewrite group and gold-policy limits visible in any results.

This is research for administrative completeness. Neither matching citations nor benchmark recall establishes technical equivalence, legal transfer, safety, design compliance or professional approval.
