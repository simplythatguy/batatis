import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// The left rail lists places to go (applications, queue, code library). The assistant is the header's
// Ask button and Cmd/Ctrl+J only; a rail entry for it came back once after the user removed it.
test("no rail destination opens the assistant", () => {
  const shell = readFileSync(new URL("../Shell.tsx", import.meta.url), "utf8");
  const start = shell.indexOf("const destinations: RailDestination[]");
  const end = shell.indexOf("];", shell.indexOf("id: \"code\"", start));
  assert.ok(start > 0 && end > start, "destinations list found");
  const list = shell.slice(start, end);
  assert.doesNotMatch(list, /spark|toggleAssistant|assistant/i);
  assert.match(shell, /<AskButton \/>/, "the header Ask stays");
});
