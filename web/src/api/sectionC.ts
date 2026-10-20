import { useEffect, useState } from "react";
import type { AttributionStatus, SectionCRow } from "../types";
import { engine, EngineError } from "./client";
import type { SectionCRow as EngineRow } from "./types.gen";

const STATUS: Record<EngineRow["attribution_status"], AttributionStatus> = {
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
    attributionStatus: STATUS[r.attribution_status],
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

export type SectionCSource = "loading" | "live" | "cached" | "error";

const PROVISION_ID = /^\d+(?:\.\d+)+/;

export interface Wanted {
  candidateId: string;
  provision: string;
}

/**
 * Section C rows from POST /section-c for the given provisions. When the engine cannot be reached or
 * rejects the request, falls back to `offline` rows (the fixture), and says so through `source`.
 */
export function useSectionC(wanted: Wanted[], offline: SectionCRow[], attempt = 0) {
  const real = wanted.filter((w) => PROVISION_ID.test(w.provision));
  const key = `${attempt}|` + real.map((w) => `${w.candidateId}=${w.provision}`).join("|");
  const [state, setState] = useState<{ key: string; source: SectionCSource; rows: SectionCRow[]; error?: string; status?: number }>({
    key: "",
    source: "loading",
    rows: [],
  });

  useEffect(() => {
    if (!real.length) {
      setState({ key, source: "live", rows: [] });
      return;
    }
    const ctl = new AbortController();
    setState((s) => ({ ...s, key, source: "loading" }));
    engine
      .sectionC(
        real.map((w) => w.provision),
        ctl.signal,
      )
      .then((rows) => {
        const view = real.flatMap((w) => rows.filter((r) => within(r.provision_id, w.provision)).map((r) => toViewRow(r, w.candidateId)));
        setState({ key, source: "live", rows: view });
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        const ids = new Set(real.map((w) => w.candidateId));
        const cached = offline.filter((r) => ids.has(r.candidateId));
        const status = e instanceof EngineError ? e.status : 0;
        const message = e instanceof EngineError ? e.detail : e instanceof Error ? e.message : String(e);
        if (cached.length) setState({ key, source: "cached", rows: cached, error: message, status });
        else setState({ key, source: "error", rows: [], error: message, status });
      });
    return () => ctl.abort();
    // `key` captures the provisions and the retry count.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state.key === key ? state : { ...state, key, source: "loading" as const };
}

export type ProvisionText =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "live"; text: string; citation: string }
  | { state: "error"; message: string };

/** Verbatim provision text from GET /code/{id}. An error is a state, not a permanent loading spinner. */
export function useProvisionText(id: string | undefined, attempt = 0): ProvisionText {
  const [got, setGot] = useState<{ id: string; attempt: number; value: ProvisionText }>({ id: "", attempt: -1, value: { state: "idle" } });
  useEffect(() => {
    if (!id) return;
    const ctl = new AbortController();
    setGot({ id, attempt, value: { state: "loading" } });
    engine
      .provision(id, "B", ctl.signal)
      .then((r) =>
        setGot({
          id,
          attempt,
          value: { state: "live", text: r.text.replace(/\s+/g, " ").trim(), citation: r.citation },
        }),
      )
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        const message = e instanceof Error ? e.message : "The provision text did not load.";
        setGot({ id, attempt, value: { state: "error", message } });
      });
    return () => ctl.abort();
  }, [id, attempt]);
  if (!id) return { state: "idle" };
  if (got.id !== id || got.attempt !== attempt) return { state: "loading" };
  return got.value;
}
