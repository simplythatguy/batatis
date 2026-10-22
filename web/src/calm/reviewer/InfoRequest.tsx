/**
 * Request more information: the deterministic information request, edited by the officer.
 * Include or leave out items, reword them, add your own, preview the exact text, then send it to
 * the case thread (the applicant is notified). A third-party package has no applicant account, so
 * its text is copied out instead. Once sent, the request is frozen and shown as the applicant sees it.
 */
import { useEffect, useId, useMemo, useState } from "react";
import { AccountsError, review } from "../../api/accounts";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { ReviewSession, SentInformationRequests } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
import { CIcon, Modal } from "../ui";
import { sentLabel } from "./queue";
import { draftFrom, includedCount, previewText, requestItems, returnAfterRequest, sameDraft, SECTION_LABEL, toEdit, type DraftItem } from "./packageView";
import "./review.css";

let officerSeq = 0;

function errorText(e: unknown, fallback: string): string {
  return e instanceof AccountsError ? e.detail : fallback;
}

function SentView({ s, applicant, sent, failed, onRetry }: { s: ReviewSession; applicant: string; sent: SentInformationRequests | null; failed?: boolean; onRetry?: () => void }) {
  const ir = s.information_request;
  const theirs = sent?.requests ?? [];
  return (
    <>
      <p className="pr-status"><span className="cf-dot is-done" aria-hidden="true" />Sent {sentLabel(ir.sent_at).replace(/^Today/, "today")}{ir.sent_by_name ? ` by ${ir.sent_by_name}` : ""}. It’s frozen; run a new review to ask again.</p>
      <section className="pr-group" aria-label={`What ${applicant} sees`}>
        <h3 className="pr-group-h">What {applicant} sees</h3>
        {failed ? (
          <p className="ac-error" role="alert">What the applicant sees didn’t load. <button type="button" className="cf-btn is-xs" onClick={onRetry}>Try again</button></p>
        ) : sent === null ? (
          <p className="pr-faint">Loading…</p>
        ) : theirs.length ? (
          <ol className="pr-sent">
            {theirs.map((r) => (
              <li key={`${r.package_id}-${r.version}`} className="pr-letter">
                <p className="pr-letter-meta">From {r.sent_by_name || "the officer"} · {sentLabel(r.sent_at)} · version {r.version}</p>
                <p className="pr-letter-intro">{r.intro}</p>
                <ol className="pr-letter-items">{r.items.map((t, i) => <li key={i}>{t}</li>)}</ol>
              </li>
            ))}
          </ol>
        ) : (
          <p className="pr-faint">Nothing has reached the applicant yet.</p>
        )}
      </section>
    </>
  );
}

export function InfoRequest({
  target,
  session,
  latest,
  canEdit,
  terminalStatus,
  applicant,
  onChange,
  onReturned,
}: {
  target: ReviewTarget;
  session: ReviewSession;
  /** Only the latest version is edited and sent. */
  latest: boolean;
  /** The current claimer (cases) or any officer of the authority (packages). */
  canEdit: boolean;
  /** A settled case keeps the request as a historical record, without claim recovery. */
  terminalStatus?: "accepted" | "refused";
  applicant: string;
  onChange: (s: ReviewSession) => void;
  /** The application was also returned so the applicant can update it. */
  onReturned?: () => Promise<void> | void;
}) {
  const id = useId();
  const ir = session.information_request;
  const isCase = target.kind === "case";
  const sentAlready = Boolean(ir.sent_at);
  const editable = canEdit && !terminalStatus && latest && !sentAlready;

  const [intro, setIntro] = useState(ir.intro);
  const [items, setItems] = useState<DraftItem[]>(() => draftFrom(ir).items);
  const [editing, setEditing] = useState<string | null>(null);
  const [introOpen, setIntroOpen] = useState(false);
  const [adding, setAdding] = useState("");
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState<"" | "save" | "send">("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [alsoReturn, setAlsoReturn] = useState(true);
  const [sent, setSent] = useState<SentInformationRequests | null>(null);
  const [sentFailed, setSentFailed] = useState(false);
  const [sentAttempt, setSentAttempt] = useState(0);

  // A different version (or a server update) resets the draft.
  useEffect(() => {
    const d = draftFrom(session.information_request);
    setIntro(d.intro);
    setItems(d.items);
    setEditing(null);
    setPreview(false);
    setError("");
  }, [session.package_id, session.version, session.information_request]);

  useEffect(() => {
    if (!isCase || !sentAlready) return;
    const ctl = new AbortController();
    setSent(null);
    setSentFailed(false);
    // A failure is shown as a failure with a retry, never as "nothing has reached the applicant".
    packageReview.sent(target.id, ctl.signal).then(
      (r) => { if (!ctl.signal.aborted) setSent(r); },
      () => { if (!ctl.signal.aborted) setSentFailed(true); },
    );
    return () => ctl.abort();
  }, [isCase, sentAlready, target.id, ir.message_id, sentAttempt]);

  const server = useMemo(() => toEdit(ir.intro, draftFrom(ir).items), [ir]);
  const local = toEdit(intro, items);
  const dirty = !sameDraft(local, server);
  const count = includedCount(items);
  const text = previewText(intro, items);

  /** Any edit makes earlier save or send feedback stale. */
  const edited = () => { setError(""); setNote(""); };
  const patch = (key: string, p: Partial<DraftItem>) => { edited(); setItems((list) => list.map((i) => (i.key === key ? { ...i, ...p } : i))); };

  async function save(): Promise<ReviewSession | null> {
    if (!dirty) return session;
    setBusy("save");
    setError("");
    try {
      const next = await packageReview.edit(target, session.version, local);
      onChange(next);
      setNote("Draft saved.");
      return next;
    } catch (e) {
      setError(errorText(e, "The draft didn’t save. Try again."));
      return null;
    } finally {
      setBusy("");
    }
  }

  function addItem() {
    const t = adding.trim();
    if (!t) return;
    const key = `new-${++officerSeq}`;
    edited();
    setItems((list) => [...list, { id: null, key, text: t, included: true, authored: "officer", officerCheck: false, section: null, linked: false }]);
    setAdding("");
  }

  async function send() {
    setConfirm(false);
    const saved = await save();
    if (!saved || target.kind !== "case") return;
    setBusy("send");
    setError("");
    try {
      const done = await packageReview.send(target.id, saved.version);
      onChange(done);
      if (alsoReturn) {
        try {
          await review.decide(target.id, { outcome: "return", message: returnAfterRequest(includedCount(draftFrom(done.information_request).items)), items: requestItems(done) });
          await onReturned?.();
          setNote(`Sent to ${applicant} and returned so they can update the application.`);
        } catch (e) {
          setNote("");
          setError(`The request was sent, but the application wasn’t returned: ${errorText(e, "try Return again")}.`);
        }
      } else {
        setNote(`Sent to ${applicant}. The application stays with you.`);
      }
    } catch (e) {
      setError(errorText(e, "The request didn’t send. Try again."));
    } finally {
      setBusy("");
    }
  }

  async function copy() {
    const saved = await save();
    if (!saved) return;
    try {
      await navigator.clipboard.writeText(saved.information_request.text || text);
      setNote("Copied. Paste it into your email to the applicant.");
    } catch {
      setPreview(true);
      setNote("Copy didn’t work here. Select the preview text and copy it.");
    }
  }

  return (
    <section className="pr" aria-labelledby={`${id}-h`}>
      <header className="pr-head">
        <div className="pr-head-txt">
          <h2 id={`${id}-h`} className="pr-head-title">Information request</h2>
          <p className="pr-faint">Version {session.version} · {sentAlready ? "sent" : ir.edited ? "edited draft" : "draft from the review"}{!latest ? " · an earlier version" : ""}</p>
        </div>
        {!sentAlready && (
          <div className="pr-head-acts">
            <button type="button" className="ac-tab" aria-pressed={!preview} onClick={() => setPreview(false)}>Edit</button>
            <button type="button" className="ac-tab" aria-pressed={preview} onClick={() => setPreview(true)}>Preview</button>
          </div>
        )}
      </header>
      <div className="pr-body">
        {sentAlready ? (
          <>
            <SentView s={session} applicant={applicant} sent={isCase ? sent : { case_id: "", requests: [] }} failed={isCase && sentFailed} onRetry={() => setSentAttempt((n) => n + 1)} />
            {!isCase && <pre className="pr-letter pr-pre">{ir.text}</pre>}
          </>
        ) : preview ? (
          <>
            <p className="pr-lede">Exactly what {isCase ? `${applicant} receives` : "you copy"}{count ? "" : ". Include at least one item"}.</p>
            <pre className="pr-letter pr-pre" aria-label="Preview">{text}</pre>
          </>
        ) : (
          <>
            <h2 className="pr-title">Ask for what’s missing</h2>
            <p className="pr-lede">Drafted from the review, one item per gap. Include what you want to ask, reword anything, or add your own. Items marked “look first” are left out until you check them.</p>
            <div className="pr-intro">
              {introOpen && editable ? (
                <>
                  <label htmlFor={`${id}-intro`} className="pr-group-h">Opening line</label>
                  <textarea id={`${id}-intro`} className="ac-ta pr-ta" rows={3} maxLength={2000} value={intro} onChange={(e) => { edited(); setIntro(e.target.value); }} />
                  <button type="button" className="cf-btn is-xs" onClick={() => setIntroOpen(false)}>Done</button>
                </>
              ) : (
                <>
                  <p className="pr-intro-text">{intro}</p>
                  {editable && <button type="button" className="cf-btn is-xs is-ghost" onClick={() => setIntroOpen(true)}>Edit the opening</button>}
                </>
              )}
            </div>
            <fieldset className="pr-req" disabled={!editable}>
              <legend className="cf-sr">Items</legend>
              <ul className="pr-list">
                {items.map((i) => (
                  <li key={i.key} className={`pr-req-item${i.included ? " is-on" : ""}`}>
                    <label className="ac-check pr-req-check">
                      <input type="checkbox" checked={i.included} onChange={() => patch(i.key, { included: !i.included })} aria-label={`Include: ${i.text}`} />
                      <span className="ac-box" aria-hidden="true"><AcIcon name="check" size={12} stroke={2.4} /></span>
                    </label>
                    <div className="pr-item-body">
                      {editing === i.key ? (
                        <>
                          <label htmlFor={`${id}-${i.key}`} className="cf-sr">Item text</label>
                          <textarea id={`${id}-${i.key}`} className="ac-ta pr-ta" rows={3} maxLength={2000} value={i.text} autoFocus onChange={(e) => patch(i.key, { text: e.target.value })}
                            onKeyDown={(e) => { if (e.key === "Escape" || (e.key === "Enter" && (e.metaKey || e.ctrlKey))) { e.preventDefault(); setEditing(null); } }} />
                        </>
                      ) : (
                        <p className="pr-req-text">{i.text || <span className="pr-faint">Empty item</span>}</p>
                      )}
                      <p className="pr-item-meta">
                        {i.section ? SECTION_LABEL[i.section] : "Your item"}
                        {i.officerCheck && <span className="pr-tag"><span className="cf-dot is-pending" aria-hidden="true" />Look first: the review couldn’t establish this</span>}
                        {i.authored === "officer" && i.id && <span className="pr-tag">Your wording</span>}
                      </p>
                      {editable && (
                        <div className="pr-req-acts">
                          <button type="button" className="cf-btn is-xs is-ghost" onClick={() => setEditing(editing === i.key ? null : i.key)}>{editing === i.key ? "Done" : "Edit"}</button>
                          {!i.linked && (
                            <button type="button" className="cf-btn is-xs is-ghost" onClick={() => { edited(); setItems((list) => list.filter((x) => x.key !== i.key)); }}>Remove</button>
                          )}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              {!items.length && <p className="pr-faint">The review found nothing to ask. Add your own item if you need something.</p>}
            </fieldset>
            {editable && (
              <div className="pr-add">
                <label htmlFor={`${id}-add`} className="pr-group-h">Add your own item</label>
                <textarea id={`${id}-add`} className="ac-ta pr-ta" rows={2} maxLength={2000} placeholder="Please provide…" value={adding} onChange={(e) => { edited(); setAdding(e.target.value); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); addItem(); } }} />
                <button type="button" className="cf-btn is-xs" disabled={!adding.trim()} onClick={addItem}><CIcon name="plus" size={13} />Add item</button>
              </div>
            )}
          </>
        )}
        {error && <p className="ac-error" role="alert">{error}</p>}
        {note && !error && <p className="ac-done" role="status"><span className="cf-dot is-done" aria-hidden="true" />{note}</p>}
      </div>
      {!sentAlready && (
        <footer className="pr-foot">
          <span className="pr-faint pr-count">{count} {count === 1 ? "item" : "items"} included{dirty ? " · unsaved changes" : ""}</span>
          <span className="ac-grow" />
          {editable && <button type="button" className="cf-btn is-sm is-ghost" disabled={!dirty || Boolean(busy)} onClick={() => void save()}>{busy === "save" ? "Saving…" : "Save draft"}</button>}
          {isCase ? (
            <button type="button" className="cf-btn is-sm is-primary" disabled={!editable || !count || Boolean(busy)} onClick={() => setConfirm(true)}>
              <AcIcon name="send" size={14} />{busy === "send" ? "Sending…" : `Send to ${applicant}`}
            </button>
          ) : (
            <button type="button" className="cf-btn is-sm is-primary" disabled={!count || Boolean(busy)} onClick={() => void copy()}>Copy the text</button>
          )}
        </footer>
      )}
      {!sentAlready && !editable && isCase && (terminalStatus || latest) && (
        <p className="pr-fine pr-admin">{terminalStatus
          ? `This application was ${terminalStatus}. This request is a historical, read-only record and can’t be edited or sent.`
          : "Start reviewing (or take over) to edit and send this request."}</p>
      )}

      <Modal open={confirm} onClose={() => setConfirm(false)} labelledBy={`${id}-ct`} className="ac-return">
        <div className="cf-modal-body">
          <h2 id={`${id}-ct`} className="cf-modal-title">Send to {applicant}?</h2>
          <p className="cf-muted">The {count} included {count === 1 ? "item goes" : "items go"} to the application’s messages and {applicant} is notified. The request can’t be changed after it’s sent.</p>
          <label className="ac-check pr-confirm-check">
            <input type="checkbox" checked={alsoReturn} onChange={() => setAlsoReturn((v) => !v)} />
            <span className="ac-box" aria-hidden="true"><AcIcon name="check" size={12} stroke={2.4} /></span>
            <span className="ac-check-text">Also return the application so they can update it and send it again</span>
          </label>
          <p className="pr-faint pr-small">Leave this off to keep the application with you; they can still reply with documents.</p>
        </div>
        <div className="cf-modal-foot">
          <button type="button" className="cf-btn" onClick={() => setConfirm(false)}>Not yet</button>
          <button type="button" className="cf-btn is-primary" onClick={() => void send()}>{alsoReturn ? "Send and return" : "Send"}</button>
        </div>
      </Modal>
    </section>
  );
}
