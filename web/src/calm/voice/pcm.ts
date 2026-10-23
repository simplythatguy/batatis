/**
 * The relay's audio format, and nothing else: PCM16 little-endian, mono, 24 kHz, base64 in JSON
 * (docs/api/voice.md). Pure functions, so capture and playback share one tested definition.
 */

export const PCM_RATE = 24000;
/** 100 ms per append: 4,800 bytes, well inside the relay's 32,000-byte frame limit. */
export const FRAME_SAMPLES = 2400;

/** Float samples in [-1, 1] to PCM16 LE bytes (clipped; +1 → 0x7fff, -1 → 0x8000). */
export function floatToPcm16(input: Float32Array): Uint8Array {
  const out = new Uint8Array(input.length * 2);
  const view = new DataView(out.buffer);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i] || 0));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return out;
}

/** PCM16 LE bytes to float samples. An odd byte count is not PCM16 and yields nothing. */
export function pcm16ToFloat(bytes: Uint8Array): Float32Array<ArrayBuffer> {
  if (bytes.length % 2) return new Float32Array(0);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const out = new Float32Array(bytes.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = view.getInt16(i * 2, true) / 0x8000;
  return out;
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

/** Base64 to bytes; anything that is not valid base64 decodes to an empty array. */
export function base64ToBytes(value: string): Uint8Array {
  let binary: string;
  try {
    binary = atob(value);
  } catch {
    return new Uint8Array(0);
  }
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

/**
 * Streaming linear-interpolation resampler from the microphone's rate to 24 kHz. It keeps its
 * position and the last input sample between chunks, so chunk boundaries leave no seam.
 * Microphone input is already band-limited speech; the browser's own 24 kHz AudioContext is
 * preferred and makes this a pass-through.
 */
export class Resampler {
  private readonly step: number;
  /** Next output position in [previous chunk's last sample, ...this chunk]; starts on the first sample. */
  private pos = 1;
  private last = 0;

  constructor(inputRate: number) {
    this.step = inputRate / PCM_RATE;
  }

  push(input: Float32Array): Float32Array {
    if (this.step === 1) return input;
    const n = input.length;
    const out: number[] = [];
    // Virtual buffer: index 0 is the previous chunk's last sample, index k is input[k - 1].
    while (this.pos < n) {
      const i = Math.floor(this.pos);
      const frac = this.pos - i;
      const a = i === 0 ? this.last : input[i - 1];
      const b = input[i];
      out.push(a + (b - a) * frac);
      this.pos += this.step;
    }
    this.pos -= n;
    if (n) this.last = input[n - 1];
    return Float32Array.from(out);
  }
}

/** Collect 24 kHz float samples into fixed PCM16 frames. */
export function framePcm16(emit: (frame: Uint8Array) => void) {
  let pending = new Float32Array(0);
  return (samples: Float32Array) => {
    const joined = new Float32Array(pending.length + samples.length);
    joined.set(pending);
    joined.set(samples, pending.length);
    let start = 0;
    while (joined.length - start >= FRAME_SAMPLES) {
      emit(floatToPcm16(joined.subarray(start, start + FRAME_SAMPLES)));
      start += FRAME_SAMPLES;
    }
    pending = joined.slice(start);
  };
}
