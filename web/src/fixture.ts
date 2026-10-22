import { CODE_EDITION } from "./config";
import type { Case } from "./types";

/**
 * Fixture case: a manufacturer of a continuous exterior insulating sheathing board (modelled on
 * the organizers' BTRboard example). The applicant, product, files and test values are fictional.
 *
 * Code text: every `quote.text`, `intent[].text` and `citation` below was copied from
 * `codedb.lookup(..., division="B")` against codedb/build/codedb.sqlite on 2026-10-20 (line breaks
 * joined with spaces; "…" marks an omission). Attribution brackets, statuses and the "differs"
 * flag are the database's `attributions`, `attribution_status` and `intent_comparison` rows.
 */
export const FIXTURE: Case = {
  id: "case-northcore-cx",
  title: "NorthCore CX exterior sheathing board",
  applicantType: "manufacturer",
  codeEdition: CODE_EDITION,
  authority: "",
  description:
    "We make NorthCore CX, a foil-faced rigid board that goes on the outside of the studs as continuous insulation and replaces the housewrap. We want builders to use it on houses and townhomes anywhere in Alberta.",
  files: [
    { id: "file-datasheet", name: "NorthCore-CX_product-data-sheet.pdf", pages: 4, read: true },
    { id: "file-test", name: "NorthCore-CX_vapour-permeance-test.pdf", pages: 9, read: true },
  ],
  facts: [
    {
      id: "f-product",
      field: "product.name",
      value: "NorthCore CX",
      kind: "pointed",
      source: {
        type: "file",
        ref: "NorthCore-CX_product-data-sheet.pdf",
        page: 1,
        bbox: [54, 702, 318, 726],
        quote: "NorthCore CX continuous insulating sheathing",
      },
      status: "confirmed",
    },
    {
      id: "f-role",
      field: "product.role",
      value: "Exterior insulating sheathing that replaces the housewrap",
      kind: "pointed",
      source: {
        type: "user_text",
        ref: "Your description",
        quote: "goes on the outside of the studs as continuous insulation and replaces the housewrap",
      },
      status: "confirmed",
    },
    {
      id: "f-permeance",
      field: "product.permeance",
      value: "28 ng/(Pa·s·m²), dry cup",
      kind: "pointed",
      source: {
        type: "file",
        ref: "NorthCore-CX_vapour-permeance-test.pdf",
        page: 3,
        bbox: [72, 488, 402, 504],
        quote: "Water vapour permeance (dry cup): 28 ng/(Pa·s·m²)",
      },
      status: "confirmed",
    },
    {
      id: "f-rsi-board",
      field: "product.rsi",
      value: "RSI 0.88 per 25 mm",
      kind: "pointed",
      source: {
        type: "file",
        ref: "NorthCore-CX_product-data-sheet.pdf",
        page: 2,
        bbox: [310, 540, 470, 556],
        quote: "Thermal resistance: RSI 0.88 (25 mm)",
      },
      status: "confirmed",
    },
    {
      id: "f-rsi-cavity",
      field: "assembly.cavityRsi",
      value: "RSI 3.34 stud-cavity batt",
      kind: "proposed",
      source: {
        type: "file",
        ref: "NorthCore-CX_product-data-sheet.pdf",
        page: 3,
        quote: "Typical wall: 2x6 studs, R-19 batt, NorthCore CX 25 mm",
      },
      confidence: 0.64,
      status: "unconfirmed",
    },
    {
      id: "f-ratio",
      field: "assembly.ratio",
      value: "0.26",
      kind: "computed",
      source: { type: "code", ref: "Formula over f-rsi-board and f-rsi-cavity" },
      formula: "RSI 0.88 outboard ÷ RSI 3.34 inboard = 0.26",
      inputs: ["f-rsi-board", "f-rsi-cavity"],
      status: "confirmed",
    },
    {
      id: "f-part",
      field: "building.part",
      value: "Part 9: houses and small buildings",
      kind: "proposed",
      source: { type: "user_text", ref: "Your description", quote: "houses and townhomes" },
      confidence: 0.86,
      status: "unconfirmed",
    },
    {
      id: "f-edition",
      field: "code.edition",
      value: CODE_EDITION,
      kind: "exact",
      source: { type: "code", ref: "Code database" },
      status: "confirmed",
    },
    {
      id: "f-owner",
      field: "owner",
      value: "Northwind Board Works Ltd.",
      kind: "pointed",
      source: {
        type: "file",
        ref: "NorthCore-CX_product-data-sheet.pdf",
        page: 1,
        bbox: [54, 60, 290, 72],
        quote: "Manufactured by Northwind Board Works Ltd.",
      },
      status: "unconfirmed",
    },
    {
      id: "f-scope",
      field: "scope",
      value: "jurisdiction",
      kind: "proposed",
      source: { type: "user_text", ref: "Your description", quote: "anywhere in Alberta" },
      confidence: 0.7,
      status: "unconfirmed",
    },
  ],
  questions: [
    {
      id: "q-cavity",
      text: "Is there insulation in the stud cavity too? If so, how much?",
      why: "Sets the inside insulation used to check where a vapour-resistant board may sit.",
      field: "assembly.cavityRsi",
    },
    {
      id: "q-cladding",
      text: "Is siding fastened into the board itself, or through it into studs or strapping?",
      why: "The code limits using rigid insulation to hold cladding; this decides if that applies.",
      field: "assembly.claddingAttachment",
    },
    {
      id: "q-climate",
      text: "Which parts of Alberta will it be installed in?",
      why: "The required insulation ratio depends on the climate of the location.",
      field: "site.climate",
    },
    {
      id: "q-facer",
      text: "Has the foil facer been tested to the sheathing-membrane standard?",
      why: "Decides whether the facer can stand in for a sheathing membrane.",
      field: "product.facerStandard",
    },
  ],
  candidates: [
    {
      id: "c-vapour",
      topic: "Where a vapour-resistant board may sit in the wall",
      provision: "9.25.5.2.(1)(b)",
      part: 9,
      benchmark: true,
      quote: {
        text:
          "Sheet and panel-type materials described in Article 9.25.5.1. shall be installed a) on the warm face of the assembly (see also Article 9.25.4.2.), b) at a location where the ratio between the total thermal resistance of all materials outboard of its innermost impermeable surface and the total thermal resistance of all materials inboard of that surface is not less than that required by Table 9.25.5.2., or c) outboard of an air space that is vented to the outdoors.",
        citation: "NBC(AE) 2023 p2, Div B, Sentence 9.25.5.2.(1) [PDF p.1000]",
      },
      departure:
        "put the foil-faced board on the outside of the studs, where the outside-to-inside insulation ratio may be lower than the table asks for",
      clarifyingQuestion: "How much insulation is inside the board, in the stud cavity? We use it to compute the ratio.",
      answer: "yes",
    },
    {
      id: "c-membrane",
      topic: "What material counts as the sheathing membrane",
      provision: "9.27.3.2.(1)",
      part: 9,
      benchmark: false,
      quote: {
        text: "Sheathing membranes shall conform to the performance requirements of CAN/CGSB-51.32-M, “Sheathing, Membrane, Breather Type.”",
        citation: "NBC(AE) 2023 p2, Div B, Sentence 9.27.3.2.(1) [PDF p.1015]",
      },
      departure: "use the board's foil facer as the sheathing membrane, tested to a different standard",
      clarifyingQuestion: "Which standard was the foil facer tested to, and who ran the test?",
      answer: "not-sure",
    },
    {
      id: "c-cladding",
      topic: "Using the board to hold the siding",
      provision: "9.23.17.3.(1)",
      part: 9,
      benchmark: false,
      quote: {
        text: "Gypsum sheathing, rigid insulation and fibreboard shall not be used for the attachment of cladding materials.",
        citation: "NBC(AE) 2023 p2, Div B, Sentence 9.23.17.3.(1) [PDF p.990]",
      },
      departure: "rely on the board itself to hold the siding fasteners",
      clarifyingQuestion: "Do the siding fasteners rely on the board, or do they reach studs or strapping?",
      answer: null,
    },
  ],
  sectionC: [
    {
      candidateId: "c-vapour",
      provision: "9.25.5.2.(1)(b)",
      citation: "NBC(AE) 2023 p2, Div B, Clause 9.25.5.2.(1)(b) [PDF p.1000]",
      attributionStatus: "inherited",
      inheritedFrom: "9.25.5.2.(1)",
      pairs: [
        { bracket: "[F62,F63-OS2.3]", functions: ["F62", "F63"], objectives: ["OS2.3"] },
        { bracket: "[F62,F63-OH1.1,OH1.2]", functions: ["F62", "F63"], objectives: ["OH1.1", "OH1.2"] },
      ],
      intent: [
        {
          objective: "OS2",
          text: "To limit the probability of inadequate moisture diffusion, venting or drainage of moisture to the exterior under normal interior conditions, which could lead to condensation. …",
        },
      ],
      differs: false,
      explanation:
        "The board would sit outside the studs, so this sentence decides where a vapour-resistant panel may go. Your evidence needs to address the same objectives and functions listed for this row. This does not say whether the design complies.",
    },
    {
      candidateId: "c-membrane",
      provision: "9.27.3.2.(1)",
      citation: "NBC(AE) 2023 p2, Div B, Sentence 9.27.3.2.(1) [PDF p.1015]",
      attributionStatus: "direct",
      pairs: [
        { bracket: "[F20,F61,F62,F55-OS2.3]", functions: ["F20", "F61", "F62", "F55"], objectives: ["OS2.3"] },
        {
          bracket: "[F20,F61,F62,F55-OH1.1,OH1.2,OH1.3]",
          functions: ["F20", "F61", "F62", "F55"],
          objectives: ["OH1.1", "OH1.2", "OH1.3"],
        },
      ],
      intent: [
        {
          objective: "OS2",
          text: "To limit the probability that performance, with respect to strength, airtightness, … will fall significantly below expectations. …",
        },
      ],
      differs: true,
      differsDetail:
        "NBC(AE) 2023 pairs F20, F55, F61 and F62 with OS2.3; the NBC 2020 intent statement does not carry those pairs.",
      explanation:
        "If the foil facer replaces the sheathing membrane, this is the standard the membrane would otherwise meet. Evidence would need to show the facer meets the same functions. This does not say whether the facer qualifies.",
    },
    {
      candidateId: "c-cladding",
      provision: "9.23.17.3.(1)",
      citation: "NBC(AE) 2023 p2, Div B, Sentence 9.23.17.3.(1) [PDF p.990]",
      attributionStatus: "no-row",
      pairs: [],
      intent: [
        {
          objective: null,
          text: "To limit the application of Sentence 9.23.17.2.(1) and Table 9.23.17.2.-A so as to exclude sheathing materials that do not have an adequate capacity to hold fasteners.",
        },
      ],
      differs: false,
      explanation:
        "Applies only if the siding relies on the board to hold its fasteners. The attribution table has no row for this sentence, so Section C states that instead of inventing an objective.",
    },
  ],
  process: { rationale: "", risk: "", mitigation: "", assumptions: "", maintenance: "", qualifications: "" },
};

/**
 * Titles of the objectives and functions used above, from the database `definitions` table.
 * F55 had a whitespace extraction artifact ("thro ugh") joined.
 */
export const CODE_TERMS: Record<string, string> = {
  "OS2.3": "damage to or deterioration of building elements",
  "OH1.1": "inadequate indoor air quality",
  "OH1.2": "inadequate thermal comfort",
  "OH1.3": "contact with moisture",
  F20: "To support and withstand expected loads and forces.",
  F55: "To resist the transfer of air through environmental separators.",
  F61: "To resist the ingress of precipitation, water or moisture from the exterior or from the ground.",
  F62: "To facilitate the dissipation of water and moisture from the building.",
  F63: "To limit moisture condensation.",
};
