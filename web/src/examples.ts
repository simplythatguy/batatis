/**
 * Three example cases. They are never the case a new visitor starts on.
 * Sentence text is included only where this repo already stores it (the NorthCore fixture).
 * The other two name provisions from evals_dev and label the summary as not code text.
 */
import { CODE_EDITION } from "./config";
import { FIXTURE } from "./fixture";
import type { Case, Fact } from "./types";

export interface Example {
  id: string;
  label: string;
  blurb: string;
  case: Case;
}

function pointed(id: string, field: string, value: string, quote: string): Fact {
  return {
    id,
    field,
    value,
    kind: "pointed",
    status: "confirmed",
    source: { type: "user_text", ref: "Development case text", quote },
  };
}

const soffit = `We're building a new two-storey single detached house with a building area of 150 m2 on a narrow infill lot. The north side wall sits 0.3 m from the property line, which is the side yard against the neighbour's lot, not a street or lane. The client wants the same 450 mm roof overhang all the way around, including over that north wall. The soffit would be vented aluminum.`;

const ducts = `Mechanical contractor here. On a three-storey, twelve-unit wood-frame apartment with a building area of 480 m2 we have supply ducts that pass through the rated corridor walls. There's no room above the ceiling for damper access panels, so we'd like to skip the fire dampers and instead use 26 gauge steel duct sealed with a listed firestop at each wall.`;

const homebuilder: Case = {
  id: "example-soffit",
  exampleId: "homebuilder-soffit",
  title: "Soffit on a narrow infill lot",
  applicantType: "homebuilder",
  codeEdition: CODE_EDITION,
  authority: "calgary",
  description: soffit,
  files: [],
  facts: [
    pointed("ex-soffit-desc", "project.description", soffit, soffit),
    pointed("ex-soffit-alt", "alternative", soffit, soffit),
    pointed("ex-soffit-storeys", "building.storeys", "two-storey", "two-storey"),
  ],
  questions: [],
  candidates: [
    {
      id: "ex-soffit",
      topic: "Roof soffit over a close side wall",
      provision: "9.10.15.5.(8)",
      part: 9,
      benchmark: true,
      identified: true,
      answer: null,
      departure: "project the roof soffit over a side wall whose limiting distance is 0.45 m or less",
      clarifyingQuestion: "Is the north wall facing a side lot line, and is the overhang still wanted there?",
      quote: {
        text: "Roof soffit projects over an exposing building face whose limiting distance is 0.45 m or less.",
        citation: "Summary from development case dev-001, not the code sentence. Provision named there: 9.10.15.5.(8).",
      },
    },
  ],
  sectionC: [
    {
      candidateId: "ex-soffit",
      provision: "9.10.15.5.(8)",
      citation: "Cached from development case dev-001. Not a live lookup.",
      attributionStatus: "direct",
      pairs: [{ bracket: "[F03-OP3.1]", functions: ["F03"], objectives: ["OP3.1"] }],
      intent: [],
      differs: false,
    },
  ],
  process: { rationale: "", risk: "", mitigation: "", assumptions: "", maintenance: "", qualifications: "" },
};

const contractor: Case = {
  id: "example-dampers",
  exampleId: "contractor-dampers",
  title: "Ducts through a rated corridor wall",
  applicantType: "contractor",
  codeEdition: CODE_EDITION,
  authority: "",
  description: ducts,
  files: [],
  facts: [
    pointed("ex-duct-desc", "project.description", ducts, ducts),
    pointed("ex-duct-alt", "alternative", ducts, ducts),
    pointed("ex-duct-storeys", "building.storeys", "three-storey", "three-storey"),
  ],
  questions: [],
  candidates: [
    {
      id: "ex-damper",
      topic: "Fire dampers in rated corridor walls",
      provision: "9.10.13.13.(1)",
      part: 9,
      benchmark: true,
      identified: true,
      answer: null,
      departure: "omit fire dampers and use firestopped steel duct instead",
      clarifyingQuestion: "What is the fire-resistance rating of the corridor wall the duct passes through?",
      quote: {
        text: "Ducts penetrate rated fire separations without fire dampers; firestopped steel duct proposed instead.",
        citation: "Summary from development case dev-003, not the code sentence. Provision named there: 9.10.13.13.(1).",
      },
    },
  ],
  sectionC: [
    {
      candidateId: "ex-damper",
      provision: "9.10.13.13.(1)",
      citation: "Cached from development case dev-003. Not a live lookup.",
      attributionStatus: "direct",
      pairs: [
        { bracket: "[F03-OP1.2]", functions: ["F03"], objectives: ["OP1.2"] },
        { bracket: "[F03-OS1.2]", functions: ["F03"], objectives: ["OS1.2"] },
      ],
      intent: [],
      differs: false,
    },
  ],
  process: { rationale: "", risk: "", mitigation: "", assumptions: "", maintenance: "", qualifications: "" },
};

const manufacturer: Case = {
  ...structuredClone(FIXTURE),
  id: "example-northcore",
  exampleId: "manufacturer-northcore",
};

export const EXAMPLES: Example[] = [
  {
    id: "manufacturer-northcore",
    label: "Manufacturer · NorthCore sheathing",
    blurb: "Foil-faced board used as continuous insulation and a sheathing membrane. Cached code text is in this repo.",
    case: manufacturer,
  },
  {
    id: "contractor-dampers",
    label: "General contractor · corridor ducts",
    blurb: "Steel ducts through rated corridor walls, without fire dampers. Cached summary from development case dev-003.",
    case: contractor,
  },
  {
    id: "homebuilder-soffit",
    label: "Homebuilder · infill soffit",
    blurb: "Two-storey house, soffit over a 0.3 m side yard. Cached summary from development case dev-001.",
    case: homebuilder,
  },
];

export function exampleCase(id: string): Case | undefined {
  const found = EXAMPLES.find((e) => e.id === id);
  return found ? structuredClone(found.case) : undefined;
}
