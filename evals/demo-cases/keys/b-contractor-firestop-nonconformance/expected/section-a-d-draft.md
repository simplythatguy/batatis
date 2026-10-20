> agent-authored, model-checked, not human-verified or official

# Expected: Section A–D draft (Case B, only for penetrations with no tested system)
> EXAMPLE DATA. Draft for the SCC form (W4; from Dec 1, 2026 the **revised** SCC form goes with OVP-portal registration, IB-2026-10-01) and the Calgary *Request for Specific Variance* (W10). **Calgary: one request per issue/permit**, so the sprinkler question, if needed, is a separate request. This is not an approval.

## Section A
| Field | Draft value | Flag |
|---|---|---|
| Owner | Example Commons Holdings Inc. *(fictional)* | ✓ |
| Representative | Carlos Mendes, Northgate Example Builders *(fictional)* | ⚠ Written authorization |
| Mailing address | `[REQUIRED]` | ❌ |
| Date of request | `[on submission]` | — |

## Section B
| Field | Draft value | Flag |
|---|---|---|
| Permit number | BP-0000-00000 *(fictional)* | ✓ |
| Municipal address / legal | 0000 Example Avenue SW; Lot 0 Block 0 Plan 0000000 *(fictional)* | ✓ |
| Description | At `[n]` combustible-pipe penetrations on L3–L4 (IDs `[list]`) where **no CAN/ULC-S115:2018 system tested at a 50 Pa pressure differential is listed** for the penetrant and annular space, use firestop system `[EJ ref]` per the manufacturer's engineering judgment dated `[date]`, reviewed by the coordinating registered professional. | ⚠ `n` and the EJ are TBD. All other penetrations are remediated to listed systems. |

## Section C
**Applicable code:** NBC(AE) 2023, Division B (2nd printing in force; rows and pages below checked against the **1st printing**).

| Article(s) | Objective | Function | Intent statement | Source |
|---|---|---|---|---|
| 3.1.9.1.(1), firestops at penetrations of rated fire separations | OS1.2, OP1.2 (fire impacting areas beyond its point of origin); OS1.3, OP1.3 (collapse due to fire) | F03 (retard effects of fire beyond its point of origin); F04 (retard failure or collapse due to fire) | **⚠ GAP: intent lookup not available in the source set. Leave blank and flag it. Don't paraphrase from memory.** | Table 3.10.1.1., 1st pr. PDF p.317: [F03-OS1.2], [F03-OP1.2], [F04-OS1.3], [F04-OP1.3] |
| **3.1.9.4.(3)**, combustible DWV piping penetrating a rated fire separation (via (4)(b): 50 Pa CAN/ULC-S115:2018 test in buildings > 3 storeys) | OS1.2, OP1.2; OS1.3, OP1.3 | F03; F02, F04 | **⚠ GAP: intent lookup not available.** Flagged blank. | Table 3.10.1.1., 1st pr. PDF p.318 (B 3-196): [F03-OS1.2], [F02,F04-OS1.3], [F03-OP1.2], [F02,F04-OP1.3] |
| 3.1.8.1.(2), openings in fire separations protected | OS1.2, OP1.2 | F03 | ⚠ GAP: intent lookup not available | Table 3.10.1.1., 1st pr. PDF p.316 (B 3-194): [F03-OS1.2], [F03-OP1.2], "applies to the requirement that openings in fire separations be protected with closures, shafts or other means". (3.1.8.1.(1) is attributed to clause (a) only.) |

*Benchmark acceptable solution:* a firestop system tested to CAN/ULC-S115:2018 (2nd printing, Div B Table 1.3.1.2, PDF p.116) **with a 50 Pa pressure differential**, for the actual penetrant, size, annular space and floor assembly, with an F rating ≥ the required rating; piping not in a vertical service space (3.1.9.4.(4)(b), (c)).
**Required by 2.3.1.1:** a code analysis (why no 50 Pa-tested system fits; the tested systems the EJ relies on, by interpolation or bracketing; differences from the tested configuration); **assumptions and limiting factors** (sizes, annular space range, assembly type), test procedures and performance parameters; O&M; inspection before concealment; qualifications; the coordinator.
**Good practice / SCO expectation (not 2.3.1.1 terms):** a **risk assessment** (e.g. plastic pipe burn-through behaviour, smoke passage) and **mitigations** (e.g. added intumescent collars *if the EJ specifies them*, sprinklered building context as stated by the design team, not assumed by the tool).

## Section D
| Supporting document | Responsible | Status |
|---|---|---|
| NCR-FS-007 firestop inspection report | Example Firestop Inspection Ltd. *(fictional)* | ✓ |
| Remediation plan: listed CAN/ULC-S115:2018 systems per penetration type | Firestop sub + architect | ❌ Not prepared |
| Manufacturer EJ meeting IFC content (W14) | Example Sealants Co. **technical staff** or a qualified PE/FPE | ❌ Sales email only |
| Code analysis and coordinator statement | Example Architecture Inc. *(fictional)*, coordinating RP | ❌ |
| Penetration schedule with photos | Northgate Example Builders *(fictional)* | ✓ |
| Re-inspection record before close-in | Inspector + firestop inspector | ❌ Future |
