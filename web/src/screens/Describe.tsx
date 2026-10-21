import { useState } from "react";
import { AUTHORITIES } from "../config";
import { FactLedger, QuestionChips } from "../case-parts";
import { DraftNote, FieldSteps, GapStrip, PanelHeader } from "../components";
import { useCase } from "../store";

function PastePlans() {
  const { c, dispatch } = useCase();
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  return <div className="field">
    <label htmlFor="paste-plans">Text from your plans</label>
    <textarea id="paste-plans" rows={4} value={text} onChange={e => setText(e.target.value)} />
    <button type="button" className="btn" disabled={!text.trim()} onClick={() => {
      dispatch({ type: "setDescription", text: [c.description.trim(), text.trim()].filter(Boolean).join("\n\n") });
      setText(""); setNote("Added to your description.");
    }}>Add text</button>
    {note && <p className="meta" role="status">{note}</p>}
  </div>;
}

export function Describe() {
  const { c, gaps, dispatch, saveDraft } = useCase();
  return <>
    <PanelHeader title="Your project" />
    <GapStrip gaps={gaps} />
    <div className="pane scroll-body"><div className="focused-content">
      <FieldSteps nextHref="#/application?tab=A" steps={[
        { title: "What are you building?", fields: ["description"], content: <>
          <div className="field">
            <label className="sr-only" htmlFor="description">What are you building?</label>
            <textarea id="description" className="describe-text" rows={5} value={c.description} onChange={e => dispatch({type:"setDescription",text:e.target.value})} placeholder={c.applicantType === "manufacturer" ? "Describe your product and how it will be used…" : "Describe your project and what you want to do differently…"} />
          </div>
          <details className="compact-help"><summary>Add text from plans</summary><PastePlans /></details>
          <p className="meta visit-note">Changes save to Batatis as you type. Download a copy before leaving.</p>
        </> },
        { title: "Who will review it?", fields: ["authority"], content: <div className="field">
          <label htmlFor="authority">Reviewing authority</label>
          <select id="authority" value={c.authority} data-empty={!c.authority} onChange={e => dispatch({type:"setAuthority",authority:e.target.value as typeof c.authority})}>
            <option value="">Choose when you know</option>{AUTHORITIES.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <details className="compact-help"><summary>What is an authority?</summary><p>The municipality or organization reviewing your building permit. You can leave this unanswered.</p></details>
        </div> },
      ]} />
      {(c.questions.length > 0 || c.facts.length > 0) && <details className="disclosure"><summary>Review captured details</summary><QuestionChips /><FactLedger /></details>}
    </div></div>
    <div className="footer-bar"><DraftNote /><button type="button" className="btn" onClick={() => void saveDraft()}>Save draft</button></div>
  </>;
}
