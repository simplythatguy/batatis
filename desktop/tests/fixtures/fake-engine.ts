/**
 * A stand-in engine process for host tests: real pipes and frames, scripted answers and timing.
 * argv: workspace kind ("local" | "dev"), then optional "refuse" or "garbage".
 */
import { encodeFrame, FrameDecoder, type FrameHeader } from "../../src/main/frames.ts";

const kind = process.argv[2] ?? "dev";
const mode = process.argv[3] ?? "";
const send = (header: { t: string } & Record<string, unknown>, body?: Uint8Array) => process.stdout.write(encodeFrame(header, body));

if (mode === "refuse") {
  send({ t: "refused", protocol: "batatis.bridge.v1", reason: "hosted configuration is not allowed" });
  process.exit(3);
}
if (mode === "garbage") {
  process.stdout.write(Buffer.from([0, 0, 0, 3, 0, 0, 0, 0, 1, 2, 3]));
  setTimeout(() => process.exit(0), 50);
} else {
  const profiles = [
    { profile: "applicant", userId: "user_applicant", name: "Test applicant", kind: "applicant", authority: null },
    { profile: "reviewer:calgary", userId: "user_calgary", name: "Test reviewer, Calgary", kind: "reviewer", authority: "calgary" },
  ];
  send({
    t: "hello", protocol: "batatis.bridge.v1", workspace: { kind, id: "fake-workspace" },
    codedb: { available: false, build: null, expectedBuild: "2" }, ...(kind === "dev" ? { dev: { profiles } } : {}),
  });
}

const requests = new Map<string, { header: FrameHeader; body: Buffer[] }>();
const held: Array<() => void> = [];
const log = { requests: [] as unknown[], cancelled: [] as string[], sessions: [] as unknown[], calls: [] as unknown[] };
let failNextSession = false;

const json = (id: string, status: number, value: unknown, headers: [string, string][] = []) => {
  send({ t: "start", id, status, headers: [["content-type", "application/json"], ...headers] });
  send({ t: "body", id, more: false }, Buffer.from(JSON.stringify(value)));
};

function answer(id: string, header: FrameHeader, body: Buffer) {
  const path = String(header.path);
  const query = String(header.query ?? "");
  const headers = Array.isArray(header.headers) ? header.headers : [];
  log.requests.push({ id, method: header.method, path, query, headers, body: body.toString("utf8") });
  if (path === "/api/crash") process.exit(9);
  if (path === "/api/hold") {
    held.push(() => json(id, 200, { held: true }));
    return;
  }
  if (path === "/api/stream") {
    send({ t: "start", id, status: 200, headers: [["content-type", "text/event-stream"]] });
    send({ t: "body", id, more: true }, Buffer.from("event: first\n\n"));
    held.push(() => send({ t: "body", id, more: false }, Buffer.from("event: done\n\n")));
    return;
  }
  if (path === "/api/fail") {
    send({ t: "fail", id, detail: "engine error" });
    return;
  }
  if (path === "/api/nothing") {
    send({ t: "start", id, status: 204, headers: [] });
    send({ t: "body", id, more: false });
    return;
  }
  const set = new URLSearchParams(query).get("set");
  const cookie = set === "clear" ? 'batatis_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=lax'
    : set ? `batatis_session=${set.padEnd(43, "x")}; HttpOnly; Max-Age=2592000; Path=/; SameSite=lax` : null;
  json(id, 200, { path, query, headers, body: body.toString("utf8") }, cookie ? [["set-cookie", cookie]] : []);
}

const decoder = new FrameDecoder();
process.stdin.on("data", (chunk: Buffer) => {
  for (const { header, body } of decoder.push(chunk)) {
    const id = String(header.id ?? "");
    if (header.t === "req") requests.set(id, { header, body: [] });
    else if (header.t === "body") {
      const request = requests.get(id);
      if (!request) continue;
      request.body.push(Buffer.from(body));
      if (!header.more) {
        requests.delete(id);
        answer(id, request.header, Buffer.concat(request.body));
      }
    } else if (header.t === "cancel") log.cancelled.push(id);
    else if (header.t === "call.res") log.calls.push(header);
    else if (header.t === "ctl") control(id, String(header.op), header.args);
  }
});
process.stdin.on("end", () => process.exit(0));

function control(id: string, op: string, args: unknown) {
  const reply = (value: unknown) => send({ t: "ctl.res", id, ok: true, value });
  if (op === "shutdown") {
    reply({});
    process.exit(0);
  }
  if (op === "dev.session") {
    log.sessions.push(args);
    if (failNextSession) {
      failNextSession = false;
      send({ t: "ctl.res", id, ok: false, error: "failed" });
      return;
    }
    const profile = typeof args === "object" && args !== null && "profile" in args ? String(args.profile) : "";
    reply({ token: profile.replace(/[^A-Za-z0-9]/g, "_").padEnd(43, "t").slice(0, 43), profile });
    return;
  }
  if (op === "fail-next-session") { failNextSession = true; reply({}); return; }
  if (op === "release") { for (const done of held.splice(0)) done(); reply({}); return; }
  if (op === "log") { reply(log); return; }
  if (op === "call") { send({ t: "call", id: `c-${id}`, op: "provider.completeJson", args }); reply({}); return; }
  send({ t: "ctl.res", id, ok: false, error: "unavailable" });
}
