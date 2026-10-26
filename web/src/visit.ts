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

/** A new visitor does not resume the previous case. Any stored value is ignored. */
export function initialVisit(_stored?: string | null): Visit {
  return { phase: "who", case: emptyCase("homebuilder"), note: "" };
}

/** The next role is a new case. `previous` is not copied. */
export function caseForRole(type: ApplicantType | null, previous?: Case): Case {
  void previous;
  return emptyCase(type);
}
