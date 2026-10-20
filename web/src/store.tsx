import { createContext, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from "react";
import { EngineError, type EngineGap } from "./api/client";
import { type CompletenessRecord } from "./humanReview";
import { clearEngineSession, engineCaseId, ensureEngineCase, pushDeletedEvidence, pushFacts, pushListedEvidence, refreshGaps, syncJurisdiction } from "./api/sync";
import { engineNotices, groupEvidenceGaps, missingFromEngine, shouldConfirmReplace } from "./rules";
import { exampleCase } from "./examples";
import { emptyCase } from "./intake";
import { gapLabel, getGaps, reducer, type Action } from "./model";
import { caseForRole, initialVisit } from "./visit";
import type { ApplicantType, Case, Gap } from "./types";

/** Older builds kept the whole case here. It is removed on load and never written again. */
const LEGACY_KEYS = ["batatis-web-case-v4", "batatis-web-case-v3"];

/** A cold visit starts empty. Nothing about a previous visitor's case is read or kept in this browser. */
function load() {
  try {
    for (const key of LEGACY_KEYS) sessionStorage.removeItem(key);
    clearEngineSession();
  } catch {
    /* storage unavailable: nothing to clear */
  }
  return initialVisit();
}

interface Store {
  c: Case;
  /** Workflow gaps (unconfirmed facts, unanswered cards) plus engine gaps when the route returns. */
  gaps: Gap[];
  /** Engine `info` items. Shown as notices, never counted as missing. */
  notices: string[];
  engineGaps: EngineGap[];
  /** idle = no review requested. engine = online result. browser = limited local check. */
  gapsSource: "idle" | "loading" | "engine" | "browser";
  gapsNote: string;
  /** Raw failure text for a collapsed technical detail. Not shown as the status line. */
  reviewDetail: string;
  /** True only after the latest save and online review both succeeded. */
  syncOk: boolean;
  /** Latest save/review outcome. Safe to read after `await saveDraft()` from an older render. */
  readSync: () => { reviewed: boolean; detail: string };
  engineId: string | null;
  /** Increments after facts are pushed, so Section D can reload on the new facts. */
  factsEpoch: number;
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
  completenessRecord: CompletenessRecord | null;
  setCompletenessRecord: (record: CompletenessRecord | null) => void;
  /** Gap list from the latest review, including one that has not re-rendered yet. */
  readGaps: () => Gap[];
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
  professional_qualifications: "#/application?tab=alt&focus=field-qualifications",
  professional_requirement: "#/application?tab=D&focus=prof-role",
  responsible_professional: "#/application?tab=D&focus=prof-role",
};

const FIELD_ALIASES: Record<string, string[]> = {
  owner_name: ["owner_name", "owner", "section_a.owner_name"],
  owner: ["owner_name", "owner", "section_a.owner_name"],
  representative: ["representative", "section_a.representative"],
  mailing_address: ["mailing_address", "mailingAddress", "section_a.mailing_address"],
  mailingAddress: ["mailing_address", "mailingAddress"],
  application_date: ["application_date", "date"],
  date: ["application_date", "date"],
  civic_address: ["civic_address", "municipalAddress"],
  municipalAddress: ["civic_address", "municipalAddress"],
  legal_description: ["legal_description", "legalDescription"],
  legalDescription: ["legal_description", "legalDescription"],
  alternative_description: ["alternative_description", "alternative"],
  alternative: ["alternative_description", "alternative"],
  scope: ["scope"],
  "assembly.cavityRsi": ["assembly.cavityRsi"],
  "professional.role": ["professional.role", "professional_requirement", "responsible_professional"],
  professional_requirement: ["professional.role", "professional_requirement", "responsible_professional"],
  responsible_professional: ["professional.role", "professional_requirement", "responsible_professional"],
};

function aliasKeys(field: string): string[] {
  return FIELD_ALIASES[field] ?? [field];
}

function composeGaps(localCase: Case, source: Store["gapsSource"], engine: EngineGap[]): Gap[] {
  const local = getGaps(localCase);
  if (source !== "engine") return local;
  const seen = new Set<string>();
  const admin: Gap[] = [];
  for (const g of missingFromEngine(groupEvidenceGaps(engine))) {
    const keys = aliasKeys(g.field);
    if (keys.some((key) => seen.has(key))) continue;
    for (const key of keys) seen.add(key);
    admin.push({
      id: g.id,
      severity: g.severity,
      label: gapLabel(g.message, g.fix_hint),
      href: hrefFor(g.field),
      field: g.field,
    });
  }
  const workflow = local.filter((g) => {
    if (g.id.startsWith("detail-") || g.id.startsWith("process-")) return false;
    if (!g.field) return true;
    return !aliasKeys(g.field).some((key) => seen.has(key));
  });
  return [...admin, ...workflow];
}

function hrefFor(field: string): string {
  if (FIELD_HREF[field]) return FIELD_HREF[field];
  if (field.startsWith("section_c") || field.startsWith("provisions")) return "#/section-c";
  if (field.startsWith("evidence") || field.startsWith("professional")) return "#/application?tab=D";
  return "#/describe";
}

export function CaseProvider({ children }: { children: ReactNode }) {
  const loaded = useMemo(load, []);
  const [phase, setPhase] = useState<"who" | "case">(loaded.phase);
  const [resetNote, setResetNote] = useState(loaded.note);
  const [c, dispatch] = useReducer(reducer, loaded.case);
  const [engineId, setEngineId] = useState<string | null>(null);
  const [factsEpoch, setFactsEpoch] = useState(0);
  const [engineGaps, setEngineGaps] = useState<EngineGap[]>([]);
  const [gapsSource, setGapsSource] = useState<Store["gapsSource"]>("idle");
  const [gapsNote, setGapsNote] = useState("Your application has not been reviewed online yet.");
  const [reviewDetail, setReviewDetail] = useState("");
  const [syncOk, setSyncOk] = useState(false);
  const syncState = useRef({ reviewed: false, detail: "" });
  const [savedNote, setSavedNote] = useState("");
  const [pendingExampleId, setPendingExampleId] = useState<string | null>(null);
  const [completenessRecord, setCompletenessRecord] = useState<CompletenessRecord | null>(null);
  const latestGaps = useRef<Gap[]>([]);

  function reviewingCopy() {
    return c.exampleId ? "Reviewing this example…" : "Reviewing your application…";
  }

  async function sync(announce: boolean): Promise<string | null> {
    setGapsSource("loading");
    setGapsNote(reviewingCopy());
    setSyncOk(false);
    if (!announce) setSavedNote("");
    try {
      let id = await ensureEngineCase(c.title, c.authority);
      if (c.authority) id = await syncJurisdiction(id, c.authority, c.title);
      setEngineId(id);
      const factError = await pushFacts(id, c.facts);
      const evidenceError = await pushListedEvidence(id, c.listedEvidence ?? []);
      const deleted = await pushDeletedEvidence(id, c.deletedEvidence ?? []);
      if (deleted.acked.length) dispatch({ type: "ackEvidenceDeletion", ids: deleted.acked });
      setFactsEpoch((n) => n + 1);
      const got = await refreshGaps(id);
      if (got.error && /case not found/i.test(got.error)) {
        clearEngineSession();
        setEngineId(null);
      }
      if (got.error) {
        setEngineGaps([]);
        setGapsSource("browser");
        setReviewDetail(got.error);
        setGapsNote("Online review unavailable. Showing a limited check of fields in this browser.");
        setSyncOk(false);
        latestGaps.current = composeGaps(c, "browser", []);
      } else {
        setEngineGaps(got.gaps);
        setGapsSource("engine");
        setReviewDetail(factError ?? evidenceError ?? deleted.error ?? "");
        setGapsNote("Online administrative review finished. This does not decide whether the design complies or is safe.");
        setSyncOk(!factError && !evidenceError && !deleted.error);
        latestGaps.current = composeGaps(c, "engine", got.gaps);
      }
      if (announce) {
        setSavedNote(got.error || factError ? "Draft saved in this browser." : "Draft saved.");
      }
      syncState.current = { reviewed: !got.error && !factError, detail: got.error || factError || "" };
      return id;
    } catch (e) {
      setEngineId(engineCaseId());
      setEngineGaps([]);
      setGapsSource("browser");
      const message = e instanceof EngineError ? e.detail : e instanceof Error ? e.message : String(e);
      if (e instanceof EngineError && e.status === 404 && /case not found/i.test(e.detail)) clearEngineSession();
      setReviewDetail(message);
      setGapsNote("Online review unavailable. Showing a limited check of fields in this browser.");
      setSyncOk(false);
      latestGaps.current = composeGaps(c, "browser", []);
      syncState.current = { reviewed: false, detail: message };
      if (announce) setSavedNote("Draft saved in this browser.");
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
  }, [phase, c.facts, c.authority, c.title, c.listedEvidence, c.deletedEvidence]);

  function openCase(next: Case) {
    clearEngineSession();
    setEngineId(null);
    setEngineGaps([]);
    setSyncOk(false);
    setSavedNote("");
    setReviewDetail("");
    setCompletenessRecord(null);
    const blank = !next.facts.length && !next.authority;
    setGapsSource(blank ? "idle" : "loading");
    setGapsNote(blank ? "Your application has not been reviewed online yet." : next.exampleId ? "Reviewing this example…" : "Reviewing your application…");
    setResetNote("");
    dispatch({ type: "reset", to: next });
    setPhase("case");
    location.hash = "#/describe";
  }

  const gaps = useMemo(() => composeGaps(c, gapsSource, engineGaps), [c, engineGaps, gapsSource]);
  const notices = useMemo(() => (gapsSource === "engine" ? engineNotices(engineGaps) : []), [engineGaps, gapsSource]);
  useEffect(() => {
    latestGaps.current = gaps;
  }, [gaps]);

  const value = useMemo<Store>(
    () => ({
      c,
      gaps,
      notices,
      engineGaps,
      gapsSource,
      gapsNote,
      reviewDetail,
      syncOk,
      readSync: () => syncState.current,
      engineId,
      factsEpoch,
      savedNote,
      phase,
      resetNote,
      dispatch,
      saveDraft: () => sync(true),
      beginEmpty: (type) => openCase(caseForRole(type, c)),
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
      completenessRecord,
      setCompletenessRecord,
      readGaps: () => latestGaps.current,
      resetToWho: () => {
        clearEngineSession();
        setEngineId(null);
        setEngineGaps([]);
        setGapsSource("idle");
        setGapsNote("");
        setReviewDetail("");
        setSyncOk(false);
        setSavedNote("");
        setCompletenessRecord(null);
        dispatch({ type: "reset", to: emptyCase("homebuilder") });
        setPhase("who");
        setResetNote("Cleared. Nothing from the previous case is kept.");
        location.hash = "#/";
      },
    }),
    // sync closes over the latest case via the render that built it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [c, gaps, notices, engineGaps, gapsSource, gapsNote, reviewDetail, syncOk, engineId, factsEpoch, savedNote, phase, resetNote, pendingExampleId, completenessRecord],
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
