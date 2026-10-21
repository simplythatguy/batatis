import type { AuthorityId } from "./types";

/** NBC edition this product cites. One string, used by intake, examples, and screen headers. */
export const CODE_EDITION = "NBC(AE) 2023, 2nd printing";

/**
 * Authorities the applicant can pick. The engine case stays without a jurisdiction
 * until one of these is chosen.
 */
export const AUTHORITIES: { id: Exclude<AuthorityId, "">; name: string }[] = [
  { id: "calgary", name: "Calgary" },
  { id: "edmonton", name: "Edmonton" },
];

/** Exit-count sentences. 9.9.4.4 is openings near exterior exit stairs, not this. */
export const EXIT_COUNT = {
  part3: "3.4.2.1.(1)",
  part9: "9.9.8.2.(1)",
} as const;

/**
 * NRC credit shown next to code text. The printing selector is explicit; the bare publication URL defaults to the first printing.
 * The intent supplement link is the README's source record.
 */
export const NRC_CREDIT = "© National Research Council of Canada";
export const NRC_SOURCES = {
  code: {
    title: CODE_EDITION,
    url: "https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en",
  },
  intent: {
    title: "Supplement to the NBC 2020: Intent Statements",
    url: "https://nrc-publications.canada.ca/eng/view/object/?id=de0e0ec9-a452-4337-bc84-002a230c9d66",
  },
} as const;
