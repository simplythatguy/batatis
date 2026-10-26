# Application workspace

The fourth applicant stage (`#/application`). The application is a live document the applicant reads, edits, signs and sends without leaving Batatis. It replaces the page images of a draft PDF.

Owner: application workspace thread (2026-10-26). Inputs from other threads, used as they land:

| Input | Owner | How the workspace uses it |
| --- | --- | --- |
| AI drafts of the proposed alternative, the six narratives, Section C explanations | writing thread | A `proposed` fact (or the writing thread's documented draft record) for a block's field shows as a suggestion to accept or reject. |
| Completeness results | rulebook thread | `useCase().gaps` (and its successor) drive the inline "missing" marks and the Send step's "Officer would flag" list. The workspace adds no completeness rules. |
| Saving | saving thread | Edits go through the existing store actions (`setDetail`, `setProcess`, …). The workspace owns only its own record (signatures, consent, edit history) through the routes below. |
| Officer requests | officer thread | `DecisionItem.field` pins a request to the block that edits that field. |
| Code reference components | visual language thread | Section C rows render citation chips through the shared component when it exists. |

## Interaction model

Chosen after two prototypes (inline living document; paper with a focus panel and steps). The result grafts B's three steps onto A's direct editing.

One sub-bar under the header: three steps, `Edit · Sign · Send`. The current step shows its word; the others show an icon and a count (Edit: open suggestions and requests; Sign: `signed/required`). The application's real status sits at the right (`Draft`, `Sent`, `In review`, `Returned`, `Accepted`, `Refused`), never "Draft" for a sent application.

### Edit

- The paper is the editor. It follows the official form: Section A, Section B (including the proposed alternative), the applicant's case (rationale, risk, mitigating measures, assumptions and limits, maintenance, qualifications: the appendix content, placed where an officer reads it), Section C, Section D. Real headings and text: selectable, findable with the browser's find, read by screen readers.
- Click a value and type. Text fields and narratives edit in place through the store's actions; nothing else changes the case. Values that are not free text (reviewing office, site/jurisdiction scope, code references, supporting documents, not-applicable reasons) show a quiet `Change` link to the exact question card.
- Missing required items show inline as a red dot and `Missing`, with `Write it` (focuses the block).
- Select text on the paper: a dark floating bar offers `Ask` (opens the assistant with the passage as the focus), `Rewrite`, `Clearer`, `Shorter`. A rewrite returns a suggestion; nothing changes until the applicant accepts it.
- A suggestion renders inline as a tracked change: removed words struck through in faint ink, added words on a pale violet field with a dashed underline, and a small bar `✦ AI suggestion · Accept · Reject` under the block. AI text is never shown in the applicant's plain ink before acceptance.
- After acceptance the words are the applicant's. The block keeps a quiet `✦` in its left margin ("Drafted with AI · accepted <date>"), and the history records the change.
- Verbatim code text keeps the solid-rule quote style and is never editable. Section C objectives and functions are lookups (lock icon), never editable.
- A returned application shows each officer request on the block it concerns (`DecisionItem.field`), above the block, in the officer's words.
- History (clock icon in the sub-bar) opens a drawer: every change, newest first, with who (`You`, `AI · accepted`, `Restored`), the block, and `Restore` on each entry. `⌘Z` outside a text field and the toast after accepting an AI change undo the last change.
- Zoom: `−` `+` in the sub-bar scale the paper (80–140%). Sections are reachable from the step's outline popover (`A B ¶ C D`).
- Read-only (sent, in review, accepted, refused): no caret, no selection rewrite; `Ask` stays.

### Sign

- One screen with the form's own signature block: the consent checkbox (the form's disclosure text one click away), then one card per required signer: the owner, and the owner's representative when the application names one.
- `Sign here` opens a dialog: `Draw` (pointer, touch or pen) or `Type` (the name in a signature face). The printed name comes from the application and stays editable; the date is today's date in Alberta and is filled automatically. The form's attestation sentence sits above the button.
- A signature is tied to the content it signed. If the application changes after signing, the card says `Changed since signed` and asks to sign again; the export leaves that signature out.
- Batatis never signs or seals for anyone: each signature needs an explicit act by its signer. Professionals sign their own Section D documents; the Sign step offers no professional signature.
- A signer who is not at this computer: `Copy signing link` (phase 2, see routes).

### Send

- Officer view: the real package pages as the officer receives them (the exported PDF, drawn a few pages at a time), and beside them:
  - `Officer would flag n`: the shared completeness results, plus unsigned or out-of-date signatures and missing consent, each with `Fix` that opens the block or the Sign step.
  - `In the package`: Form Part 1, the appendix, each attached supporting document with its page count; a listed document with no file says `Not attached`.
  - The one primary action: `Submit to <office>` (disabled with the reason while anything blocks), and `Download PDF` (the official package when ready; otherwise a draft marked on every page).

## Data shape (web)

`web/src/calm/workspace/document.ts` derives everything from the case; no copy of the case is kept.

```ts
type SectionId = "A" | "B" | "case" | "C" | "D";
type BlockTarget =
  | { kind: "detail"; field: string; section: "A" | "B" }      // store action setDetail
  | { kind: "process"; field: ProcessFieldId }                  // store action setProcess
  | { kind: "card"; href: string };                             // not free text: opens its question card
interface DocBlock {
  id: string;               // stable: the target's field key, e.g. "owner_name", "process.risk"
  section: SectionId;
  label: string;
  text: string;             // the confirmed value; "" when missing
  target: BlockTarget;
  required: boolean;
  missing: boolean;
  notApplicable?: string;   // the applicant's N/A reason
  aiAccepted?: string;      // ISO date of the last accepted AI change
  requests: { id: string; note: string }[];   // officer requests pinned to this block
}
interface Suggestion {
  id: string;
  blockId: string;
  origin: "rewrite" | "draft";
  before: string;           // whole block text the suggestion was made against
  after: string;            // whole block text if accepted
  factId?: string;          // a writing-thread proposed fact; Reject dismisses it
}
interface HistoryEntry {
  id: string; at: string; block: string; label: string;
  before: string; after: string; by: "you" | "ai" | "restore";
}
```

A suggestion whose `before` no longer equals the block's text is stale and is dropped (never applied over newer words).

## Engine routes

All owner-only, on draft or returned applications for writes; reads follow case access.

| Route | Body | Result |
| --- | --- | --- |
| `GET /cases/{id}/workspace` | | `{ content_hash, signers: [{ role, name, required }], signatures: [{ role, name, signed_on, method, image, current }], consent: { agreed, at } \| null, history: HistoryEntry[] }` |
| `PUT /cases/{id}/signatures/{role}` | `{ name, method: "drawn" \| "typed", image }` | The signature with `signed_on` set by the server (Alberta date) and `content_hash` of the content it signs. `role` is `owner` or `owner_rep`. `image` is a PNG data URL, at most 200 KB. |
| `DELETE /cases/{id}/signatures/{role}` | | 204 |
| `PUT /cases/{id}/consent` | `{ agreed: bool }` | `{ agreed, at }` |
| `POST /cases/{id}/history` | `{ entries: HistoryEntry[] }` | Appends; keeps the newest 300. |
| `POST /cases/{id}/rewrite` | `{ field, text, start, end, instruction }` | `{ replacement, cited, removed_citations, notice }`. Rewrites `text[start:end]` (the whole text when `start == end`). Fields: the proposed alternative, the six narratives and Section C explanations only. Same guards as `/assist`: no invented article numbers, no compliance or safety claims, no professional evidence; unverifiable quotes lose their quote marks. |

`content_hash` covers what the signers attest to: confirmed applicant facts (except the signature, date and consent facts), the narratives, the confirmed code references and the listed documents. A signature is `current` when its hash equals the case's.

## Export

- Signatures, their dates and the printed names are drawn into the form's signature block from current signatures; the consent box is checked when consent is agreed.
- Signature fields Batatis did not fill, their date fields and an unchecked consent box stay live form fields, so another tool can sign; everything else stays flattened.
- A draft carries a visible mark on every page: `Draft · not for submission`.
- The package appends each attached supporting document's PDF after the appendix, with a bookmark per document.
- The re-upload reader accepts Batatis's own export (form, appendix, attachments, live signature fields).

## Assistant

`/assist` replies keep a quoted line (`> …`) in the code-text style only when its words appear in the code text of a provision the reply cites or the context focuses; any other quote is shown as plain AI text.
