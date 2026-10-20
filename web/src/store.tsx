import { createContext, useContext, useEffect, useMemo, useReducer, useState, type Dispatch, type ReactNode } from "react";
import type { EngineGap } from "./api/client";
import { EngineError } from "./api/client";
import { clearEngineSession, engineCaseId, ensureEngineCase, pushFacts, refreshGaps, syncJurisdiction } from "./api/sync";
import { shouldConfirmReplace } from "./rules";
import { exampleCase } from "./examples";
import { emptyCase } from "./intake";
import { getGaps, reducer, type Action } from "./model";
import type { ApplicantType, Case, Gap } from "./types";

const KEY = "batatis-web-case-v4";

interface Persisted {
  phase: "who" | "case";
  case: Case;
  note: string;
}

function load(): Persisted {
  if (new URLSearchParams(location.search).has("reset")) {
    sessionStorage.removeItem(KEY);
    clearEngineSession();
  }
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Persisted;
      const blank = emptyCase(parsed.case?.applicantType || "homebuilder");
      if (parsed.phase === "case" && parsed.case) {
        return {
          phase: "case",
          note: parsed.note ?? "",
          case: {
            ...blank,
            ...parsed.case,
            process: { ...blank.process, ...parsed.case.process },
            authority: parsed.case.authority ?? "",
            files: parsed.case.files ?? [],
            facts: parsed.case.facts ?? [],
            questions: parsed.case.questions ?? [],
            candidates: parsed.case.candidates ?? [],
            sectionC: parsed.case.sectionC ?? [],
          },
        };
      }
    }
  } catch {
    /* a new visitor starts at Who are you */
  }
  return { phase: "who", case: emptyCase("homebuilder"), note: "" };
}

interface Store {
  c: Case;
  /** Workflow gaps (unconfirmed facts, unanswered cards) plus engine gaps when the route returns. */
  gaps: Gap[];
  engineGaps: EngineGap[];
  /** engine = GET /gaps. browser = that call failed and the list is the local check. */
  gapsSource: "loading" | "engine" | "browser";
  gapsNote: string;
  engineId: string | null;
  savedNote: string;
  phase: "who" | "case";
  /** Shown after Reset so the clear is visible. */
  resetNote: string;
  dispatch: Dispatch<Action>;
  saveDraft: () => Promise<string | null>;
  beginEmpty: (type: ApplicantType) => void;
  loadExample: (id: string) => void;
  /** Opens an example, or asks first when that would wipe a case the user started. */
  askExample: (id: string) => void;
  pendingExampleId: string | null;
  confirmExample: () => void;
  dismissExample: () => void;
  resetToWho: () => void;
}

const Ctx = createContext<Store | null>(null);

const FIELD_HREF: Record<string, string> = {
  owner_name: "#/application?tab=A&focus=field-owner",
  representative: "#/application?tab=A&focus=field-representative",
  mailing_address: "#/application?tab=A&focus=field-mailingAddress",
  application_date: "#/application?tab=A&focus=field-date",
  civic_address: "#/application?tab=B&focus=field-municipalAddress",
  legal_description: "#/application?tab=B&focus=field-legalDescription",
  alternative_description: "#/application?tab=B&focus=field-alternative",
  scope: "#/application?tab=B&focus=field-scope",
  jurisdiction: "#/describe",
  rationale: "#/application?tab=alt&focus=field-rationale",
  risk_assessment: "#/application?tab=alt&focus=field-risk",
  mitigating_measures: "#/application?tab=alt&focus=field-mitigation",
  assumptions_and_limits: "#/application?tab=alt&focus=field-assumptions",
  maintenance_operation: "#/application?tab=alt&focus=field-maintenance",
  qualifications: "#/application?tab=alt&focus=field-qualifications",
  provisions: "#/code-check",
  responsible_professional: "#/application?tab=alt",
  professional_qualifications: "#/application?tab=alt&focus=field-qualifications",
  professional_requirement: "#/application?tab=D",
};

function hrefFor(field: string): string {
  if (FIELD_HREF[field]) return FIELD_HREF[field];
  if (field.startsWith("section_c") || field.startsWith("provisions")) return "#/section-c";
  if (field.startsWith("evidence") || field.startsWith("professional")) return "#/application?tab=D";
  return "#/describe";
}

export function CaseProvider({ children }: { children: ReactNode }) {
  const loaded = useMemo(load, []);
  const [phase, setPhase] = useState(loaded.phase);
  const [resetNote, setResetNote] = useState(loaded.note);
  const [c, dispatch] = useReducer(reducer, loaded.case);
  const [engineId, setEngineId] = useState<string | null>(null);
  const [engineGaps, setEngineGaps] = useState<EngineGap[]>([]);
  const [gapsSource, setGapsSource] = useState<Store["gapsSource"]>("loading");
  const [gapsNote, setGapsNote] = useState("Checking what is still missing…");
  const [savedNote, setSavedNote] = useState("");
  const [pendingExampleId, setPendingExampleId] = useState<string | null>(null);

  useEffect(() => sessionStorage.setItem(KEY, JSON.stringify({ phase, case: c, note: resetNote })), [phase, c, resetNote]);

  async function sync(announce: boolean): Promise<string | null> {
    try {
      let id = await ensureEngineCase(c.title, c.authority);
      if (c.authority) id = await syncJurisdiction(id, c.authority, c.title);
      setEngineId(id);
      const factError = await pushFacts(id, c.facts);
      const got = await refreshGaps(id);
      if (got.error && /case not found/i.test(got.error)) {
        clearEngineSession();
        setEngineId(null);
      }
      if (got.error) {
        setEngineGaps([]);
        setGapsSource("browser");
        setGapsNote(`The administrative check did not return (${got.error}). This list is what is still empty here. It is not a finding that the design complies.`);
      } else {
        setEngineGaps(got.gaps);
        setGapsSource("engine");
        setGapsNote("From the engine's administrative check. This is not a finding that the design complies.");
      }
      if (announce) {
        setSavedNote(factError ? `Draft saved. One fact was not accepted: ${factError}` : `Draft saved on the engine (${id}).`);
      }
      return id;
    } catch (e) {
      setEngineId(engineCaseId());
      setEngineGaps([]);
      setGapsSource("browser");
      const message = e instanceof EngineError ? e.detail : e instanceof Error ? e.message : String(e);
      if (e instanceof EngineError && e.status === 404 && /case not found/i.test(e.detail)) clearEngineSession();
      setGapsNote(`The engine did not take this case (${message}). This list is what is still empty here.`);
      if (announce) setSavedNote(`Draft saved in this browser. ${message}`);
      return null;
    }
  }

  useEffect(() => {
    if (phase !== "case") return;
    if (!c.facts.length && !c.authority) return;
    const handle = window.setTimeout(() => void sync(false), 500);
    return () => window.clearTimeout(handle);
    // Re-check when the applicant edits facts or picks an authority before the case exists.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, c.facts, c.authority, c.title]);

  function openCase(next: Case) {
    clearEngineSession();
    setEngineId(null);
    setEngineGaps([]);
    setGapsSource("loading");
    setGapsNote("Checking what is still missing…");
    setResetNote("");
    dispatch({ type: "reset", to: next });
    setPhase("case");
    location.hash = "#/describe";
  }

  const gaps = useMemo(() => {
    const local = getGaps(c);
    if (gapsSource !== "engine") return local;
    const admin: Gap[] = engineGaps.map((g) => ({
      id: g.id,
      severity: g.severity,
      label: g.message,
      href: hrefFor(g.field),
    }));
    const workflow = local.filter((g) => !g.id.startsWith("detail-") && !g.id.startsWith("process-"));
    return [...admin, ...workflow];
  }, [c, engineGaps, gapsSource]);

  const value = useMemo<Store>(
    () => ({
      c,
      gaps,
      engineGaps,
      gapsSource,
      gapsNote,
      engineId,
      savedNote,
      phase,
      resetNote,
      dispatch,
      saveDraft: () => sync(true),
      beginEmpty: (type) => openCase(emptyCase(type)),
      loadExample: (id) => {
        const next = exampleCase(id);
        if (next) openCase(next);
      },
      askExample: (id) => {
        if (phase === "case" && shouldConfirmReplace({ description: c.description, factCount: c.facts.length, fileCount: c.files.length })) {
          setPendingExampleId(id);
          return;
        }
        const next = exampleCase(id);
        if (next) openCase(next);
      },
      pendingExampleId,
      confirmExample: () => {
        const id = pendingExampleId;
        setPendingExampleId(null);
        const next = id ? exampleCase(id) : undefined;
        if (next) openCase(next);
      },
      dismissExample: () => setPendingExampleId(null),
      resetToWho: () => {
        clearEngineSession();
        setEngineId(null);
        setEngineGaps([]);
        setGapsSource("browser");
        setGapsNote("");
        setSavedNote("");
        dispatch({ type: "reset", to: emptyCase("homebuilder") });
        setPhase("who");
        setResetNote("Cleared. Nothing from the previous case is kept.");
        location.hash = "#/";
      },
    }),
    // sync closes over the latest case via the render that built it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [c, gaps, engineGaps, gapsSource, gapsNote, engineId, savedNote, phase, resetNote, pendingExampleId],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCase(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useCase outside CaseProvider");
  return s;
}

export function resetCase(dispatch: Dispatch<Action>) {
  clearEngineSession();
  dispatch({ type: "reset", to: emptyCase("homebuilder") });
}
