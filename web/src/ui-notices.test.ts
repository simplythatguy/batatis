import assert from "node:assert/strict";
import test from "node:test";
import { exportNotice, exportReason, type EngineGap } from "./api/client.ts";
import { NRC_CREDIT, NRC_SOURCES } from "./config.ts";
import { EVIDENCE_HINT, engineNotices, groupEvidenceGaps, missingFromEngine, QUOTE_LABEL, quoteKind, splitNoticeUrl } from "./rules.ts";

const CALGARY_URL = "https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf";
const CALGARY =
  "Calgary also asks for its own Request for Specific Variance form " +
  `(in the City's Guide to Applying for an Alternative Solution: ${CALGARY_URL}). ` +
  "Keep this SCC form and appendix; ask your Safety Codes Officer whether they want both.";

const gap = (id: string, severity: EngineGap["severity"], message = id): EngineGap => ({ id, section: "B", field: id, message, severity });

test("an info item is a notice, never a missing item", () => {
  const engine = [gap("owner_name", "blocking"), gap("info:calgary_variance_form", "info", CALGARY), gap("permit", "warning")];
  assert.deepEqual(missingFromEngine(engine).map((g) => g.id), ["owner_name", "permit"]);
  assert.deepEqual(engineNotices(engine), [CALGARY]);
  assert.deepEqual(engineNotices([gap("a", "info", CALGARY), gap("b", "info", CALGARY)]), [CALGARY]);
});

test("the Calgary notice links the City guide and reads cleanly without the raw URL", () => {
  const { text, url } = splitNoticeUrl(CALGARY);
  assert.equal(url, CALGARY_URL);
  assert.equal(
    text,
    "Calgary also asks for its own Request for Specific Variance form (in the City's Guide to Applying for an Alternative Solution). Keep this SCC form and appendix; ask your Safety Codes Officer whether they want both.",
  );
  assert.doesNotMatch(url ?? "", /^#/);
  assert.deepEqual(splitNoticeUrl("No link here."), { text: "No link here.", url: null });
});

test("409 reasons from PR #21 render their label and fix hint, not [object Object]", () => {
  assert.equal(exportReason({ section: "B", gap_id: "x", label: "Owner name missing.", fix_hint: "Enter the owner.", severity: "blocking" }), "Owner name missing. Enter the owner.");
  assert.equal(exportReason("Owner name missing."), "Owner name missing.");
  assert.equal(exportReason({ label: "Owner name missing. Enter the owner.", fix_hint: "Enter the owner." }), "Owner name missing. Enter the owner.");
  assert.equal(exportReason({}), "");
  assert.doesNotMatch(exportReason({ label: "A" }), /object Object/);
});

test("the export notice header is shown, but the privacy notice is left to the privacy notice", () => {
  assert.equal(exportNotice(CALGARY), CALGARY);
  assert.equal(exportNotice(null), "");
  assert.equal(exportNotice("Do not upload personal information. In live mode, text you enter is sent to OpenAI (US)…"), "");
});

test("only code-database text is labelled Code text", () => {
  const base = { identified: true, quote: { text: "1) Penetrations … shall be sealed by a firestop", citation: "NBC(AE) 2023 p2, Div B, Sentence 3.1.9.1.(1) [PDF p.159]" } };
  assert.equal(quoteKind(base), "code");
  assert.equal(quoteKind({ ...base, quote: { ...base.quote, source: "code" } }), "code");
  assert.equal(quoteKind({ identified: true, quote: { text: "Ranks high because …", citation: "No code sentence was returned." } }), "ranking");
  assert.equal(quoteKind({ identified: true, quote: { text: "x", citation: "c", source: "ranking" } }), "ranking");
  assert.equal(quoteKind({ identified: true, quote: { text: "x", citation: "Summary from a development case, not the code sentence." } }), "summary");
  assert.equal(quoteKind({ identified: false, quote: { text: "my words", citation: "c" } }), "applicant");
  assert.equal(quoteKind({ identified: true, quote: { text: "  ", citation: "Article 3.1.9.1." } }), "missing");
  assert.equal(QUOTE_LABEL.ranking.pill, "AI-written");
  assert.notEqual(QUOTE_LABEL.summary.pill, "Code text");
});

test("the NRC credit names the publisher and links the official publication", () => {
  assert.equal(NRC_CREDIT, "© National Research Council of Canada");
  assert.match(NRC_SOURCES.code.title, /NBC\(AE\) 2023, 2nd printing/);
  assert.match(NRC_SOURCES.code.url, /^https:\/\/nrc-publications\.canada\.ca\/.*0316d953-0d55-4311-af69-cad55efec499$/);
  assert.match(NRC_SOURCES.intent.url, /^https:\/\/nrc-publications\.canada\.ca\/.*de0e0ec9-a452-4337-bc84-002a230c9d66$/);
});

test("evidence lines for one sentence become one item that names every pair", () => {
  const line = (pair: string, n: number): EngineGap => ({
    id: `evidence-${n}`,
    section: "D",
    field: `evidence.e${n}`,
    severity: "blocking",
    message: `Your application appears to be missing supporting evidence for 3.1.9.1.(1), ${pair}.`,
    fix_hint: "Performance issue. Select appropriate evidence types with the responsible designer; not every ladder rung is required.",
  });
  const other = gap("owner_name", "blocking");
  const grouped = groupEvidenceGaps([line("F03–OS1.2", 1), other, line("F04–OS1.3", 2), line("F03–OS1.2", 3)]);
  assert.equal(grouped.length, 2);
  assert.equal(grouped[0].message, "Your application appears to be missing supporting evidence for 3.1.9.1.(1) (2 function–objective pairs: F03–OS1.2, F04–OS1.3).");
  assert.equal(grouped[0].fix_hint, EVIDENCE_HINT);
  assert.equal(grouped[1].id, "owner_name");
  const single = groupEvidenceGaps([line("F03–OS1.2", 1)]);
  assert.equal(single[0].message, "Your application appears to be missing supporting evidence for 3.1.9.1.(1) (F03–OS1.2).");
});
