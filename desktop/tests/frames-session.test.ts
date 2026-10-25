import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { chunks, encodeFrame, FrameDecoder, FrameError, MAX_BODY } from "../src/main/frames.ts";
import { SealedTokenStore, SessionJar, sessionFrom } from "../src/main/session.ts";
import { scratch } from "./helpers.ts";

const TOKEN = `tok_${"0123456789".repeat(3)}abcdefghi`;
const OTHER = "b".repeat(43);

test("frames split across arbitrary pipe chunks decode to the same headers and exact bytes", () => {
  const body = Buffer.from(Array.from({ length: 70_000 }, (_, i) => i % 256));
  const wire = Buffer.concat([encodeFrame({ t: "start", id: "r1", status: 200 }), encodeFrame({ t: "body", id: "r1", more: false }, body)]);
  const decoder = new FrameDecoder();
  const frames = [];
  for (let offset = 0; offset < wire.length; offset += 7) frames.push(...decoder.push(wire.subarray(offset, offset + 7)));
  assert.deepEqual(frames.map((f) => f.header), [{ t: "start", id: "r1", status: 200 }, { t: "body", id: "r1", more: false }]);
  assert.deepEqual(Buffer.from(frames[1].body), body);
  assert.equal(decoder.buffered, 0);
});

test("oversized and malformed frames are refused instead of guessed", () => {
  assert.throws(() => encodeFrame({ t: "body" }, new Uint8Array(MAX_BODY + 1)), FrameError);
  const huge = Buffer.alloc(8);
  huge.writeUInt32BE(0xffffff, 0);
  assert.throws(() => new FrameDecoder().push(huge), FrameError);
  const notJson = Buffer.concat([Buffer.from([0, 0, 0, 2, 0, 0, 0, 0]), Buffer.from("{x")]);
  assert.throws(() => new FrameDecoder().push(notJson), FrameError);
  const noType = encodeFrame({ t: "x" }).toString("latin1").replace('"t":"x"', '"u":"x"');
  assert.throws(() => new FrameDecoder().push(Buffer.from(noType, "latin1")), FrameError);
});

test("a body is cut into frame-sized pieces and an empty body still ends the request", () => {
  assert.deepEqual(chunks(new Uint8Array(0)).map((c) => c.length), [0]);
  assert.deepEqual(chunks(new Uint8Array(MAX_BODY * 2 + 3)).map((c) => c.length), [MAX_BODY, MAX_BODY, 3]);
});

test("the jar follows sign-in, renewal and sign-out, and ignores other cookies", async () => {
  const saved: (string | null)[] = [];
  const jar = new SessionJar(null, { save: async (token) => { saved.push(token); } });
  assert.equal(jar.cookieHeader(), null);
  await jar.apply([`batatis_session=${TOKEN}; HttpOnly; Max-Age=2592000; Path=/; SameSite=lax`], jar.epoch);
  assert.equal(jar.cookieHeader(), `batatis_session=${TOKEN}`);
  await jar.apply([`batatis_session=${TOKEN}; Max-Age=2592000`, "theme=dark; Path=/"], jar.epoch);
  await jar.apply(['batatis_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=lax'], jar.epoch);
  assert.equal(jar.cookieHeader(), null);
  assert.deepEqual(saved, [TOKEN, null], "renewing the same token is not a new session");
});

test("a late Set-Cookie from before a switch cannot restore the earlier person", async () => {
  const jar = new SessionJar(TOKEN);
  const before = jar.epoch;
  jar.replace(OTHER);
  await jar.apply([`batatis_session=${TOKEN}; Max-Age=2592000`], before);
  await jar.apply(['batatis_session=""; Max-Age=0'], before);
  assert.equal(jar.token, OTHER);
  assert.notEqual(jar.epoch, before);
});

test("cookie parsing accepts only well-formed session tokens", () => {
  assert.equal(sessionFrom(`batatis_session=${TOKEN}; Path=/`), TOKEN);
  assert.equal(sessionFrom("batatis_session=short; Path=/"), undefined);
  assert.equal(sessionFrom("other=1"), undefined);
  assert.equal(sessionFrom('batatis_session=""; Max-Age=0'), null);
  assert.equal(new SessionJar("not-a-token").token, null);
});

test("the normal workspace session is sealed by the OS or not kept at all", async (t) => {
  const dir = scratch(t);
  const file = join(dir, "session.bin");
  const sealed = new SealedTokenStore(file, {
    available: async () => true,
    encrypt: async (plain) => Buffer.from([...Buffer.from(plain)].reverse()),
    decrypt: async (data) => Buffer.from([...data].reverse()).toString(),
  });
  await sealed.save(TOKEN);
  assert.ok(!readFileSync(file).toString().includes(TOKEN), "the token is not stored in the clear");
  assert.equal(await sealed.load(), TOKEN);
  await sealed.save(null);
  assert.equal(existsSync(file), false);

  const locked = new SealedTokenStore(file, { available: async () => false, encrypt: async () => { throw new Error("no"); }, decrypt: async () => { throw new Error("no"); } });
  await locked.save(TOKEN);
  assert.equal(existsSync(file), false, "no plaintext fallback");
  assert.equal(await locked.load(), null);
});

test("a workspace without a saved session does not initialize the OS keyring", async (t) => {
  let lookups = 0;
  const store = new SealedTokenStore(join(scratch(t), "session.bin"), {
    available: async () => { lookups += 1; return true; },
    encrypt: async (plain) => Buffer.from(plain),
    decrypt: async (sealed) => sealed.toString(),
  });
  assert.equal(await store.load(), null);
  assert.equal(lookups, 0, "an empty workspace must not wait for a Keychain access prompt");
});
