/**
 * batatis://app: the built web app and its /api, in one origin. /api goes to the private engine with
 * the host's session cookie; nothing a page sends can pick a URL, a header outside the list, or a file.
 */
import { readFile, realpath } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";
import { EngineFailed, EngineLost, type EngineReply, type EngineRequest } from "./engine";
import type { SessionJar } from "./session";

export const ORIGIN = "batatis://app";
/** The engine's own cap (PDF limit plus multipart overhead); the engine applies the exact limits. */
export const BODY_LIMIT = 4 * 1024 * 1024 + 64 * 1024;
const METHODS = new Set(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]);
const FORWARDED_HEADERS = new Set(["accept", "content-type"]);
const NO_BODY = new Set([204, 205, 304]);

export const CSP = [
  "default-src 'self'", "script-src 'self'", "style-src 'self'", "img-src 'self' data: blob:", "font-src 'self'",
  "connect-src 'self'", "media-src 'self' blob:", "object-src 'none'", "base-uri 'none'", "form-action 'none'",
  "frame-ancestors 'none'", "frame-src 'none'", "worker-src 'none'",
].join("; ");

const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".woff2": "font/woff2", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8", ".json": "application/json",
};

export type ApiGate =
  | { kind: "open"; engine: { request(request: EngineRequest, signal?: AbortSignal): Promise<EngineReply> }; jar: SessionJar }
  | { kind: "closed"; detail: string };

type RequestIdentity = Extract<ApiGate, { kind: "open" }> & { epoch: number; cookie: string | null };

export interface AppProtocolOptions {
  distDir: string;
  /** Read per request: the current engine and session, or why /api is closed (starting, switching, stopped). */
  gate: () => ApiGate;
}

export function createAppProtocol(options: AppProtocolOptions): (request: Request) => Promise<Response> {
  const root = resolve(options.distDir);
  return async (request) => {
    let url: URL;
    try {
      url = new URL(request.url);
    } catch {
      return text(400, "Bad request");
    }
    if (url.protocol !== "batatis:" || url.host !== "app" || url.username || url.password) return text(404, "Not found");
    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) return forward(request, url, options.gate);
    return serveFile(root, url.pathname);
  };
}

async function forward(request: Request, url: URL, readGate: () => ApiGate): Promise<Response> {
  if (!METHODS.has(request.method)) return json(405, { detail: "Method not allowed" });
  const gate = readGate();
  if (gate.kind === "closed") return json(503, { detail: gate.detail }, { "Retry-After": "2" });
  const identity: RequestIdentity = { ...gate, epoch: gate.jar.epoch, cookie: gate.jar.cookieHeader() };
  const body = await readBody(request);
  if (body === null) return json(413, { detail: "That upload is too large." });
  if (!matchesIdentity(readGate(), identity)) return json(503, { detail: "The local workspace or session changed. Nothing was sent." }, { "Retry-After": "2" });
  const headers: [string, string][] = [];
  for (const [name, value] of request.headers) if (FORWARDED_HEADERS.has(name.toLowerCase())) headers.push([name.toLowerCase(), value]);
  if (identity.cookie) headers.push(["cookie", identity.cookie]);
  let reply: EngineReply;
  try {
    reply = await identity.engine.request({ method: request.method, path: url.pathname, query: url.search.replace(/^\?/, ""), headers, body }, request.signal);
  } catch (error) {
    if (error instanceof EngineLost) return json(503, { detail: "The local service stopped before answering. Nothing was retried." });
    if (error instanceof EngineFailed) return json(502, { detail: "The local service could not answer." });
    throw error;
  }
  if (matchesIdentity(readGate(), identity)) {
    await identity.jar.apply(reply.headers.filter(([name]) => name.toLowerCase() === "set-cookie").map(([, value]) => value), identity.epoch);
  }
  const out = new Headers();
  for (const [name, value] of reply.headers) if (name.toLowerCase() !== "set-cookie") out.append(name, value);
  if (NO_BODY.has(reply.status) || request.method === "HEAD") {
    void reply.body.cancel();
    return new Response(null, { status: reply.status, headers: out });
  }
  return new Response(reply.body, { status: reply.status, headers: out });
}

function matchesIdentity(gate: ApiGate, identity: RequestIdentity): boolean {
  return gate.kind === "open" && gate.engine === identity.engine && gate.jar === identity.jar
    && gate.jar.epoch === identity.epoch && gate.jar.cookieHeader() === identity.cookie;
}

async function readBody(request: Request): Promise<Uint8Array | null> {
  if (request.method === "GET" || request.method === "HEAD" || !request.body) return new Uint8Array(0);
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > BODY_LIMIT) return null;
  const reader = request.body.getReader();
  const parts: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const step = await reader.read();
    if (step.done) break;
    size += step.value.length;
    if (size > BODY_LIMIT) {
      await reader.cancel();
      return null;
    }
    parts.push(step.value);
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) {
    body.set(part, offset);
    offset += part.length;
  }
  return body;
}

async function serveFile(root: string, pathname: string): Promise<Response> {
  let decoded: string;
  try {
    decoded = decodeURIComponent(pathname === "/" ? "/index.html" : pathname);
  } catch {
    return text(400, "Bad request");
  }
  if (decoded.includes("\0") || decoded.includes("\\")) return text(404, "Not found");
  const candidate = resolve(root, `.${decoded}`);
  if (!candidate.startsWith(root + sep)) return text(404, "Not found");
  let file: string;
  try {
    file = await realpath(candidate);
  } catch {
    return text(404, "Not found");
  }
  if (!file.startsWith((await realpath(root)) + sep)) return text(404, "Not found");
  const type = TYPES[extname(file).toLowerCase()];
  if (!type) return text(404, "Not found");
  let data: Buffer;
  try {
    data = await readFile(file);
  } catch {
    return text(404, "Not found");
  }
  const headers: Record<string, string> = { "Content-Type": type, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache" };
  if (type.startsWith("text/html")) headers["Content-Security-Policy"] = CSP;
  return new Response(new Uint8Array(data), { status: 200, headers });
}

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers } });
}

function text(status: number, body: string): Response {
  return new Response(body, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
