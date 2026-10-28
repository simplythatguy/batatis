/**
 * The deck options every screen that builds the deck passes (deck, Review, header progress): rule
 * data and stored results, checklists, and this visit's package choices. Recorded uncertainty
 * lives on the case and is read by buildDeck. One source,
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
    confirmAuthority: true,
    benchmark: extras.identify?.benchmark ?? null,
  }), [extras.rules, extras.caseRules, extras.checklists, extras.identify, session.packages]);
  return { options, extras };
}
