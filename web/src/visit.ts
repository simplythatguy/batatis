/**
 * A cold visit and a role change start empty.
 * Nothing from a stored session or the previous role is copied forward.
 */
import { emptyCase } from "./intake";
import type { ApplicantType, Case } from "./types";

export interface Visit {
  phase: "who";
  case: Case;
  note: string;
}

/** Ignore `stored`. A new visitor does not resume the previous case. */
export function initialVisit(stored: string | null): Visit {
  void stored;
  return { phase: "who", case: emptyCase("homebuilder"), note: "" };
}

/** The next role is a new case. `previous` is not copied. */
export function caseForRole(type: ApplicantType, previous?: Case): Case {
  void previous;
  return emptyCase(type);
}
