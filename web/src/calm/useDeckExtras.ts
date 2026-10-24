/**
 * The deck options every screen that builds the deck passes (deck, Review, header progress): rule
 * data and stored results, checklists, and this visit's package and Not sure choices. One source,
 * so the counts agree everywhere.
 */
import { useMemo } from "react";
import { useCase } from "../store";
import { useCaseExtras, type CaseExtras } from "./caseExtras";
import type { DeckOptions } from "./deck";
import { useSession } from "./session";

/** Combine shared engine extras and visit choices into the options used by every deck consumer. */
export function useDeckExtras(): { options: DeckOptions; extras: CaseExtras } {
  const { c, engineId, factsEpoch } = useCase();
  const extras = useCaseExtras(engineId, factsEpoch, c.authority);
  const session = useSession();
  const options = useMemo<DeckOptions>(() => ({
    rules: extras.rules,
    storedRules: extras.caseRules,
    checklists: extras.checklists,
    packages: session.packages,
    ruleUnsure: new Set(session.ruleUnsure),
    confirmAuthority: true,
  }), [extras.rules, extras.caseRules, extras.checklists, session.packages, session.ruleUnsure]);
  return { options, extras };
}
