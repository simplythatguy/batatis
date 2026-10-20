import { useEffect, useState } from "react";
import type { AttributionStatus, SectionCRow } from "../types";
import { engine } from "./client";
import type { SectionCRow as EngineRow } from "./types.gen";

export const ATTRIBUTION_STATUS: Record<EngineRow["attribution_status"], AttributionStatus> = {
  direct: "direct",
  "inherited from parent": "inherited",
  "no row in the attribution table": "no-row",
};

const list = (xs: string[]) => xs.map((x) => x.replace(/[[\]]/g, "")).join(", ");

/** Engine row -> screen row. Pairs regroup by table bracket; every word comes from the engine. */
export function toViewRow(r: EngineRow, candidateId: string): SectionCRow {
  const brackets = new Map<string, { functions: Set<string>; objectives: Set<string> }>();
  const terms: Record<string, string> = {};
  for (const p of r.pairs) {
    const b = brackets.get(p.bracket) ?? { functions: new Set(), objectives: new Set() };
    b.functions.add(p.function);
    b.objectives.add(p.objective);
    brackets.set(p.bracket, b);
    if (p.function_text) terms[p.function] = p.function_text;
    if (p.objective_text) terms[p.objective] = p.objective_text;
  }
  const detail = [
    r.only_in_ae.length && `NBC(AE) 2023 has ${list(r.only_in_ae)}, which the NBC 2020 intent statement does not.`,
    r.only_in_intent.length && `The NBC 2020 intent statement has ${list(r.only_in_intent)}, which NBC(AE) 2023 does not.`,
  ].filter(Boolean);
  return {
    candidateId,
    provision: r.provision_id,
    citation: r.citation,
    attributionStatus: ATTRIBUTION_STATUS[r.attribution_status],
    inheritedFrom: r.attributed_via ?? undefined,
    pairs: [...brackets].map(([bracket, b]) => ({ bracket, functions: [...b.functions], objectives: [...b.objectives] })),
    // The same statement can repeat across intent blocks (one per objective); show it once.
    intent: [
      ...new Map(r.intents.flatMap((i) => i.intents.map((text) => [text, { objective: i.objective, text }] as const))).values(),
    ],
    differs: r.differs,
    differsDetail: detail.length ? detail.join(" ") : undefined,
    terms,
  };
}

/** True when `row` (a sentence or clause id) belongs to the candidate provision `p` (itself or below it). */
const within = (row: string, p: string) => row === p || (row.startsWith(p) && (p.endsWith(".") || row[p.length] === "("));

export type SectionCSource = "loading" | "live" | "offline";

export interface Wanted {
  candidateId: string;
  provision: string;
}

/**
 * Section C rows from POST /section-c for the given provisions. When the engine cannot be reached or
 * rejects the request, falls back to `offline` rows (the fixture), and says so through `source`.
 */
export function useSectionC(wanted: Wanted[], offline: SectionCRow[]) {
  const key = wanted.map((w) => `${w.candidateId}=${w.provision}`).join("|");
  const [state, setState] = useState<{ key: string; source: SectionCSource; rows: SectionCRow[]; error?: string }>({
    key: "",
    source: "loading",
    rows: [],
  });

  useEffect(() => {
    if (!wanted.length) {
      setState({ key, source: "live", rows: [] });
      return;
    }
    const ctl = new AbortController();
    setState((s) => ({ ...s, key, source: "loading" }));
    engine
      .sectionC(
        wanted.map((w) => w.provision),
        ctl.signal,
      )
      .then((rows) => {
        const view = wanted.flatMap((w) => rows.filter((r) => within(r.provision_id, w.provision)).map((r) => toViewRow(r, w.candidateId)));
        setState({ key, source: "live", rows: view });
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        const ids = new Set(wanted.map((w) => w.candidateId));
        setState({ key, source: "offline", rows: offline.filter((r) => ids.has(r.candidateId)), error: String(e instanceof Error ? e.message : e) });
      });
    return () => ctl.abort();
    // `key` captures `wanted`; `offline` is the static fixture.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state.key === key ? state : { ...state, key, source: "loading" as const };
}

/** Verbatim provision text and citation from GET /code/{id}; null until loaded, or when `id` is undefined. */
export function useProvisionText(id: string | undefined) {
  const [got, setGot] = useState<{ id: string; text: string; citation: string } | null>(null);
  useEffect(() => {
    if (!id) return;
    const ctl = new AbortController();
    engine
      .provision(id, "B", ctl.signal)
      .then((r) => setGot({ id, text: r.text.replace(/\s+/g, " ").trim(), citation: r.citation }))
      .catch(() => undefined);
    return () => ctl.abort();
  }, [id]);
  return got && got.id === id ? got : null;
}
