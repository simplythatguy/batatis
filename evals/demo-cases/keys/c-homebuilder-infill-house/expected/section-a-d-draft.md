> agent-authored, model-checked, not human-verified or official

# Expected: Section A–D draft (Case C, W-07 bedroom window only)
> EXAMPLE DATA. For the SCC Variance Form (W4), submitted with the Edmonton house permit application (no City-specific form, W20). From Dec 1, 2026, issued variances are registered via the SCC OVP portal with the revised form (IB-2026-10-01). Use it only if the routes inside the cited sentences are rejected. Not an approval. #1 and #2 are **not** in this request: they ride on the STANDATAs.

## Section A
| Field | Draft value | Flag |
|---|---|---|
| Owner | J. & R. Example *(fictional)* | ✓ |
| Representative | Priya Natarajan, Larkspur Example Homes *(fictional)* | ⚠ Owner authorization |
| Mailing address | `[REQUIRED]` | ❌ |
| Date | `[on submission]` | — |

## Section B
| Field | Draft value | Flag |
|---|---|---|
| Permit number | `[pending: request submitted with the permit application]` | ⚠ |
| Municipal address / legal | 0000 Example Crescent NW, Edmonton; Lot 0 Block 0 Plan 0000000 *(fictional)* | ✓ |
| Description | Bedroom 3 (2nd floor) sole window W-07, casement, unobstructed opening 400 × 780 mm = **0.312 m²** where 0.35 m² is required; minimum dimension 400 mm (≥380 mm). House unsprinklered. Fall protection: `[REQUIRED: ASTM F2090 WOCD per STANDATA 23-BCV-001 / Edmonton B23-02, or a guard per 9.8.8.1.(4)/(5)]`. | ⚠ The opening basis needs confirming |

## Section C
**Applicable code:** NBC(AE) 2023, Division B (2nd printing in force; rows checked against the 1st printing).

| Article | Objective | Function | Intent statement *(NBC 2020 national explanatory supplement, not Alberta law; not independently checked again)* | Source |
|---|---|---|---|---|
| 9.9.10.1.(1) | OS3.7 (an emergency delays or prevents movement to safety) | F10 (timely movement to a safe place in an emergency) | GAP: intent lookup not available | Table 9.38.1.1., 1st pr. PDF p.1117 (B 9-295) |
| 9.9.10.1.(2) | OS3.7 | F10 | GAP: intent lookup not available | same |

*Benchmark acceptable solution:* an openable window or door with ≥0.35 m² unobstructed opening, no dimension <380 mm, that stays open without support, **or** sprinklering under the 9.9.10.1.(1) exception.
**Required by 2.3.1.1:** a code analysis (the shortfall, 0.038 m² or about 11%; why the routes inside the cited sentences were rejected); **assumptions and limiting factors** (room use, single window, how the opening is measured); O&M (e.g. hardware and the WOCD must stay operable and auto-reset); the designer's qualifications.
**Good practice / SCO expectation (not 2.3.1.1 terms):** a **risk assessment** (bedroom occupant trapped if the interior route is blocked) and **mitigations proposed by the designer**, which the tool lists as candidates and doesn't judge adequate (e.g. a second opening that meets 9.9.10.1.(2), sprinklering, revised hardware or sash configuration giving a larger opening).

## Section D
| Document | Responsible | Status |
|---|---|---|
| Window schedule A-202 rev P1 | Larkspur Example Homes *(fictional)* | ✓ |
| Supplier opening dimension confirmation (measurement basis) | Example Fenestration Co. *(fictional)* | ❌ |
| WOCD product data showing ASTM F2090 and B23-02 criteria | Supplier | ❌ |
| Code analysis with risk, mitigations, assumptions | Designer (named) | ❌ |
| Owner authorization of the representative | Owners | ❌ |
