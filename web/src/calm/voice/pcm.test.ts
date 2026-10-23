import assert from "node:assert/strict";
import { test } from "node:test";
import { base64ToBytes, bytesToBase64, FRAME_SAMPLES, floatToPcm16, framePcm16, pcm16ToFloat, Resampler } from "./pcm.ts";

test("PCM16 is little-endian, clipped, and round-trips through base64", () => {
  const bytes = floatToPcm16(new Float32Array([0, 1, -1, 2, -2, 0.5]));
  // 0x7fff for +1 (and clipped +2), 0x8000 for -1 (and clipped -2), LE byte order.
  assert.deepEqual([...bytes], [0, 0, 0xff, 0x7f, 0x00, 0x80, 0xff, 0x7f, 0x00, 0x80, 0xff, 0x3f]);
  const back = base64ToBytes(bytesToBase64(bytes));
  assert.deepEqual([...back], [...bytes]);
  const f = pcm16ToFloat(back);
  assert.equal(f.length, 6);
  assert.ok(Math.abs(f[1] - 1) < 1e-4 && f[2] === -1 && Math.abs(f[5] - 0.5) < 1e-4);
});

test("an odd byte count is not PCM16 and decodes to nothing", () => {
  assert.equal(pcm16ToFloat(new Uint8Array([1, 2, 3])).length, 0);
  assert.equal(base64ToBytes("not base64!").length, 0);
});

test("48 kHz input becomes 24 kHz with continuity across chunk boundaries", () => {
  const r = new Resampler(48000);
  const tone = (n0: number, n: number) => Float32Array.from({ length: n }, (_, i) => Math.sin((2 * Math.PI * 440 * (n0 + i)) / 48000));
  const a = r.push(tone(0, 1000));
  const b = r.push(tone(1000, 1000));
  const out = new Float32Array([...a, ...b]);
  // Half as many samples, give or take the interpolation tail kept for the next chunk.
  assert.ok(Math.abs(out.length - 1000) <= 1, `got ${out.length}`);
  // Each output sample matches the 440 Hz tone sampled at 24 kHz (no seam at sample 500).
  for (let i = 0; i < out.length; i++) {
    const want = Math.sin((2 * Math.PI * 440 * i) / 24000);
    assert.ok(Math.abs(out[i] - want) < 0.02, `sample ${i}: ${out[i]} vs ${want}`);
  }
});

test("44.1 kHz input resamples to the 24 kHz rate", () => {
  const r = new Resampler(44100);
  const out = r.push(new Float32Array(44100));
  assert.ok(Math.abs(out.length - 24000) <= 1, `got ${out.length}`);
});

test("24 kHz input passes through unchanged", () => {
  const r = new Resampler(24000);
  const input = Float32Array.from({ length: 10 }, (_, i) => i / 10);
  assert.deepEqual([...r.push(input)], [...input]);
});

test("frames are 100 ms of PCM16 at 24 kHz, within the relay's 32,000-byte append limit", () => {
  const frames: Uint8Array[] = [];
  const framer = framePcm16((f) => frames.push(f));
  framer(new Float32Array(FRAME_SAMPLES + 100));
  assert.equal(frames.length, 1);
  assert.equal(frames[0].length, FRAME_SAMPLES * 2);
  assert.ok(frames[0].length <= 32000);
  framer(new Float32Array(FRAME_SAMPLES - 100));
  assert.equal(frames.length, 2);
});
