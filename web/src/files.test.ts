import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { pendingUploads, reducer, uploadHeldFile } from "./model.ts";
import { fileReadLabel } from "./intakeView.ts";
import { openedCase } from "./calm/openCase.ts";
import type { Case as EngineCase, FileReport, IntakeResult } from "./api/types.gen.ts";
import type { Fact } from "./types.ts";

function report(over: Partial<FileReport> = {}): FileReport {
  return { file_id: "a", name: "plan.pdf", status: "read", reason: null, pages: 12,
    pages_read: Array.from({ length: 12 }, (_, n) => n + 1), pages_not_read: [], text_pages_read: Array.from({ length: 12 }, (_, n) => n + 1),
    semantic_pages_read: [], semantic_pages_sent: [], image_pages_read: [], semantic_reason: null, pictures_not_read_reason: null, media_type: "application/pdf",
    form: null, form_fields_read: 0, form_fields_skipped: [], facts: 0, ...over };
}

const result = (files: FileReport[] = []): IntakeResult => ({ case_id: "case", case_version: 1, facts: [], record: {
  ran_at: "", text_sha256: null, files, pointers: [], removed_file_ids: [], conflicts: [], unresolved_citations: [], plan: null, review: null,
  model: { status: "off", model: null, reason: null, pointed: 0, proposed: 0, dropped: 0, input_tokens: 0, output_tokens: 0 },
} });

test("file labels report whole, partial, image-only, unavailable, and unfinished reads", () => {
  assert.deepEqual(fileReadLabel(undefined), { tone: "pending", label: "Waiting to read" });
  assert.deepEqual(fileReadLabel(report()), { tone: "done", label: "Read · 12 of 12 pages" });
  const partial = report({ status: "partly_read", pages: 140, pages_read: Array.from({ length: 60 }, (_, n) => n + 1), text_pages_read: Array.from({ length: 60 }, (_, n) => n + 1), reason: "Only some pages were read." });
  assert.equal(fileReadLabel(partial).label, "Read · 60 of 140 pages");
  assert.equal(fileReadLabel(partial).tone, "warning");
  assert.deepEqual(fileReadLabel(report({ pages: 2, pages_read: [1, 2], text_pages_read: [], image_pages_read: [1, 2] })), { tone: "done", label: "2 drawings looked at" });
  assert.equal(fileReadLabel(report({ status: "not_read", pages: 1, pages_read: [], text_pages_read: [], pictures_not_read_reason: "AI is off" })).label, "Pictures not read: AI is off");
  assert.equal(fileReadLabel(report({ status: "partly_read", semantic_pages_read: [1, 2], semantic_reason: "Reading limit reached" })).label, "Read · 2 of 12 pages");
  assert.equal(fileReadLabel(report({ status: "not_read", pages_read: [], text_pages_read: [], reason: "This file could not be opened." })).tone, "blocking");
  assert.equal(fileReadLabel(report({ text_pages_read: [] })).label, "Read again", "an older report cannot claim the new coverage");
});

test("failed uploads retain the original File for retry, then release it only after success", async () => {
  const file = new File(["picture bytes"], "plan.png", { type: "image/png" });
  const held = [{ id: "local", file }];
  let calls = 0;
  const upload = async (same: File) => {
    assert.equal(same, file);
    if (++calls === 1) throw new Error("temporary offline");
    return { id: "engine-file", name: file.name, content_type: file.type, size: file.size };
  };
  const failed = await uploadHeldFile(held, "local", upload);
  assert.equal(failed.kind, "failed");
  assert.equal(failed.held[0].file, file);
  const c = { files: [{ id: "local", name: file.name, read: false, error: "Upload failed" }] };
  assert.equal(pendingUploads(c, failed.held).length, 0, "a failed upload waits for Retry, without an automatic loop");
  assert.equal(pendingUploads(c, failed.held, "local")[0].file, file);
  const retried = await uploadHeldFile(failed.held, "local", upload);
  assert.equal(retried.kind, "uploaded");
  assert.deepEqual(retried.held, []);
  assert.equal(calls, 2);
});

test("upload acknowledgement leaves the file waiting for its actual intake report", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "addFiles", files: [{ id: "local", name: "plan.pdf" }] });
  c = reducer(c, { type: "setFileResult", id: "local", error: null, engineId: "a" });
  assert.equal(c.files[0].read, false);
  c = reducer(c, { type: "noteIntake", text: "", result: result([report()]) });
  assert.equal(c.files[0].read, true);
});

test("removal drops only unconfirmed facts with no other source, and late reads cannot restore them", () => {
  const make = (id: string, status: "confirmed" | "unconfirmed"): Fact => ({ id, field: id, value: 2, kind: "pointed", status,
    source: { type: "file", ref: "a", page: 1, bbox: null, quote: "two" }, inputs: [], formula: null, confidence: .9 });
  const facts = [make("only", "unconfirmed"), make("shared", "unconfirmed"), make("confirmed", "confirmed")];
  const read = result([report()]);
  read.facts = facts;
  read.record.pointers = facts.map(f => ({ fact_id: f.id, field: f.field, source_ref: "a", page: 1, method: "rules", start: 0, end: 3, verified: true, source_name: "plan.pdf", quote: "two" }));
  read.record.pointers.push({ ...read.record.pointers[1], source_ref: "b", source_name: "other.pdf" });
  let c = { ...emptyCase("homebuilder"), facts, files: [{ id: "local", engineId: "a", name: "plan.pdf", read: true }] };
  c = reducer(c, { type: "restoreIntake", result: read, text: "" });
  c = reducer(c, { type: "removeFile", id: "local" });
  assert.deepEqual(c.facts.map(f => f.id), ["shared", "confirmed"]);
  assert.equal(c.facts[0].source.ref, "b");
  assert.ok(!c.intake?.record.pointers.some(p => p.source_ref === "a"));
  c = reducer(c, { type: "noteIntake", result: read, text: "" });
  assert.ok(!c.facts.some(f => f.id === "only"));
  assert.equal(c.files.length, 0);
  c = reducer(c, { type: "noteIntake", result: { ...read, record: { ...read.record, removed_file_ids: ["a"], pointers: read.record.pointers.filter(p => p.source_ref !== "a"), files: [] } }, text: "" });
  assert.equal(c.intake?.filesChanged, undefined, "a server-acknowledged removal does not require endless rereading");
});

test("reopening restores uploaded names, ids and actual reports from inventory", () => {
  const read = result([report()]);
  const saved = { id: "case", facts: [], title: "Plans", provisions: [], selected_articles: null, authority: null, jurisdiction: null,
    decision: null, intake: read.record, identify: null } as EngineCase;
  const c = openedCase(saved, "homebuilder", { intake: read, identify: null, files: [
    { id: "a", name: "plan.pdf", size: 10, content_type: "application/pdf", read_report: read.record.files[0] },
    { id: "b", name: "photo.webp", size: 20, content_type: "image/webp", read_report: null },
  ] });
  assert.deepEqual(c.files.map(f => [f.name, f.engineId, f.read]), [["plan.pdf", "a", true], ["photo.webp", "b", false]]);
  assert.equal(fileReadLabel(c.intake?.record.files[0]).label, "Read · 12 of 12 pages");
  const older = result([report({ text_pages_read: [] })]);
  assert.equal(openedCase(saved, "homebuilder", { intake: older, identify: null }).intake?.filesChanged, true);
});
