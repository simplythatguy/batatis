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
