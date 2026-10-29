import assert from "node:assert/strict";
import test from "node:test";
import { EXAMPLES } from "./examples.ts";
import { EXIT_COUNT } from "./config.ts";
import {
  EXAMPLE_EXPORT_BLOCK,
  UPLOAD_UNAVAILABLE,
  exampleExportBlocked,
  exitCountWarning,
  factSignature,
  failureKind,
  jurisdictionForCreate,
  publicDetail,
  sectionCQuoteLabel,
  shouldConfirmReplace,
  takeSseEvents,
  uploadMessage,
} from "./rules.ts";

test("an example cannot be exported as a real application", () => {
  assert.equal(exampleExportBlocked("homebuilder-soffit"), true);
  assert.equal(exampleExportBlocked(undefined), false);
  assert.match(EXAMPLE_EXPORT_BLOCK, /not a real application/i);
});

test("example buttons ask before they replace a case the user has started", () => {
  assert.equal(shouldConfirmReplace({ description: "", factCount: 0, fileCount: 0 }), false);
  assert.equal(shouldConfirmReplace({ description: "hempcrete walls", factCount: 0, fileCount: 0 }), true);
  assert.equal(shouldConfirmReplace({ description: "", factCount: 2, fileCount: 0 }), true);
  assert.equal(shouldConfirmReplace({ description: "  ", factCount: 0, fileCount: 1 }), true);
});

test("the engine-down state is only an unreachable engine", () => {
  assert.equal(failureKind(0, "failed to fetch"), "unreachable");
  assert.equal(failureKind(404, "Not Found"), "missing-route");
  assert.equal(failureKind(404, "case not found"), "stale-case");
  assert.equal(failureKind(404, "provision not found"), "other");
  assert.equal(failureKind(404, "identify result not found"), "other");
  assert.equal(publicDetail(404, "case not found"), "case not found");
  assert.equal(publicDetail(404, "provision not found in this identification"), "This rule isn’t in your code check. Check the code again.");
  assert.equal(publicDetail(404, "identify result not found"), "Check the code first.");
  assert.doesNotMatch(publicDetail(404, "requirement not found"), /not found/);
  assert.doesNotMatch(publicDetail(404, "Not Found"), /no route/i);
  assert.doesNotMatch(publicDetail(404, "case not found"), /no route/i);
  assert.equal(failureKind(500, "Internal Server Error"), "other");
  assert.equal(failureKind(503, "code database not found: /tmp/secret.sqlite"), "codedb");
  assert.equal(publicDetail(503, "code database not found: /tmp/secret.sqlite (set BATATIS_CODEDB)"), "The code database is not available.");
  assert.equal(publicDetail(502, "Bad Gateway"), "The review service did not respond.");
  assert.equal(publicDetail(503, "SCC variance form not found"), "SCC variance form not found");
  assert.equal(publicDetail(503, "missing /Users/aamia/form.pdf"), "The engine is missing a file it needs.");
  assert.doesNotMatch(publicDetail(503, "code database not found: /tmp/secret.sqlite"), /\/tmp|BATATIS/);
});

test("a missing upload route is not the engine-down state", () => {
  assert.equal(uploadMessage(404, "Not Found"), UPLOAD_UNAVAILABLE);
  assert.equal(failureKind(404, "Not Found"), "missing-route");
  assert.notEqual(failureKind(404, "Not Found"), "unreachable");
});

test("cached Section C text is a summary, and only codedb text is verbatim", () => {
  assert.deepEqual(sectionCQuoteLabel(true), { pill: "Code text", meta: "Retrieved verbatim" });
  assert.deepEqual(sectionCQuoteLabel(false), { pill: "Summary", meta: "Cached summary" });
  assert.notEqual(sectionCQuoteLabel(false).meta, "Retrieved verbatim");
});

test("jurisdiction stays empty until the applicant picks, and an edit re-posts", () => {
  assert.equal(jurisdictionForCreate(""), null);
  assert.equal(jurisdictionForCreate("calgary")?.id, "calgary");
  assert.equal(jurisdictionForCreate("edmonton")?.name, "Edmonton");
  const first = factSignature({ id: "desc-description", field: "project.description", value: "hemp", status: "confirmed", kind: "pointed" });
  const edited = factSignature({ id: "desc-description", field: "project.description", value: "hempcrete", status: "confirmed", kind: "pointed" });
  assert.notEqual(first, edited);
  assert.equal(first, factSignature({ id: "desc-description", field: "project.description", value: "hemp", status: "confirmed", kind: "pointed" }));
});

test("different applicant answers never share an acknowledgement signature", () => {
  const value = { id: "answer", field: "owner", value: "Aa", status: "confirmed", kind: "pointed" };
  assert.notEqual(factSignature(value), factSignature({ ...value, value: "BB" }), "the old 32-bit hash collision lost this changed answer");
});

test("exit count is not cited as 9.9.4.4", () => {
  const warning = exitCountWarning("9.9.4.4.(1)", "Single exit from the second storey");
  assert.ok(warning);
  assert.match(warning, new RegExp(EXIT_COUNT.part3.replace(/[().]/g, "\\$&")));
  assert.match(warning, new RegExp(EXIT_COUNT.part9.replace(/[().]/g, "\\$&")));
  assert.equal(exitCountWarning("9.9.4.4.(1)", "Openings near an exterior exit stair"), null);
  assert.equal(exitCountWarning("3.4.2.1.(1)", "Single exit"), null);
  for (const example of EXAMPLES) {
    for (const card of example.case.candidates) {
      assert.equal(exitCountWarning(card.provision, card.topic), null, `${example.id} ${card.provision}`);
    }
  }
});

test("SSE frames split on a blank line and keep a partial tail", () => {
  const { events, rest } = takeSseEvents("event: screen\ndata: {\"stage\":\"screen\"}\n\nevent: done\ndata: {\"art");
  assert.equal(events.length, 1);
  assert.equal(events[0].event, "screen");
  assert.match(rest, /done/);
});
