import assert from "node:assert/strict";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { createVoiceAudio } from "./audio.ts";
import { VoiceClient } from "./session.ts";
import { base64ToBytes } from "./pcm.ts";

class Node { connect() {} disconnect() {} }
const scope = { context_id: "ctx_0123456789abcdef", case_id: "A", case_version: 7, screen: "question", focus: { kind: "card", id: "field-owner" }, destinations: ["settings"], attachment_ids: [] };

/** Runs the real worklet source, capture framer and client, with no device or network. */
async function capture(boundary: "none" | "mute" | "revision" | "queued", partial = 2048, rate = 24000) {
  const originalContext = Object.getOwnPropertyDescriptor(globalThis, "AudioContext");
  const originalWorklet = Object.getOwnPropertyDescriptor(globalThis, "AudioWorkletNode");
  let Processor: new () => { port: { onmessage: ((e: { data: unknown }) => void) | null }; process(inputs: Float32Array[][]): void };
  const posted: unknown[] = [];
  let tap: Worklet;
  class ProcessorBase {
    port = { onmessage: null, postMessage(data: unknown) { posted.push(data); } };
  }
  class Context {
    state = "running"; sampleRate = rate; currentTime = 0; destination = new Node();
    audioWorklet = { addModule: async (url: string) => {
      const source = await (await fetch(url)).text();
      runInNewContext(source, { AudioWorkletProcessor: ProcessorBase, Float32Array, Number, registerProcessor(_name: string, ctor: typeof Processor) { Processor = ctor; } });
    } };
    createMediaStreamSource() { return new Node(); }
    createGain() { return Object.assign(new Node(), { gain: { value: 1 } }); }
    createAnalyser() { return Object.assign(new Node(), { fftSize: 256, getByteTimeDomainData: (a: Uint8Array) => a.fill(128) }); }
    close() { return Promise.resolve(); }
  }
  class Worklet extends Node {
    processor = new Processor();
    port = { onmessage: null as ((e: { data: unknown }) => void) | null, postMessage: (data: unknown) => this.processor.port.onmessage?.({ data }) };
    constructor() { super(); tap = this; }
    push(value: number, count = 2048) { this.processor.process([[new Float32Array(count).fill(value)]]); }
    flush() { for (const data of posted.splice(0)) this.port.onmessage?.({ data }); }
  }
  Object.defineProperty(globalThis, "AudioContext", { configurable: true, value: Context });
  Object.defineProperty(globalThis, "AudioWorkletNode", { configurable: true, value: Worklet });
  const track = { enabled: true, stop() {} };
  const mic = { stream: { getAudioTracks: () => [track] }, stop() {} };
  const socket = { readyState: 1, bufferedAmount: 0, sent: [] as Record<string, unknown>[], onmessage: null as ((e: { data: unknown }) => void) | null, onclose: null, onerror: null,
    send(text: string) { this.sent.push(JSON.parse(text)); }, close() {}, emit(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) }); } };
  const client = new VoiceClient({ socket: () => socket, microphone: async () => mic, audio: createVoiceAudio, now: () => 1_000_000, setTimer: () => 0, clearTimer() {}, page: () => ({ protocol: "https:", host: "batatis.example" }) }, { onTranscript() {}, onResponse() {} });
  try {
    await client.start("/api/voice/relay/session", scope);
    const ids = { session_id: "voice_audio", context_id: scope.context_id, revision: 0, case_id: "A", case_version: 7 };
    socket.emit({ type: "session.ready", session_id: ids.session_id, context_id: null, revision: null, case_id: null, case_version: null });
    socket.emit({ type: "session.started", ...ids, expires_at: 1055, max_seconds: 55 });
    tap!.push(.75, partial);
    if (boundary !== "queued") tap!.flush();
    assert.equal(socket.sent.filter(x => x.type === "audio.append").length, 0);
    if (boundary === "mute") { client.toggleMute(); client.toggleMute(); }
    if (boundary === "revision" || boundary === "queued") {
      client.invalidateContext(); assert.equal(client.update({ ...scope, screen: "settings", focus: null }), true);
      socket.emit({ type: "audio.clear", ...ids }); socket.emit({ type: "context.updated", ...ids, revision: 1 });
    }
    tap!.flush(); // queued old worklet messages arrive after the boundary
    for (let i = 0; i < 12; i++) { tap!.push(.125); tap!.flush(); }
    const appends = socket.sent.filter(x => x.type === "audio.append"); assert.ok(appends.length);
    let old = 0;
    for (const message of appends) {
      const bytes = base64ToBytes(message.audio as string), v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      for (let i = 0; i < bytes.length; i += 2) if (v.getInt16(i, true) > 20000) old++;
    }
    assert.equal(old, boundary === "none" ? partial : 0, "only the no-boundary control may retain earlier audio");
  } finally {
    client.end();
    if (originalContext) Object.defineProperty(globalThis, "AudioContext", originalContext); else Reflect.deleteProperty(globalThis, "AudioContext");
    if (originalWorklet) Object.defineProperty(globalThis, "AudioWorkletNode", originalWorklet); else Reflect.deleteProperty(globalThis, "AudioWorkletNode");
  }
}

test("actual capture drops a partial PCM frame across mute", () => capture("mute"));
test("actual capture drops old PCM after an acknowledged context revision", () => capture("revision"));
test("already queued worklet blocks cannot enter the acknowledged new scope", () => capture("queued"));
test("reset also discards samples still inside the worklet's partial buffer", () => capture("mute", 1024));
test("a non-24k resampler cannot retain a sample across a revision", () => capture("revision", 2048, 48000));
test("without a boundary, the worklet and framer preserve continuous input", () => capture("none"));

async function failedStartup(stage: "source" | "analyser" | "gain" | "connect" | "fallback") {
  const originalContext = Object.getOwnPropertyDescriptor(globalThis, "AudioContext");
  const contexts: Context[] = [];
  let stopped = 0, sockets = 0;
  const refuse = () => { throw new Error("Audio graph unavailable"); };
  class GraphNode extends Node {
    connect() { if (stage === "connect") refuse(); }
  }
  class Context {
    state = "running"; sampleRate = 24000; currentTime = 0; destination = new Node(); closed = 0;
    constructor() { contexts.push(this); }
    createMediaStreamSource() {
      if (stage === "source" || (stage === "fallback" && contexts[0] === this)) refuse();
      return new GraphNode();
    }
    createAnalyser() {
      if (stage === "analyser") refuse();
      return Object.assign(new GraphNode(), { fftSize: 256, getByteTimeDomainData: (a: Uint8Array) => a.fill(128) });
    }
    createGain() {
      if (stage === "gain") refuse();
      return Object.assign(new GraphNode(), { gain: { value: 1 } });
    }
    async close() { this.closed++; this.state = "closed"; }
  }
  Object.defineProperty(globalThis, "AudioContext", { configurable: true, value: Context });
  const client = new VoiceClient({
    socket() { sockets++; throw new Error("Failed audio setup must not open a relay"); },
    microphone: async () => ({ stream: { getAudioTracks: () => [] }, stop() { stopped++; } }),
    audio: createVoiceAudio, now: () => 1_000_000, setTimer: () => 0, clearTimer() {},
    page: () => ({ protocol: "https:", host: "batatis.example" }),
  }, { onTranscript() {}, onResponse() {} });
  try {
    await client.start("/api/voice/relay/session", scope);
    assert.equal(client.snapshot().status, "ended");
    assert.equal(client.snapshot().problem, "unavailable");
    assert.equal(stopped, 1);
    assert.equal(sockets, 0);
    assert.equal(contexts.length, stage === "source" || stage === "fallback" ? 2 : 1);
    assert.deepEqual(contexts.map(ctx => ctx.closed), contexts.map(() => 1), "every attempted context closes once, even before the adapter reaches the client");
  } finally {
    client.end();
    if (originalContext) Object.defineProperty(globalThis, "AudioContext", originalContext); else Reflect.deleteProperty(globalThis, "AudioContext");
  }
}

for (const stage of ["source", "analyser", "gain", "connect", "fallback"] as const) {
  test(`failed audio startup releases contexts at ${stage}`, () => failedStartup(stage));
}
