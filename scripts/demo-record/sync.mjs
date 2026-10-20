/**
 * Keep recorder steps aligned with docs/demo/script.md.
 *
 * The script file lands with the demo-script change. Until it is on the
 * branch, checkScriptFile reports "absent" and recording still runs.
 * Step ids, titles, and primary routes are the shot-list columns.
 */

export function parseDemoScript(markdown) {
  const text = String(markdown).replace(/\r\n/g, "\n");
  const byId = new Map();
  const rowRe = /^\|\s*(\d+)\s*\|[^|\n]*\|[^|\n]*\|\s*`([^`]+)`[^|\n]*\|/gm;
  let match;
  while ((match = rowRe.exec(text))) {
    byId.set(match[1], { id: match[1], route: match[2].trim(), title: "" });
  }
  const headRe = /^### Shot (\d+) — (.+)$/gm;
  while ((match = headRe.exec(text))) {
    const shot = byId.get(match[1]) ?? { id: match[1], route: "", title: "" };
    shot.title = match[2].trim();
    byId.set(match[1], shot);
  }
  return [...byId.values()].sort((a, b) => Number(a.id) - Number(b.id));
}

export function diffScript(steps, markdown) {
  const shots = parseDemoScript(markdown);
  const problems = [];
  const stepById = new Map(steps.map((step) => [step.id, step]));
  const shotIds = new Set(shots.map((shot) => shot.id));
  if (shots.length === 0) {
    problems.push("docs/demo/script.md has no shot-list rows the recorder can read.");
  }
  for (const shot of shots) {
    const step = stepById.get(shot.id);
    if (!step) {
      problems.push(`Shot ${shot.id} is in docs/demo/script.md and missing from the recorder.`);
      continue;
    }
    if (shot.title && step.title !== shot.title) {
      problems.push(`Shot ${shot.id} title differs. Script: "${shot.title}". Recorder: "${step.title}".`);
    }
    if (shot.route && step.route !== shot.route) {
      problems.push(`Shot ${shot.id} route differs. Script: ${shot.route}. Recorder: ${step.route}.`);
    }
  }
  for (const step of steps) {
    if (!shotIds.has(step.id)) problems.push(`Recorder step ${step.id} is not in the script shot list.`);
  }
  return { shots, problems };
}
