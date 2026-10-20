import { createContext, useContext, useEffect, useMemo, useReducer, useState, type Dispatch, type ReactNode } from "react";
import { FIXTURE } from "./fixture";
import { getGaps, reducer, type Action } from "./model";
import type { Case, Gap } from "./types";

const KEY = "batatis-web-case-v2";

function readSaved(): Case | null {
  if (new URLSearchParams(location.search).has("reset")) sessionStorage.removeItem(KEY);
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Case;
  } catch {
    /* fall through to the fixture */
  }
  return null;
}

interface Store {
  c: Case;
  gaps: Gap[];
  dispatch: Dispatch<Action>;
  /** The tab reloaded with changes to the case, so the app asks before resuming it. */
  restored: boolean;
}

const Ctx = createContext<Store | null>(null);

/** Fields commit to the case as the applicant types (see draft.ts); the browser copy is written
 *  ~500 ms after the last change, and at once when the page is hidden. */
const SAVE_DELAY = 500;

export function CaseProvider({ children }: { children: ReactNode }) {
  const [saved] = useState(readSaved);
  const [c, dispatch] = useReducer(reducer, undefined, () => saved ?? FIXTURE);
  const [restored] = useState(() => saved !== null && JSON.stringify(saved) !== JSON.stringify(FIXTURE));
  useEffect(() => {
    const save = () => sessionStorage.setItem(KEY, JSON.stringify(c));
    const t = window.setTimeout(save, SAVE_DELAY);
    window.addEventListener("pagehide", save);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("pagehide", save);
    };
  }, [c]);
  const value = useMemo(() => ({ c, gaps: getGaps(c), dispatch, restored }), [c, restored]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCase(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useCase outside CaseProvider");
  return s;
}

export const resetCase = (dispatch: Dispatch<Action>) => dispatch({ type: "reset", to: FIXTURE });
