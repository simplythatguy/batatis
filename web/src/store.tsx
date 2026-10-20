import { createContext, useContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import { FIXTURE } from "./fixture";
import { getGaps, reducer, type Action } from "./model";
import type { Case, Gap } from "./types";

const KEY = "batatis-web-case-v1";

function load(): Case {
  if (new URLSearchParams(location.search).has("reset")) sessionStorage.removeItem(KEY);
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Case;
  } catch {
    /* fall through to the fixture */
  }
  return FIXTURE;
}

interface Store {
  c: Case;
  gaps: Gap[];
  dispatch: Dispatch<Action>;
}

const Ctx = createContext<Store | null>(null);

export function CaseProvider({ children }: { children: ReactNode }) {
  const [c, dispatch] = useReducer(reducer, undefined, load);
  useEffect(() => sessionStorage.setItem(KEY, JSON.stringify(c)), [c]);
  const value = useMemo(() => ({ c, gaps: getGaps(c), dispatch }), [c]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCase(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useCase outside CaseProvider");
  return s;
}

export const resetCase = (dispatch: Dispatch<Action>) => dispatch({ type: "reset", to: FIXTURE });
