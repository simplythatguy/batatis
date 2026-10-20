/**
 * Keep recorder steps aligned with the demo script.
 *
 * The script file belongs to #20. The recorder reads it from that branch, or
 * from a path passed with --script. It is not stored on this branch.
 *
 * Shot ids and titles come from `### Shot N —` headings.
 * The primary route is the first hash route on that shot's `**Route:**` line.
 * Older shot tables that put one route in backticks are still read.
 */

export function parseDemoScript(markdown) {
  const text = String(markdown).replace(/\r\n/g, "\n");
  const byId = new Map();
  const rowRe = /^\|\s*(\d+)\s*\|[^|\n]*\|[^|\n]*\|\s*`([^`]+)`[^|\n]*\|/gm;
  let match;
  while ((match = rowRe.exec(text))) {
    byId.set(match[1], { id: match[1], route: match[2].trim(), title: "" });
  }
  const sections = text.split(/^### Shot /m).slice(1);
  for (const section of sections) {
    const head = section.match(/^(\d+) — ([^\n]+)/);
    if (!head) continue;
    const id = head[1];
    const title = head[2].trim();
    const prev = byId.get(id) ?? { id, route: "", title: "" };
    const routeLine = section.match(/\*\*Route:\*\*[ \t]*([^\n]+)/);
    let route = prev.route;
    if (routeLine) {
      const hashes = [...routeLine[1].matchAll(/`(#\/[^`]*)`/g)].map((item) => item[1].trim());
      if (hashes.length) route = hashes[0];
    }
    byId.set(id, { id, route, title });
  }
  return [...byId.values()].sort((a, b) => Number(a.id) - Number(b.id));
}

export function diffScript(steps, markdown) {
  const shots = parseDemoScript(markdown);
  const problems = [];
  const stepById = new Map(steps.map((step) => [step.id, step]));
  const shotIds = new Set(shots.map((shot) => shot.id));
  if (shots.length === 0) {
    problems.push("The demo script has no shot-list rows the recorder can read.");
  }
  for (const shot of shots) {
    const step = stepById.get(shot.id);
    if (!step) {
      problems.push(`Shot ${shot.id} is in the demo script and missing from the recorder.`);
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
    if (!shotIds.has(step.id)) problems.push(`Recorder step ${step.id} is not in the demo script.`);
  }
  return { shots, problems };
}
