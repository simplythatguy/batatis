import { useEffect, useRef, useState, type ReactNode } from "react";
import { EngineError, engine } from "../api/client";
import {
  MODE_LABEL,
  articleKey,
  articlePairs,
  benchmarkQuote,
  groupPairs,
  measuredComparison,
  printChip,
  quoteOf,
  runDetail,
  type IdentifyAnswer,
  type IdentifyArticle,
  type IdentifyResult,
} from "../api/identify";
import { GapStrip, Icon, PanelHeader, StatusPill, type Dot } from "../components";
import { DEMO_DESCRIPTIONS } from "../demoDescriptions";
import { CODE_TERMS } from "../fixture";
import { OFFICER_QUESTION_ID, acceptedArticles } from "../model";
import { useCase } from "../store";
import type { AttributionPair, Candidate, CandidateAnswer, CodeIdAnswer, CodeIdRun } from "../types";

// —— Shared wording: one question that reads the same for a homebuilder, a manufacturer and a contractor ——

const ASK = "Is this the requirement your project does differently?";
const MEASURED_HELP =
  "“Measured against” means the requirement a standard design would follow. A variance explains how your project does it differently.";

const ANSWERS: { value: CodeIdAnswer; label: string }[] = [
  { value: "yes", label: "Yes, we do this differently" },
  { value: "not-sure", label: "Not sure" },
  { value: "no", label: "Doesn't apply to us" },
];

const ANSWER_STATUS: Record<CodeIdAnswer, { dot: Dot; label: string }> = {
  yes: { dot: "done", label: "Goes to Section C" },
  "not-sure": { dot: "warning", label: "Not sure · question recorded" },
  no: { dot: "pending", label: "Doesn't apply" },
};

const VERIFIER: Record<IdentifyArticle["verifier_status"], { dot: Dot; label: string; help: string }> = {
  committed: { dot: "done", label: "Verifier confirmed the match", help: "The verifier checked that this article matches your description. It is not a compliance finding." },
  candidate: { dot: "pending", label: "Suggested · verifier did not confirm", help: "The verifier ran and did not confirm this article. Decide for yourself whether it applies." },
  unknown: { dot: "pending", label: "Not verified in this run", help: "Keyword matches and cached demo runs do not re-run the verifier." },
};

function AnswerButtons({ label, value, onChange }: { label: string; value: CodeIdAnswer | null; onChange: (v: CodeIdAnswer | null) => void }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {ANSWERS.map((o) => (
        <button
          key={o.value}
          type="button"
          className="btn"
          aria-pressed={value === o.value}
          // Pressing the chosen answer again clears it: no card forces a pick.
          onClick={() => onChange(value === o.value ? null : o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function CodeText({ text, clipped, citation, chip }: { text: string; clipped: boolean; citation?: string | null; chip?: string | null }) {
  return (
    <div className="code-said">
      <div className="block-label">
        <span className="label-pill">Code text</span>
        {chip && <span className="label-pill">{chip}</span>}
        {citation && <span className="meta mono-cite">{citation}</span>}
      </div>
      <blockquote className="cite-block quote">
        {text}
        {clipped && <span className="clip-mark"> … [clipped — full text in the code]</span>}
      </blockquote>
    </div>
  );
}

function PairList({ pairs, terms }: { pairs: AttributionPair[]; terms: Record<string, string> }) {
  const term = (code: string) => terms[code] ?? CODE_TERMS[code];
  return (
    <ul className="plain-list pairs">
      {pairs.map((p) => (
        <li key={p.bracket}>
          <span className="pair-group">
            {p.objectives.map((o) => (
              <abbr key={o} className="code-term" title={term(o)}>
                {o}
              </abbr>
            ))}
          </span>
          {p.objectives.length > 0 && p.functions.length > 0 && <span className="meta">·</span>}
          <span className="pair-group">
            {p.functions.map((f) => (
              <abbr key={f} className="code-term" title={term(f)}>
                {f}
              </abbr>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ObjectiveFunction({ pairs, terms }: { pairs: AttributionPair[]; terms: Record<string, string> }) {
  return (
    <div className="of-row">
      <span className="meta of-label">Objective · function</span>
      {pairs.length ? <PairList pairs={pairs} terms={terms} /> : <span className="muted-text">Objective/function lookup not available for this article</span>}
    </div>
  );
}

function Explanation({ text, source }: { text: string; source: "deterministic" | "ai_written" }) {
  return (
    <section className="explain-block" data-source={source}>
      <div className="block-label">
        <span className="label-pill">Explanation</span>
        {source === "ai_written" && <span className="label-pill ai-pill">AI-written</span>}
        <span className="meta">
          {source === "ai_written" ? "Not a finding about your design" : "Built from the code database · not a finding about your design"}
        </span>
      </div>
      <p className="ai-explain">{text}</p>
    </section>
  );
}

function ArticleCard({
  a,
  r,
  run,
  benchmark,
  onAnswer,
}: {
  a: IdentifyArticle;
  r: IdentifyResult;
  run: CodeIdRun;
  benchmark: boolean;
  onAnswer: (provision: string, v: CodeIdAnswer | null) => void;
}) {
  const [showFull, setShowFull] = useState(false);
  const answer = run.answers[a.provision] ?? null;
  const q = quoteOf(a);
  const shown = showFull && q?.full ? q.full : q;
  const { pairs, terms } = articlePairs(r, a);
  const chip = printChip(a);
  const v = VERIFIER[a.verifier_status] ?? VERIFIER.unknown;
  const question = run.questions.find((x) => x.provision === a.provision);
  const why = benchmark ? r.benchmark.explanation ?? a.why : a.why;
  const conf = a.confidence;
  return (
    <article className="card id-card" data-benchmark={benchmark} id={`card-${a.provision}`} tabIndex={-1} aria-labelledby={`card-${a.provision}-title`}>
      {benchmark && (
        <div className="bench-head">
          <span className="label-pill bench-pill">Measured against</span>
          <span className="meta">{MEASURED_HELP}</span>
        </div>
      )}
      <div className="card-head">
        <span className="meta rank">#{a.rank}</span>
        <h2 className="card-topic" id={`card-${a.provision}-title`}>
          {a.title}
        </h2>
        {answer && <StatusPill dot={ANSWER_STATUS[answer].dot}>{ANSWER_STATUS[answer].label}</StatusPill>}
      </div>
      <div className="id-line">
        <span className="article-id">{a.provision_id ?? a.provision}</span>
        {a.provision_id && <span className="meta">Article {a.provision}</span>}
        <span className="label-pill" title={v.help}>
          <span className={`status-dot ${v.dot}`} />
          {v.label}
        </span>
      </div>
      {benchmark && <Measured r={r} />}
      {shown ? (
        <>
          <CodeText text={shown.text} clipped={shown.clipped} citation={a.citation} chip={chip} />
          {q?.full && (
            <button type="button" className="btn btn-ghost btn-xs show-more" aria-expanded={showFull} onClick={() => setShowFull(!showFull)}>
              {showFull ? "Show the 25-word extract" : "Show the longer stored quote"}
            </button>
          )}
        </>
      ) : (
        <p className="muted-text">No code text was returned for this article.{a.citation ? ` Citation: ${a.citation}` : ""}</p>
      )}
      <ObjectiveFunction pairs={pairs} terms={terms} />
      {a.explainer?.text && <Explanation text={a.explainer.text} source={a.explainer.source} />}
      {why && <p className="meta why">Why it was suggested: {why}</p>}
      <div className="ask-block">
        <p className="ask">{ASK}</p>
        <AnswerButtons label={`${ASK} ${a.title}`} value={answer} onChange={(val) => onAnswer(a.provision, val)} />
      </div>
      {answer === "not-sure" && question && (
        <div className="followup" id={`q-${question.id}`}>
          <div className="meta">Question added to your case</div>
          <p>{question.text}</p>
          <p className="meta">{question.why}</p>
        </div>
      )}
      <details className="disclosure ref">
        <summary>
          <Icon name="chevron" size={12} />
          <span className="disclosure-title">Code reference</span>
        </summary>
        <dl className="ref-grid">
          <dt>Article</dt>
          <dd className="article-id">{a.provision}</dd>
          {a.provision_id && (
            <>
              <dt>Sentence</dt>
              <dd className="article-id">{a.provision_id}</dd>
            </>
          )}
          {a.citation && (
            <>
              <dt>Citation</dt>
              <dd className="mono">{a.citation}</dd>
            </>
          )}
          {a.part != null && (
            <>
              <dt>Part</dt>
              <dd>Part {a.part}</dd>
            </>
          )}
          {a.division && (
            <>
              <dt>Division</dt>
              <dd>Division {a.division}</dd>
            </>
          )}
          {conf && (
            <>
              <dt>Match probability</dt>
              <dd>
                {conf.probability != null ? `${Math.round(conf.probability * 100)}%` : "Not given"}
                {conf.calibration === "placeholder_uncalibrated" ? " · not calibrated yet" : ""}
              </dd>
            </>
          )}
        </dl>
      </details>
    </article>
  );
}

/** The measured comparison slot. Renders only when the engine returns every value; absent in #12. */
function Measured({ r }: { r: IdentifyResult }) {
  const m = measuredComparison(r.benchmark);
  if (!m) return null;
  return (
    <div className="measured">
      <span className="label-pill">Measured</span>
      <span>
        <span className="article-id">{m.provision_id}</span>: <strong>{m.proposed}</strong> where the code asks <strong>{m.required}</strong>
      </span>
      {m.comparison && <span className="meta">{m.comparison}</span>}
      {m.snippet && <blockquote className="cite-block quote measured-quote">{m.snippet}</blockquote>}
    </div>
  );
}

/** The benchmark when it is not one of the ranked articles, or when none was identified. */
function BenchmarkOnly({ r }: { r: IdentifyResult }) {
  const b = r.benchmark;
  if (!b.identified) {
    return (
      <article className="card id-card" data-benchmark="true">
        <div className="bench-head">
          <span className="label-pill bench-pill">Measured against</span>
          <span className="meta">{MEASURED_HELP}</span>
        </div>
        <h2 className="card-topic">No benchmark article identified yet</h2>
        <p className="ask-sub">{b.question ?? "The engine did not name the requirement this project is measured against. Check the cards below, or ask the officer."}</p>
      </article>
    );
  }
  const q = benchmarkQuote(b);
  const pairs = groupPairs(b.section_c.flatMap((x) => x.pairs));
  return (
    <article className="card id-card" data-benchmark="true">
      <div className="bench-head">
        <span className="label-pill bench-pill">Measured against</span>
        <span className="meta">{MEASURED_HELP}</span>
      </div>
      <div className="id-line">
        <span className="article-id">{b.provision_id ?? b.section_c[0]?.provision_id ?? b.provision}</span>
        {b.provision && <span className="meta">Article {b.provision}</span>}
      </div>
      <Measured r={r} />
      {q && <CodeText text={q.text} clipped={q.clipped} citation={b.citation} chip={printChip(b)} />}
      <ObjectiveFunction pairs={pairs} terms={{}} />
      {b.explanation && <p className="meta why">{b.explanation}</p>}
    </article>
  );
}

function NoneFit({ asked, onAsk }: { asked: boolean; onAsk: (v: boolean) => void }) {
  return (
    <section className="card none-fit" id="none-fit" tabIndex={-1} aria-labelledby="none-fit-title">
      <div className="card-head">
        <h2 className="card-topic" id="none-fit-title">
          None of these fit?
        </h2>
        {asked && <StatusPill dot="warning">Question recorded for the officer</StatusPill>}
      </div>
      <p className="ask-sub">
        {asked
          ? "Recorded: “None of the suggested articles fit this project. Which requirement should it be measured against?” It stays an open question in your application. You can continue."
          : "Record an open question for your Safety Codes Officer instead of picking a card. You can still continue."}
      </p>
      <div className="btn-row">
        {asked ? (
          <button type="button" className="btn btn-ghost" onClick={() => onAsk(false)}>
            Remove the question
          </button>
        ) : (
          <button type="button" className="btn" onClick={() => onAsk(true)}>
            None of these fit · ask the officer
          </button>
        )}
      </div>
    </section>
  );
}

function NarrowingQuestions({ r, busy, onRun }: { r: IdentifyResult; busy: boolean; onRun: (answers: IdentifyAnswer[]) => void }) {
  const [vals, setVals] = useState<Record<string, string>>({});
  const qs = r.open_questions ?? [];
  if (!qs.length) return null;
  const answers = Object.entries(vals)
    .filter(([, v]) => v.trim())
    .map(([field, answer]) => ({ field, answer: answer.trim() }));
  return (
    <details className="disclosure">
      <summary>
        <Icon name="chevron" size={12} />
        <span className="disclosure-title">Questions that narrow the search</span>
        <span className="meta">{qs.length} from the engine · optional</span>
      </summary>
      <form
        className="narrow"
        onSubmit={(e) => {
          e.preventDefault();
          if (answers.length) onRun(answers);
        }}
      >
        {qs.map((q) => {
          const id = `narrow-${q.field}`;
          return (
            <div key={q.field} className="field">
              <label htmlFor={id}>{q.text}</label>
              <div className="narrow-row">
                <input id={id} value={vals[q.field] ?? q.answer ?? ""} onChange={(e) => setVals({ ...vals, [q.field]: e.target.value })} placeholder="Your answer" />
                <button type="button" className="btn btn-ghost" onClick={() => setVals({ ...vals, [q.field]: "not sure" })}>
                  Not sure
                </button>
              </div>
              <span className="field-note">{q.why}</span>
            </div>
          );
        })}
        <div className="btn-row">
          <button type="submit" className="btn" disabled={busy || !answers.length}>
            Find again with these answers
          </button>
          {!answers.length && <span className="field-note">Answer at least one question first</span>}
        </div>
      </form>
    </details>
  );
}

function DemoChips({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="demo-row" role="group" aria-labelledby="demo-label">
      <span className="meta" id="demo-label">
        Try an example description:
      </span>
      {DEMO_DESCRIPTIONS.map((d) => (
        <button key={d.id} type="button" className="btn demo-chip" title={d.text} aria-label={`Paste example description: ${d.label} (${d.who})`} onClick={() => onPick(d.text)}>
          {d.label}
          <span className="meta">{d.who}</span>
        </button>
      ))}
    </div>
  );
}

type RunState = { state: "idle" } | { state: "running" } | { state: "error"; error: unknown };

function errorText(e: unknown): { title: string; body: string } {
  if (e instanceof EngineError) {
    if (e.status === 0) return { title: "The engine is not reachable", body: `Batatis could not reach the engine (${e.detail}). Check that it is running, then retry.` };
    if (e.status === 503) return { title: "The engine could not search the code", body: `The engine answered 503: ${e.detail}. Retry once the code database is available.` };
    if (e.status >= 500) return { title: "The engine hit an error", body: `The engine answered ${e.status}: ${e.detail}. Retry in a moment.` };
    return { title: "The engine rejected the request", body: `The engine answered ${e.status}: ${e.detail}.` };
  }
  return { title: "Something went wrong", body: e instanceof Error ? e.message : String(e) };
}

function Results({
  run,
  busy,
  onAnswer,
  onRerun,
  onEdit,
}: {
  run: CodeIdRun;
  busy: boolean;
  onAnswer: (provision: string, v: CodeIdAnswer | null) => void;
  onRerun: (answers: IdentifyAnswer[]) => void;
  onEdit: () => void;
}) {
  const { dispatch } = useCase();
  const r = run.result;
  const bench = r.benchmark?.identified ? r.articles.find((a) => a.provision === r.benchmark.provision) : undefined;
  const rest = r.articles.filter((a) => a !== bench);
  const asked = run.questions.some((q) => q.id === OFFICER_QUESTION_ID);
  const dot: Dot = r.mode === "live" ? "done" : r.mode === "cached_demo" ? "pending" : "warning";
  return (
    <section className="stack" aria-label="Code ID results">
      <div className="sc-source run-source">
        <span className="label-pill">
          <span className={`status-dot ${dot}`} />
          {MODE_LABEL[r.mode] ?? r.mode}
        </span>
        <span className="meta">{runDetail(r)}</span>
      </div>
      {r.intake_action === "redirect" && r.redirect_to && (
        <p className="field-note notice-line">
          <span className="status-dot warning" />
          This request belongs to the {r.redirect_to} regime rather than the building code. Ask your Safety Codes Officer where to apply.
        </p>
      )}
      {r.variance_explanation && <p className="meta intro variance-note">{r.variance_explanation}</p>}

      {r.articles.length === 0 ? (
        <div className="card">
          <h2 className="card-topic">No article found</h2>
          <p className="ask-sub">
            {r.mode === "bm25_fallback"
              ? "Keyword search ran without an AI key and returned no article. The code database may be unavailable on this engine. Nothing was committed and no card is shown."
              : "The engine returned no article for this description. No card is shown."}
          </p>
          <div className="btn-row">
            <button type="button" className="btn" onClick={onEdit}>
              Edit the description
            </button>
            <span className="meta">or try one of the example descriptions above.</span>
          </div>
        </div>
      ) : (
        <>
          {r.mode === "bm25_fallback" && (
            <p className="field-note notice-line">
              <span className="status-dot warning" />
              Keyword matches only. No AI model checked these cards and nothing is committed; decide each one yourself.
            </p>
          )}
          {bench ? (
            <ArticleCard a={bench} r={r} run={run} benchmark onAnswer={onAnswer} />
          ) : (
            (r.benchmark?.identified === false || r.benchmark?.provision) && <BenchmarkOnly r={r} />
          )}
          {rest.length > 0 && (
            <h3 className="sub-title">{bench ? "Other articles that may apply" : "Articles that may apply"}</h3>
          )}
          {rest.map((a) => (
            <ArticleCard key={a.provision} a={a} r={r} run={run} benchmark={false} onAnswer={onAnswer} />
          ))}
        </>
      )}
      <NoneFit asked={asked} onAsk={(ask) => dispatch({ type: "askOfficer", ask })} />
      <NarrowingQuestions key={r.generated_at ?? run.prose} r={r} busy={busy} onRun={onRerun} />
    </section>
  );
}

// —— Fixture example cards: the earlier Code check, with the same plain wording ——

const FIXTURE_ANSWERS: { value: CandidateAnswer; label: string }[] = [
  { value: "yes", label: "Yes, we do this differently" },
  { value: "not-sure", label: "Not sure" },
  { value: "no", label: "Doesn't apply to us" },
];

const FIXTURE_STATUS: Record<CandidateAnswer, { dot: Dot; label: string }> = {
  yes: { dot: "done", label: "Done differently" },
  no: { dot: "pending", label: "Doesn't apply" },
  "not-sure": { dot: "warning", label: "Not sure yet" },
};

function ExampleCard({ a, index, total }: { a: Candidate; index: number; total: number }) {
  const { dispatch } = useCase();
  const s = a.answer && FIXTURE_STATUS[a.answer];
  return (
    <article className="card" id={`cand-${a.id}`} tabIndex={-1} aria-labelledby={`cand-${a.id}-topic`}>
      {a.benchmark && (
        <div className="bench-head">
          <span className="label-pill bench-pill">Measured against</span>
          <span className="meta">{MEASURED_HELP}</span>
        </div>
      )}
      <div className="card-head">
        <span className="meta">
          {index + 1} of {total}
        </span>
        <h2 className="card-topic" id={`cand-${a.id}-topic`}>
          {a.topic}
        </h2>
        <span className="label-pill">Example data (fictional)</span>
        {s && <StatusPill dot={s.dot}>{s.label}</StatusPill>}
      </div>
      <CodeText text={a.quote.text} clipped={false} citation={a.quote.citation} chip={printChip(a.quote)} />
      <div className="ask-block">
        <p className="ask">{ASK}</p>
        <p className="ask-sub">
          <span className="label-pill ai-pill">AI-written</span> Our reading of the description: you {a.departure}.
        </p>
        <div className="segmented" role="group" aria-label={`${ASK} ${a.topic}`}>
          {FIXTURE_ANSWERS.map((o) => (
            <button
              key={o.value}
              type="button"
              className="btn"
              aria-pressed={a.answer === o.value}
              onClick={() => dispatch({ type: "answerCandidate", id: a.id, answer: o.value })}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>
      {a.answer === "not-sure" && (
        <div className="followup">
          <div className="meta">Worth checking</div>
          <p>{a.clarifyingQuestion}</p>
          <p className="meta">You can continue without answering; it stays listed as an open item.</p>
        </div>
      )}
      <details className="disclosure ref">
        <summary>
          <Icon name="chevron" size={12} />
          <span className="disclosure-title">Code reference</span>
        </summary>
        <dl className="ref-grid">
          <dt>Provision</dt>
          <dd className="article-id">{a.provision}</dd>
          <dt>Citation</dt>
          <dd className="mono">{a.quote.citation}</dd>
          <dt>Part</dt>
          <dd>Part {a.part}</dd>
        </dl>
      </details>
    </article>
  );
}

function Section({ title, meta, children }: { title: string; meta?: ReactNode; children: ReactNode }) {
  return (
    <section className="stack">
      <div className="ledger-head">
        <h2 className="section-title">{title}</h2>
        {meta && <span className="meta">{meta}</span>}
      </div>
      {children}
    </section>
  );
}

export function CodeCheck() {
  const { c, gaps, dispatch } = useCase();
  const [draft, setDraft] = useState(() => c.codeId?.prose ?? c.description);
  const [run, setRun] = useState<RunState>({ state: "idle" });
  const [saving, setSaving] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const findBtn = useRef<HTMLButtonElement>(null);
  const ctl = useRef<AbortController | null>(null);
  useEffect(() => () => ctl.current?.abort(), []);

  const busy = run.state === "running";
  const codeId = c.codeId;

  async function find(prose: string, answers: IdentifyAnswer[] = []) {
    const text = prose.trim();
    if (!text) return;
    ctl.current?.abort();
    const ac = new AbortController();
    ctl.current = ac;
    setRun({ state: "running" });
    const fresh = async () => {
      const k = await engine.createCase({ title: c.title }, ac.signal);
      dispatch({ type: "setEngineCase", id: k.id });
      return k.id;
    };
    try {
      let id = c.engineCaseId ?? (await fresh());
      let result: IdentifyResult;
      try {
        result = await engine.identify(id, text, answers, ac.signal);
      } catch (e) {
        // The engine keeps cases in memory; after a restart the stored id is gone. Make a new one once.
        if (!(e instanceof EngineError && e.status === 404)) throw e;
        id = await fresh();
        result = await engine.identify(id, text, answers, ac.signal);
      }
      dispatch({ type: "identified", prose: text, result });
      setRun({ state: "idle" });
    } catch (e) {
      if (!ac.signal.aborted) setRun({ state: "error", error: e });
    }
  }

  function cancel() {
    ctl.current?.abort();
    setRun({ state: "idle" });
  }

  /** Record the answer locally, then ask the engine to write Section C. Never blocks on the engine. */
  async function answer(provision: string, value: CodeIdAnswer | null) {
    if (!codeId) return;
    dispatch({ type: "answerArticle", provision, answer: value });
    const was = codeId.answers[provision] === "yes";
    if (was === (value === "yes")) return;
    const provisions = codeId.result.articles
      .filter((a) => (a.provision === provision ? value === "yes" : codeId.answers[a.provision] === "yes"))
      .map(articleKey);
    if (!provisions.length) return;
    if (!c.engineCaseId) {
      dispatch({ type: "codeIdConfirmed", confirm: { ok: false, provisions, detail: "no engine case yet" } });
      return;
    }
    setSaving(true);
    try {
      await engine.confirmIdentify(c.engineCaseId, provisions);
      dispatch({ type: "codeIdConfirmed", confirm: { ok: true, provisions } });
    } catch (e) {
      const detail = e instanceof EngineError ? (e.status ? `${e.status}: ${e.detail}` : "engine not reachable") : String(e);
      dispatch({ type: "codeIdConfirmed", confirm: { ok: false, provisions, detail } });
    } finally {
      setSaving(false);
    }
  }

  const pick = (text: string) => {
    setDraft(text);
    findBtn.current?.focus();
  };
  const edit = () => {
    textarea.current?.focus();
    textarea.current?.scrollIntoView({ block: "center" });
  };

  const accepted = codeId ? acceptedArticles(codeId) : [];
  const recorded = codeId?.questions.length ?? 0;
  const stale = codeId && draft.trim() !== codeId.prose;
  const err = run.state === "error" ? errorText(run.error) : null;

  const footerNote = codeId
    ? [
        accepted.length ? `${accepted.length} article${accepted.length > 1 ? "s" : ""} go${accepted.length > 1 ? "" : "es"} to Section C` : "No article chosen yet",
        recorded ? `${recorded} open question${recorded > 1 ? "s" : ""}` : "",
        "you can continue",
      ]
        .filter(Boolean)
        .join(" · ")
    : "Example data until you find articles · you can continue";

  return (
    <>
      <PanelHeader title="Code ID" meta="NBC(AE) 2023 · 2nd printing · Division B" />
      <GapStrip gaps={gaps} />
      <div className="pane scroll-body">
        <div className="content-col stack">
          <section className="id-describe" aria-labelledby="codeid-prose-label">
            <div className="field">
              <label htmlFor="codeid-prose" id="codeid-prose-label" className="lead-label">
                Describe the project in your own words
              </label>
              <textarea
                ref={textarea}
                id="codeid-prose"
                className="describe-text"
                rows={4}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="What are you building, installing or selling, and what do you want to do differently?"
              />
            </div>
            <div className="btn-row">
              <button
                ref={findBtn}
                type="button"
                className={`btn ${codeId ? "" : "btn-primary"}`}
                disabled={busy || !draft.trim()}
                onClick={() => find(draft)}
              >
                {busy ? "Finding articles…" : codeId ? "Find again" : "Find articles"}
              </button>
              {busy && (
                <button type="button" className="btn btn-ghost" onClick={cancel}>
                  Cancel
                </button>
              )}
              {!draft.trim() && <span className="field-note">Type a description first</span>}
              {c.description.trim() && draft.trim() !== c.description.trim() && !busy && (
                <button type="button" className="btn btn-ghost btn-xs" onClick={() => setDraft(c.description)}>
                  Use my Describe text
                </button>
              )}
            </div>
            <DemoChips onPick={pick} />
          </section>

          {busy && (
            <div className="card run-card" role="status">
              <span className="status-dot pending pulse" />
              <span>Finding articles in Division B for your description… A live run can take up to a minute.</span>
            </div>
          )}

          {err && !busy && (
            <div className="card run-card error-card" role="alert">
              <div className="card-head">
                <StatusPill dot="blocking">{err.title}</StatusPill>
              </div>
              <p className="ask-sub">
                {err.body} No articles are shown for this attempt because none were returned.
                {codeId ? " The results below are from your previous run." : ""}
              </p>
              <div className="btn-row">
                <button type="button" className="btn" onClick={() => find(draft)} disabled={!draft.trim()}>
                  Retry
                </button>
              </div>
            </div>
          )}

          {codeId ? (
            <>
              {stale && !busy && (
                <p className="field-note notice-line" role="status">
                  <span className="status-dot warning" />
                  You changed the description after this run. Select Find again to update the cards.
                </p>
              )}
              {codeId.confirm && accepted.length > 0 && (
                <p className="field-note notice-line" role="status">
                  <span className={`status-dot ${codeId.confirm.ok ? "done" : "warning"}`} />
                  {saving
                    ? "Saving to the engine…"
                    : codeId.confirm.ok
                      ? "Saved. The engine wrote Section C for the articles you marked."
                      : `Saved in this browser; the engine could not write Section C yet (${codeId.confirm.detail}).`}
                </p>
              )}
              <Results run={codeId} busy={busy} onAnswer={answer} onRerun={(a) => find(codeId.prose, a)} onEdit={edit} />
            </>
          ) : (
            <Section title="Example data (fictional)" meta="NorthCore CX sample case · not your project">
              <p className="meta intro">
                These cards show how Code ID works. Select Find articles to get cards for your own description. You never have to pick
                one: answer Not sure, or continue.
              </p>
              {c.candidates.map((a, i) => (
                <ExampleCard key={a.id} a={a} index={i} total={c.candidates.length} />
              ))}
            </Section>
          )}
        </div>
      </div>
      <div className="footer-bar">
        <span className="status-note" role="status">
          {footerNote}
        </span>
        <a className="btn btn-ghost" href="#/describe">
          Back
        </a>
        {/* Before a run, Find articles is the one primary action; after it, Continue is. */}
        <a className={`btn ${codeId ? "btn-primary" : ""}`} href="#/section-c">
          Continue to Section C
        </a>
      </div>
    </>
  );
}
