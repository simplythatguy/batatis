/**
 * Officer package review (docs/api/package-review.md). Two targets share one shape:
 *   - a case in the reviewer queue: /review/{caseId}/package-review…
 *   - a third-party package with no Batatis case: /package-review/{packageId}…
 * Wire types come from types.gen.ts. Errors are AccountsError (plain `detail`).
 */
import { call } from "./accounts";
import type { CloseOut, InformationRequestEdit, PackageReviewIndex, ReviewSession, SentInformationRequests } from "./types.gen";

export type ReviewTarget = { kind: "case"; id: string } | { kind: "package"; id: string };

const enc = encodeURIComponent;
/** Reviews read whole PDFs on the server; give them longer than a plain request. */
const SLOW = 90_000;

const base = (t: ReviewTarget) => (t.kind === "case" ? `/review/${enc(t.id)}/package-review` : `/package-review/${enc(t.id)}`);

export function pdfForm(files: File[]): FormData {
  const form = new FormData();
  for (const f of files) form.append("files", f, f.name);
  return form;
}

export const packageReview = {
  index: (t: ReviewTarget, signal?: AbortSignal) => call<PackageReviewIndex>("GET", base(t), undefined, signal),
  version: (t: ReviewTarget, version: number, signal?: AbortSignal) => call<ReviewSession>("GET", `${base(t)}/${version}`, undefined, signal),
  /** Review the saved case (no files; cases only) or uploaded PDFs: the next version, with a diff from version 2. */
  run: (t: ReviewTarget, files?: File[]) => call<ReviewSession>("POST", base(t), files?.length ? pdfForm(files) : undefined, undefined, SLOW),
  /** A third-party package: a new package id, scoped to the officer's authority. */
  start: (files: File[]) => call<ReviewSession>("POST", "/package-review", pdfForm(files), undefined, SLOW),
  edit: (t: ReviewTarget, version: number, body: InformationRequestEdit) =>
    call<ReviewSession>("PUT", `${base(t)}/${version}/information-request`, body),
  /** Cases only: posts the included items to the case thread; the applicant is notified. */
  send: (caseId: string, version: number) =>
    call<ReviewSession>("POST", `/review/${enc(caseId)}/package-review/${version}/information-request/send`, {}),
  /** What the applicant sees: sent requests only, never drafts. */
  sent: (caseId: string, signal?: AbortSignal) => call<SentInformationRequests>("GET", `/cases/${enc(caseId)}/information-request`, undefined, signal),
  closeOut: (caseId: string, signal?: AbortSignal) => call<CloseOut>("GET", `/review/${enc(caseId)}/close-out`, undefined, signal),
  /** Records the officer's own statement that they sent the copy. Batatis sends nothing. */
  markSent: (caseId: string) => call<CloseOut>("POST", `/review/${enc(caseId)}/close-out/sent`, {}),
};
