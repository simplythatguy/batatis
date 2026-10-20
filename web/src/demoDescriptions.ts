/**
 * Example descriptions for Code ID. The text is copied verbatim from the engine's seeded demo cases
 * (dev-001, dev-003, dev-013 in engine/identify/demo_cache.json on PR #12 @ c382ed7). The engine keys its cached runs on this exact
 * text (whitespace-normalised), so do not edit it. The projects are examples, not this case.
 */
export interface DemoDescription {
  id: string;
  /** Short chip label, written for this UI. */
  label: string;
  /** Who would typically write it. */
  who: string;
  text: string;
}

export const DEMO_DESCRIPTIONS: DemoDescription[] = [
  {
    id: "dev-001",
    label: "House soffit near the property line",
    who: "Homebuilder",
    text: "We're building a new two-storey single detached house with a building area of 150 m2 on a narrow infill lot. The north side wall sits 0.3 m from the property line, which is the side yard against the neighbour's lot, not a street or lane. The client wants the same 450 mm roof overhang all the way around, including over that north wall. The soffit would be vented aluminum. Can we do this as a variance and what would we need to show?",
  },
  {
    id: "dev-003",
    label: "Ducts through rated corridor walls",
    who: "Mechanical contractor",
    text: "Mechanical contractor here. On a three-storey, twelve-unit wood-frame apartment with a building area of 480 m2 we have supply ducts that pass through the rated corridor walls. There's no room above the ceiling for damper access panels, so we'd like to skip the fire dampers and instead use 26 gauge steel duct sealed with a listed firestop at each wall. The ducts are about 150 by 250 mm and serve the suites' heat recovery ventilators.",
  },
  {
    id: "dev-013",
    label: "Single exit stair, four storeys",
    who: "Designer",
    text: "We're designing a four-storey, sprinklered wood-frame apartment with eight units per floor on a mid-block lot. To make the floor plate work we want a single exit stair serving every floor, with a pressurized stair and a short corridor. Each floor is about 600 m2.",
  },
];
