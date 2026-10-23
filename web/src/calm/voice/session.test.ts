import assert from "node:assert/strict";
import { test } from "node:test";
import { checkCapability, relayUrl } from "./protocol.ts";
import { Segmenter } from "./segmenter.ts";
import { VoiceClient, type SocketLike, type VoiceAudio, type VoiceDeps, type VoiceScopeInput, type VoiceTranscript } from "./session.ts";

class FakeSocket implements SocketLike {
  readyState = 0;
  bufferedAmount = 0;
  sent: Record<string, unknown>[] = [];
  closed: number | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  url: string;
  protocol: string;
  constructor(url: string, protocol: string) { this.url = url; this.protocol = protocol; }
  send(data: string) { this.sent.push(JSON.parse(data)); }
  close(code = 1000) { if (this.closed === null) { this.closed = code; this.readyState = 3; } }
  open() { this.readyState = 1; }
  emit(event: Record<string, unknown>) { this.onmessage?.({ data: JSON.stringify(event) }); }
  drop() { this.readyState = 3; this.onclose?.({ code: 1006 }); }
  types() { return this.sent.map((s) => s.type); }
  count(type: string) { return this.sent.filter((s) => s.type === type).length; }
}

class FakeAudio implements VoiceAudio {
  frames: ((pcm: Uint8Array) => void) | null = null;
  played: number[] = [];
  cleared = 0;
  closed = false;
  playing = false;
  onIdle: () => void = () => {};
  async startCapture(onFrame: (pcm: Uint8Array) => void) { this.frames = onFrame; }
  setMuted() {}
  play(pcm: Uint8Array) { this.played.push(pcm.length); this.playing = true; }
  clearPlayback() { this.cleared += 1; this.playing = false; }
  clearCapture() {}
  level() { return 0; }
  speaking() { return this.playing; }
  close() { this.closed = true; this.frames = null; }
  /** One 100 ms frame: loud speech, or quiet room noise. */
  frame(voiced: boolean) {
    const pcm = new Uint8Array(4800);
    const v = new DataView(pcm.buffer);
    for (let i = 0; i < 2400; i++) v.setInt16(i * 2, voiced ? (i % 2 ? 6000 : -6000) : (i % 2 ? 40 : -40), true);
    this.frames?.(pcm);
  }
}

const SCOPE: VoiceScopeInput = { context_id: "ctx_0123456789abcdef", case_id: "case_1", case_version: 3, screen: "question", focus: { kind: "card", id: "field-date" }, destinations: ["settings", "questions"], attachment_ids: [] };

function harness(over: Partial<VoiceDeps> = {}) {
  const sockets: FakeSocket[] = [];
  const audio = new FakeAudio();
  const mic = { asked: 0, stopped: 0 };
  const timers: { at: number; fn: () => void; id: number }[] = [];
  let clock = 1_000_000;
  let nextId = 1;
  const deps: VoiceDeps = {
    socket: (url, protocol) => { const s = new FakeSocket(url, protocol); sockets.push(s); return s; },
    microphone: async () => { mic.asked += 1; return { stop: () => { mic.stopped += 1; } }; },
    audio: (_m, events) => { audio.onIdle = events.onIdle; return audio; },
    now: () => clock,
    setTimer: (fn, ms) => { const id = nextId++; timers.push({ at: clock + ms, fn, id }); return id; },
    clearTimer: (id) => { const i = timers.findIndex((t) => t.id === id); if (i >= 0) timers.splice(i, 1); },
    page: () => ({ protocol: "https:", host: "batatis.example" }),
    ...over,
  };
  const transcripts: VoiceTranscript[] = [];
  const responses: { text: string; withheld: boolean; turnId: string }[] = [];
  const ends: string[] = [];
  const client = new VoiceClient(deps, {
    onTranscript: (t) => transcripts.push(t),
    onResponse: (r) => responses.push(r),
    onEnd: (r) => ends.push(r),
  });
  const advance = (ms: number) => {
    clock += ms;
    for (const t of [...timers].sort((a, b) => a.at - b.at)) if (t.at <= clock && timers.includes(t)) { timers.splice(timers.indexOf(t), 1); t.fn(); }
  };
  /** Frames are 100 ms of wall time too. */
  const say = (voicedFrames: number, quietFrames = 0) => {
    for (let i = 0; i < voicedFrames; i++) { audio.frame(true); clock += 100; }
    for (let i = 0; i < quietFrames; i++) { audio.frame(false); clock += 100; }
  };
  return { client, sockets, audio, transcripts, responses, ends, advance, say, mic };
}

const flush = () => new Promise((r) => setTimeout(r, 0));
const ID = { session_id: "voice_abc" };
const ids = (revision: number | null, over: Record<string, unknown> = {}) => ({ ...ID, context_id: revision === null ? null : SCOPE.context_id, revision, case_id: revision === null ? null : "case_1", case_version: revision === null ? null : 3, ...over });

async function started(over: Partial<VoiceDeps> = {}) {
  const h = harness(over);
  void h.client.start("/api/voice/relay/session", SCOPE);
  await flush();
  const s = h.sockets[0];
  s.open();
  s.emit({ type: "session.ready", ...ids(null), notice: "n" });
  s.emit({ type: "session.started", ...ids(0), expires_at: 1000 + 55, max_seconds: 55, notice: "n", audio: { encoding: "pcm_s16le", rate: 24000, channels: 1 } });
  await flush();
  // A moment of room tone so the noise floor is learned.
  h.say(0, 5);
  return { ...h, s };
}

/** One full spoken turn up to its acknowledgement. */
function committedTurn(h: Awaited<ReturnType<typeof started>>, turn = "item_1", revision = 0) {
  h.say(6, 10);
  assert.equal(h.s.count("audio.commit"), h.s.sent.filter((m) => m.type === "audio.commit").length);
  h.s.emit({ type: "audio.clear", ...ids(revision) }); // owed for the utterance's first frame
  h.s.emit({ type: "audio.committed", ...ids(revision), turn_id: turn });
}

test("capability and relay URL: only the documented same-origin path and protocol", () => {
  const ok = { available: true, reason: null, protocol: "batatis.voice.v1", relay_path: "/api/voice/relay/session", max_seconds: 55, notice: "Voice sends your microphone audio to a third-party AI service." };
  assert.deepEqual(checkCapability(ok), ok);
  assert.equal(checkCapability({ ...ok, relay_path: "wss://evil.example/relay" }), null);
  assert.equal(checkCapability({ ...ok, protocol: "other" }), null);
  assert.equal(checkCapability({ ...ok, notice: " " }), null);
  assert.equal(relayUrl({ protocol: "https:", host: "batatis.example" }), "wss://batatis.example/api/voice/relay/session");
  assert.equal(relayUrl({ protocol: "http:", host: "localhost:5480" }), "ws://localhost:5480/api/voice/relay/session");
  assert.equal(relayUrl({ protocol: "https:", host: "user:pw@batatis.example" }), null);
  assert.equal(relayUrl({ protocol: "file:", host: "" }), null);
  assert.equal(relayUrl({ protocol: "https:", host: "batatis.example" }, "/api/voice/relay/session?token=1"), null);
});

test("microphone first, then the same-origin relay with the subprotocol; start waits for ready", async () => {
  const h = harness();
  void h.client.start("/api/voice/relay/session", SCOPE);
  await flush();
  assert.equal(h.mic.asked, 1);
  assert.equal(h.sockets[0].url, "wss://batatis.example/api/voice/relay/session");
  assert.equal(h.sockets[0].protocol, "batatis.voice.v1");
  h.sockets[0].open();
  assert.deepEqual(h.sockets[0].sent, []);
  h.sockets[0].emit({ type: "session.ready", ...ids(null), notice: "n" });
  assert.deepEqual(h.sockets[0].sent, [{ type: "session.start", scope: { ...SCOPE, revision: 0 } }]);
  assert.equal(h.client.snapshot().status, "connecting");
});

test("denied, missing or failing microphones open no relay and say why", async () => {
  for (const [name, problem] of [["NotAllowedError", "denied"], ["NotFoundError", "no-mic"], ["AbortError", "unavailable"]] as const) {
    const h = harness({ microphone: async () => { throw Object.assign(new Error(name), { name }); } });
    await h.client.start("/api/voice/relay/session", SCOPE);
    assert.equal(h.sockets.length, 0, name);
    assert.equal(h.client.snapshot().status, "ended");
    assert.equal(h.client.snapshot().problem, problem);
  }
});

test("a microphone granted after the person ended is released at once and opens nothing", async () => {
  let grant: (m: { stop(): void }) => void = () => {};
  let stopped = 0;
  const h = harness({ microphone: () => new Promise((r) => { grant = r; }) });
  void h.client.start("/api/voice/relay/session", SCOPE);
  await flush();
  h.client.end();
  grant({ stop: () => { stopped += 1; } });
  await flush();
  assert.equal(stopped, 1);
  assert.equal(h.sockets.length, 0);
});

test("silence is never sent and never answered", async () => {
  const h = await started();
  h.say(0, 40);
  assert.equal(h.s.count("audio.append"), 0);
  assert.equal(h.s.count("audio.commit"), 0);
  assert.equal(h.client.snapshot().status, "listening");
  // A short click is not a turn either.
  h.say(1, 20);
  assert.equal(h.s.count("audio.append"), 0);
});

test("a natural pause commits one utterance, then nothing is appended until audio.committed", async () => {
  const h = await started();
  h.say(6);
  assert.ok(h.s.count("audio.append") >= 6, "pre-roll and speech are sent once speech starts");
  assert.equal(h.client.snapshot().status, "hearing");
  assert.equal(h.client.snapshot().canCommit, true);
  h.say(0, 10);
  assert.equal(h.s.count("audio.commit"), 1);
  const commit = h.s.sent.find((m) => m.type === "audio.commit")!;
  assert.deepEqual(commit, { type: "audio.commit", session_id: "voice_abc", context_id: SCOPE.context_id, revision: 0 });
  const appended = h.s.count("audio.append");
  // The next utterance begins before the acknowledgement: it is held, not appended.
  h.say(5);
  assert.equal(h.s.count("audio.append"), appended);
  assert.equal(h.s.count("audio.commit"), 1, "only one commit pending");
  h.s.emit({ type: "audio.clear", ...ids(0) });
  h.s.emit({ type: "audio.committed", ...ids(0), turn_id: "item_1" });
  assert.ok(h.s.count("audio.append") > appended, "held speech follows the acknowledgement");
});

test("Done commits early only when there is real speech", async () => {
  const h = await started();
  assert.equal(h.client.commit(), false);
  h.say(4);
  assert.equal(h.client.commit(), true);
  assert.equal(h.s.count("audio.commit"), 1);
  assert.equal(h.client.commit(), false, "a second commit waits for the acknowledgement");
});

test("only the latest committed turn's final transcript is shown or navigates", async () => {
  const h = await started();
  committedTurn(h);
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_old", text: "Open settings", navigation: { destination: "settings" } });
  assert.equal(h.transcripts.length, 0, "another turn id is ignored");
  h.s.emit({ type: "transcript.completed", ...ids(0, { case_version: 4 }), turn_id: "item_1", text: "Open settings", navigation: { destination: "settings" } });
  assert.equal(h.transcripts.length, 0, "another case version is ignored");
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_1", text: "Open settings", navigation: { destination: "settings" } });
  assert.equal(h.transcripts.length, 1);
  assert.equal(h.transcripts[0].navigation, "settings");
  assert.deepEqual(h.transcripts[0].identity, { sessionId: "voice_abc", contextId: SCOPE.context_id, revision: 0, caseId: "case_1", caseVersion: 3 });
});

test("answers play only for the current turn; withheld audio never plays", async () => {
  const h = await started();
  committedTurn(h);
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_1", text: "What is a variance?", navigation: null });
  h.s.emit({ type: "response.text", ...ids(0), response_id: "r1", text: "An alternative solution…", withheld_audio: true });
  h.s.emit({ type: "response.audio", ...ids(0), response_id: "r1", audio: "AAAAAA==" });
  assert.equal(h.audio.played.length, 0);
  h.s.emit({ type: "response.done", ...ids(0), response_id: "r1" });
  committedTurn(h, "item_2");
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_2", text: "And then?", navigation: null });
  h.s.emit({ type: "response.text", ...ids(0), response_id: "r2", text: "Then the officer reviews it.", withheld_audio: false });
  h.s.emit({ type: "response.audio", ...ids(0, { session_id: "voice_other" }), response_id: "r2", audio: "AAAAAA==" });
  assert.equal(h.audio.played.length, 0, "another session's audio is dropped");
  h.s.emit({ type: "response.audio", ...ids(0), response_id: "r2", audio: "AAAAAA==" });
  assert.equal(h.audio.played.length, 1);
  assert.equal(h.client.snapshot().status, "speaking");
  assert.deepEqual(h.responses.map((r) => r.withheld), [true, false]);
});

test("its own playback is never sent back as speech (echo guard and tail)", async () => {
  const h = await started();
  committedTurn(h);
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_1", text: "Explain", navigation: null });
  h.s.emit({ type: "response.text", ...ids(0), response_id: "r1", text: "Sure.", withheld_audio: false });
  h.s.emit({ type: "response.audio", ...ids(0), response_id: "r1", audio: "AAAAAA==" });
  const before = h.s.count("audio.append");
  h.say(10, 10); // the speaker's sound reaches the microphone
  assert.equal(h.s.count("audio.append"), before);
  h.audio.playing = false;
  h.audio.onIdle();
  h.say(3); // still inside the echo tail
  assert.equal(h.s.count("audio.append"), before);
  h.say(0, 5);
  h.say(5);
  assert.ok(h.s.count("audio.append") > before, "after the tail the person can speak again");
});

test("stop speaking: playback stops at once; an answer still coming is cancelled behind one barrier", async () => {
  const h = await started();
  committedTurn(h);
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_1", text: "Explain", navigation: null });
  assert.equal(h.client.stopSpeaking(), true);
  assert.equal(h.s.count("response.cancel"), 1);
  assert.equal(h.client.snapshot().status, "stopping");
  // Nothing but end may be sent until the acknowledgement.
  h.advance(600);
  h.say(6, 10);
  assert.equal(h.s.count("audio.append") + h.s.count("audio.commit"), h.s.sent.filter((m) => m.type === "audio.append" || m.type === "audio.commit").length);
  const sentBefore = h.s.sent.length;
  assert.equal(h.client.update({ ...SCOPE, screen: "review" }), true, "queued behind the barrier");
  assert.equal(h.s.sent.length, sentBefore, "nothing sent during the barrier");
  h.s.emit({ type: "response.text", ...ids(0), response_id: "r1", text: "late", withheld_audio: false });
  assert.equal(h.responses.length, 0, "a late answer from before the stop is ignored");
  h.s.emit({ type: "audio.clear", ...ids(0) });
  assert.equal(h.s.count("context.update"), 1, "the queued update follows the acknowledgement");
  assert.equal(h.client.snapshot().status, "updating");
});

test("a stop with nothing in flight only silences playback (no paid message)", async () => {
  const h = await started();
  assert.equal(h.client.stopSpeaking(), true);
  assert.equal(h.s.count("response.cancel"), 0);
});

test("context update: stops playback, discards in-flight speech, waits for context.updated, then the new revision", async () => {
  const h = await started();
  committedTurn(h);
  h.s.emit({ type: "response.text", ...ids(0), response_id: "r1", text: "x", withheld_audio: false });
  h.say(4); // speaking when the screen changes
  const cleared = h.audio.cleared;
  assert.equal(h.client.update({ ...SCOPE, screen: "review", attachment_ids: ["file_1"] }), true);
  assert.ok(h.audio.cleared > cleared);
  const upd = h.s.sent.find((m) => m.type === "context.update")!;
  assert.equal(upd.revision, 0, "sent at the acknowledged revision");
  assert.deepEqual(upd.scope, { ...SCOPE, screen: "review", attachment_ids: ["file_1"], revision: 1 });
  assert.equal(h.client.snapshot().lostTurn, true);
  // During the barrier: no frames, commits or events from either revision act.
  const sent = h.s.sent.length;
  h.say(6, 10);
  assert.equal(h.s.sent.length, sent);
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_1", text: "Open settings", navigation: { destination: "settings" } });
  h.s.emit({ type: "transcript.completed", ...ids(1), turn_id: "item_1", text: "Open settings", navigation: { destination: "settings" } });
  assert.equal(h.transcripts.length, 0);
  h.s.emit({ type: "audio.clear", ...ids(0) });
  h.s.emit({ type: "context.updated", ...ids(2) });
  assert.equal(h.client.snapshot().status, "updating", "a wrong revision is not the acknowledgement");
  h.s.emit({ type: "context.updated", ...ids(1) });
  assert.equal(h.client.snapshot().revision, 1);
  h.say(0, 5);
  h.say(6, 10);
  const commit = h.s.sent.filter((m) => m.type === "audio.commit").at(-1)!;
  assert.equal(commit.revision, 1);
  assert.equal(h.client.snapshot().lostTurn, false, "speaking again clears the hint");
});

test("a context update for another case or version is refused (end and start again instead)", async () => {
  const h = await started();
  assert.equal(h.client.update({ ...SCOPE, case_id: "case_2" }), false);
  assert.equal(h.client.update({ ...SCOPE, case_version: 4 }), false);
  assert.equal(h.s.count("context.update"), 0);
});

test("context changes before microphone grant travel in the initial start without a second control message", async () => {
  let grant!: (mic: { stop(): void }) => void;
  const h = harness({ microphone: () => new Promise(resolve => { grant = resolve; }) });
  const starting = h.client.start("/api/voice/relay/session", SCOPE);
  assert.equal(h.client.update({ ...SCOPE, focus: { kind: "card", id: "field-owner" } }), true);
  grant({ stop() {} }); await starting;
  const s = h.sockets[0]; s.open(); s.emit({ type: "session.ready", ...ids(null), notice: "n" });
  assert.equal((s.sent[0].scope as { focus: { id: string } }).focus.id, "field-owner");
  assert.equal(s.count("context.update"), 0); assert.equal(s.count("session.end"), 0);
});

test("a scope change after session.start waits for session.started and its new revision acknowledgement", async () => {
  const h = harness(); await h.client.start("/api/voice/relay/session", SCOPE);
  const s = h.sockets[0]; s.open(); s.emit({ type: "session.ready", ...ids(null), notice: "n" });
  assert.equal(h.client.update({ ...SCOPE, screen: "review" }), true);
  assert.equal(s.count("context.update"), 0); assert.equal(s.count("session.end"), 0);
  s.emit({ type: "session.started", ...ids(0), expires_at: 1055, max_seconds: 55 });
  assert.equal(s.count("context.update"), 1); assert.equal(h.client.snapshot().status, "updating");
  s.emit({ type: "audio.clear", ...ids(0) }); s.emit({ type: "context.updated", ...ids(1) });
  assert.equal(h.client.currentScope()?.screen, "review"); assert.equal(h.client.snapshot().status, "listening");
});

test("local context invalidation drops old text/audio immediately and an older acknowledgement cannot resume it", async () => {
  const h = await started(); committedTurn(h, "old");
  h.client.invalidateContext();
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "old", text: "Old question" });
  h.s.emit({ type: "response.text", ...ids(0), response_id: "old-answer", text: "Old answer", withheld_audio: false });
  h.s.emit({ type: "response.audio", ...ids(0), response_id: "old-answer", audio: "AAA=" });
  assert.deepEqual(h.transcripts, []); assert.deepEqual(h.responses, []); assert.deepEqual(h.audio.played, []);
  assert.equal(h.client.update({ ...SCOPE, screen: "first" }), true);
  h.client.invalidateContext(); // another move while that update is still being acknowledged
  h.s.emit({ type: "audio.clear", ...ids(0) }); h.s.emit({ type: "context.updated", ...ids(1) });
  assert.equal(h.client.snapshot().status, "updating");
  const sent = h.s.count("audio.append"); h.say(6, 10); assert.equal(h.s.count("audio.append"), sent);
  assert.equal(h.client.update({ ...SCOPE, screen: "second" }), true);
  h.s.emit({ type: "audio.clear", ...ids(1) }); h.s.emit({ type: "context.updated", ...ids(2) });
  committedTurn(h, "fresh", 2);
  h.s.emit({ type: "transcript.completed", ...ids(2), turn_id: "fresh", text: "Fresh question" });
  h.s.emit({ type: "response.text", ...ids(2), response_id: "fresh-answer", text: "Fresh answer", withheld_audio: false });
  h.s.emit({ type: "response.audio", ...ids(2), response_id: "fresh-answer", audio: "AAA=" });
  assert.equal(h.transcripts.length, 1); assert.equal(h.responses.length, 1); assert.equal(h.audio.played.length, 1);
});

test("a view invalidated before the start acknowledgement stays paused until the new scope is acknowledged", async () => {
  const h = harness(); await h.client.start("/api/voice/relay/session", SCOPE);
  const s = h.sockets[0]; s.open(); s.emit({ type: "session.ready", ...ids(null), notice: "n" });
  h.client.invalidateContext();
  s.emit({ type: "session.started", ...ids(0), expires_at: 1055, max_seconds: 55 });
  assert.equal(h.client.snapshot().status, "updating");
  assert.equal(h.client.update({ ...SCOPE, screen: "new" }), true);
  s.emit({ type: "audio.clear", ...ids(0) }); s.emit({ type: "context.updated", ...ids(1) });
  assert.equal(h.client.snapshot().status, "listening");
});

test("capture initialization times out before opening a relay and releases the microphone", async () => {
  const audio = new FakeAudio(); audio.startCapture = () => new Promise(() => {});
  const h = harness({ audio: () => audio }); void h.client.start("/api/voice/relay/session", SCOPE); await flush();
  h.advance(30_000);
  assert.equal(h.client.snapshot().status, "ended"); assert.equal(h.sockets.length, 0);
  assert.equal(h.mic.stopped, 1); assert.equal(audio.closed, true);
});

test("updates queue behind a running update; only the newest is sent next", async () => {
  const h = await started();
  h.client.update({ ...SCOPE, screen: "a" });
  h.client.update({ ...SCOPE, screen: "b" });
  h.client.update({ ...SCOPE, screen: "c" });
  assert.equal(h.s.count("context.update"), 1);
  h.s.emit({ type: "audio.clear", ...ids(0) });
  h.s.emit({ type: "context.updated", ...ids(1) });
  const sent = h.s.sent.filter((m) => m.type === "context.update");
  assert.equal(sent.length, 2);
  assert.equal((sent[1].scope as { screen: string; revision: number }).screen, "c");
  assert.equal((sent[1].scope as { revision: number }).revision, 2);
});

test("a missing acknowledgement ends the session; it never reconnects", async () => {
  const h = await started();
  h.client.update({ ...SCOPE, screen: "review" });
  h.advance(10_000);
  assert.equal(h.client.snapshot().status, "ended");
  assert.equal(h.sockets.length, 1);
  assert.equal(h.audio.closed, true);
  assert.equal(h.mic.stopped, 1);
});

test("a commit that is never acknowledged ends the session", async () => {
  const h = await started();
  h.say(6, 10);
  h.advance(10_000);
  assert.equal(h.client.snapshot().status, "ended");
});

test("session.ended and a dropped socket release mic and playback; late events after end do nothing", async () => {
  const h = await started();
  h.s.emit({ type: "session.ended", ...ids(0), reason: "context_changed" });
  assert.equal(h.client.snapshot().reason, "context_changed");
  assert.equal(h.audio.closed, true);
  assert.equal(h.mic.stopped, 1);
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_1", text: "late", navigation: null });
  assert.equal(h.transcripts.length, 0);
  const d = await started();
  d.s.drop();
  assert.equal(d.client.snapshot().reason, "disconnected");
  assert.equal(d.sockets.length, 1);
});

test("rate or allowance refusal reports busy with the wait", async () => {
  const h = harness();
  void h.client.start("/api/voice/relay/session", SCOPE);
  await flush();
  const s = h.sockets[0];
  s.open();
  s.emit({ type: "session.ready", ...ids(null), notice: "n" });
  s.emit({ type: "session.error", ...ids(null), reason: "unavailable", message: "Voice unavailable", status: 429, retry_after: 12.2 });
  s.emit({ type: "session.ended", ...ids(null), reason: "unavailable" });
  assert.equal(h.client.snapshot().problem, "busy");
  assert.equal(h.client.snapshot().retryAfter, 13);
  assert.equal(h.client.snapshot().status, "ended");
});

test("ending before start sends the bare end; after start the bound end", async () => {
  const a = harness();
  void a.client.start("/api/voice/relay/session", SCOPE);
  await flush();
  a.sockets[0].open();
  a.sockets[0].emit({ type: "session.ready", ...ids(null), notice: "n" });
  const b = await started();
  b.client.end();
  assert.deepEqual(b.s.sent.at(-1), { type: "session.end", session_id: "voice_abc", context_id: SCOPE.context_id });
  const c = harness();
  void c.client.start("/api/voice/relay/session", SCOPE);
  await flush();
  c.sockets[0].open();
  c.client.end();
  assert.deepEqual(c.sockets[0].sent, [{ type: "session.end" }]);
  assert.equal(c.mic.stopped, 1);
});

test("duplicate or unsolicited acknowledgements change nothing", async () => {
  const h = await started();
  h.s.emit({ type: "audio.committed", ...ids(0), turn_id: "item_x" });
  h.s.emit({ type: "context.updated", ...ids(1) });
  assert.equal(h.client.snapshot().revision, 0);
  committedTurn(h);
  h.s.emit({ type: "audio.committed", ...ids(0), turn_id: "item_2" });
  h.s.emit({ type: "transcript.completed", ...ids(0), turn_id: "item_2", text: "x", navigation: null });
  assert.equal(h.transcripts.length, 0, "a second ack does not replace the turn");
});

test("the segmenter: a pause ends speech, blips fade, and the noise floor adapts", () => {
  const s = new Segmenter({ speechMs: 300, pauseMs: 800 });
  assert.equal(s.push(0.3, 100), "none", "the first moments only learn the room");
  for (let i = 0; i < 20; i++) assert.equal(s.push(0.004, 100), "none");
  assert.equal(s.push(0.2, 100), "none");
  for (let i = 0; i < 5; i++) s.push(0.004, 100);
  assert.equal(s.speaking, false, "a blip fades");
  s.push(0.2, 100); s.push(0.2, 100);
  assert.equal(s.push(0.2, 100), "start");
  for (let i = 0; i < 7; i++) assert.equal(s.push(0.004, 100), "none");
  assert.equal(s.push(0.004, 100), "end");
  const noisy = new Segmenter();
  for (let i = 0; i < 60; i++) noisy.push(0.03, 100);
  assert.equal(noisy.speaking, false, "steady background never becomes a turn");
});

test("speech immediately after Listening is retained without requiring initial silence", async () => {
  const h = harness(); void h.client.start("/api/voice/relay/session", SCOPE); await flush();
  const s = h.sockets[0]; s.open(); s.emit({ type: "session.ready", ...ids(null) });
  s.emit({ type: "session.started", ...ids(0), expires_at: 1055, max_seconds: 55 });
  h.say(20, 10); assert.equal(s.count("audio.commit"), 1); h.client.end();
});

test("mute clears partial upstream input and waits for acknowledgement before another utterance", async () => {
  const h = await started(); h.say(6); const before = h.s.count("audio.append");
  h.client.toggleMute(); assert.equal(h.s.count("audio.clear"), 1);
  h.client.toggleMute(); h.say(6, 10); assert.equal(h.s.count("audio.append"), before);
  h.s.emit({ type: "audio.clear", ...ids(0) }); // first append's clear
  h.s.emit({ type: "audio.clear", ...ids(0) }); // mute barrier's acknowledgement
  h.say(6, 10); assert.equal(h.s.count("audio.commit"), 1); h.client.end();
});

test("an old response.done cannot suppress the next turn's checked response", async () => {
  const h = await started(); committedTurn(h, "first");
  h.s.emit({ type: "response.text", ...ids(0), response_id: "first-response", text: "First answer", withheld_audio: true });
  h.say(6, 10);
  h.s.emit({ type: "response.done", ...ids(0), response_id: "first-response" });
  h.s.emit({ type: "audio.clear", ...ids(0) }); h.s.emit({ type: "audio.committed", ...ids(0), turn_id: "second" });
  h.s.emit({ type: "response.text", ...ids(0), response_id: "second-response", text: "Second answer", withheld_audio: true });
  assert.deepEqual(h.responses.map((r) => r.text), ["First answer", "Second answer"]); h.client.end();
});

test("a repeated completed transcript displays and navigates only once", async () => {
  const h = await started(); committedTurn(h, "one-turn");
  const event = { type: "transcript.completed", ...ids(0), turn_id: "one-turn", text: "Open settings", navigation: { destination: "settings" } };
  h.s.emit(event); h.s.emit(event);
  assert.equal(h.transcripts.length, 1); assert.equal(h.transcripts[0].navigation, "settings"); h.client.end();
});
