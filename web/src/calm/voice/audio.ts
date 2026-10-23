/**
 * Browser capture and playback for one voice session, in the relay's format (pcm.ts).
 *
 * Capture: microphone → AudioWorklet tap → 24 kHz (the context runs at 24 kHz when the browser
 * allows it; otherwise pcm.ts resamples) → 100 ms PCM16 frames. Playback: each checked PCM16 chunk
 * becomes an AudioBuffer scheduled back to back; clearing stops every queued source at once.
 * Level metering follows Irsal's voice connection (RMS of an AnalyserNode, x5, clamped).
 * Echo cancellation is requested from the browser; session.ts also ignores the microphone while
 * this plays. Everything is released by `close()`.
 */
import { framePcm16, pcm16ToFloat, PCM_RATE, Resampler } from "./pcm";
import type { MicHandle, VoiceAudio } from "./session";

export interface BrowserMic extends MicHandle {
  stream: MediaStream;
}

export async function openMicrophone(): Promise<BrowserMic> {
  if (!navigator.mediaDevices?.getUserMedia) throw Object.assign(new Error("No microphone API"), { name: "NotFoundError" });
  if (typeof AudioWorkletNode === "undefined") throw new Error("Voice capture is unavailable in this browser");
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  return { stream, stop: () => { for (const t of stream.getTracks()) t.stop(); } };
}

/** Posts the input in ~2048-sample batches; keeps no state beyond its buffer. */
const TAP = `
class BatatisTap extends AudioWorkletProcessor {
  constructor() {
    super(); this.buf = new Float32Array(2048); this.n = 0; this.epoch = 0;
    this.port.onmessage = (event) => {
      if (event.data.type !== "capture.reset" || !Number.isSafeInteger(event.data.epoch)) return;
      this.epoch = event.data.epoch; this.buf = new Float32Array(2048); this.n = 0;
    };
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      for (let i = 0; i < ch.length; i++) {
        this.buf[this.n++] = ch[i];
        if (this.n === this.buf.length) {
          this.port.postMessage({ type: "capture.samples", epoch: this.epoch, samples: this.buf }, [this.buf.buffer]);
          this.buf = new Float32Array(2048); this.n = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("batatis-tap", BatatisTap);
`;

/** Queued speech never exceeds this; the relay caps output at 55 s anyway. */
const MAX_QUEUED_SECONDS = 60;

function meter(analyser: AnalyserNode | null, data: Uint8Array<ArrayBuffer>): number {
  if (!analyser) return 0;
  analyser.getByteTimeDomainData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i++) sum += ((data[i] - 128) / 128) ** 2;
  return Math.sqrt(sum / data.length);
}

function context(): AudioContext {
  try {
    return new AudioContext({ sampleRate: PCM_RATE, latencyHint: "interactive" });
  } catch {
    return new AudioContext({ latencyHint: "interactive" });
  }
}

export function createVoiceAudio(mic: MicHandle, events: { onIdle(): void }): VoiceAudio {
  const stream = (mic as BrowserMic).stream;
  let ctx = context();
  // Construction can fail before VoiceClient receives the adapter. Keep context ownership here
  // until close(), including a failed default-rate fallback or a partially connected graph.
  let contextClosed = false;
  const closeContext = () => {
    if (contextClosed) return;
    contextClosed = true;
    try { void ctx.close().catch(() => undefined); } catch { /* already unavailable */ }
  };
  try {
    let source: MediaStreamAudioSourceNode;
    try {
      source = ctx.createMediaStreamSource(stream);
    } catch {
      // Some browsers cannot connect a microphone to a context at another rate: use the default rate.
      closeContext();
      ctx = new AudioContext({ latencyHint: "interactive" });
      contextClosed = false;
      source = ctx.createMediaStreamSource(stream);
    }
    const inputMeter = ctx.createAnalyser();
    inputMeter.fftSize = 256;
    source.connect(inputMeter);
    const output = ctx.createGain();
    output.connect(ctx.destination);
    const outputMeter = ctx.createAnalyser();
    outputMeter.fftSize = 256;
    output.connect(outputMeter);
    // A silent sink keeps the capture node pulled without sending the microphone to the speakers.
    const sink = ctx.createGain();
    sink.gain.value = 0;
    sink.connect(ctx.destination);
    const data = new Uint8Array(256);
    const sources = new Set<AudioBufferSourceNode>();
    let nextAt = 0;
    let muted = false;
    let closed = false;
    let tap: AudioWorkletNode | null = null;
    let moduleUrl: string | null = null;
    let captureEpoch = 0;
    let resetFrames = () => {};
    const clearCapture = () => {
      if (closed) return;
      captureEpoch += 1;
      resetFrames();
      tap?.port.postMessage({ type: "capture.reset", epoch: captureEpoch });
    };

    const idle = () => { if (!closed && sources.size === 0) events.onIdle(); };

    return {
      async startCapture(onFrame) {
        let resampler = new Resampler(ctx.sampleRate);
        let framer = framePcm16(onFrame);
        resetFrames = () => { resampler = new Resampler(ctx.sampleRate); framer = framePcm16(onFrame); };
        const take = (samples: Float32Array) => { if (!closed && !muted) framer(resampler.push(samples)); };
        if (ctx.state === "suspended") await ctx.resume().catch(() => undefined);
        if (closed) return;
        if (ctx.state !== "running") throw new Error("Audio capture did not start");
        // Worklet epochs also discard blocks already queued at a local context/mute boundary.
        // Browsers without this boundary support use the typed fallback.
        if (!ctx.audioWorklet || typeof AudioWorkletNode === "undefined") throw new Error("Voice capture is unavailable in this browser");
        moduleUrl = URL.createObjectURL(new Blob([TAP], { type: "text/javascript" }));
        await ctx.audioWorklet.addModule(moduleUrl);
        if (closed) return;
        const node = new AudioWorkletNode(ctx, "batatis-tap", { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1, channelCountMode: "explicit" });
        node.port.onmessage = (e: MessageEvent<{ type: string; epoch: number; samples: Float32Array }>) => {
          if (e.data?.type === "capture.samples" && e.data.epoch === captureEpoch && e.data.samples instanceof Float32Array) take(e.data.samples);
        };
        tap = node;
        node.port.postMessage({ type: "capture.reset", epoch: captureEpoch });
        source.connect(tap);
        tap.connect(sink);
      },
      setMuted(value) {
        clearCapture();
        muted = value;
        for (const t of stream.getAudioTracks()) t.enabled = !value;
      },
      clearCapture,
      play(pcm16) {
        if (closed) return;
        const samples = pcm16ToFloat(pcm16);
        if (!samples.length) return;
        const now = ctx.currentTime;
        if (Math.max(0, nextAt - now) + samples.length / PCM_RATE > MAX_QUEUED_SECONDS) return;
        const buffer = ctx.createBuffer(1, samples.length, PCM_RATE);
        buffer.copyToChannel(samples, 0);
        const node = ctx.createBufferSource();
        node.buffer = buffer;
        node.connect(output);
        const when = Math.max(now, nextAt);
        node.start(when);
        nextAt = when + samples.length / PCM_RATE;
        sources.add(node);
        node.onended = () => { sources.delete(node); node.disconnect(); idle(); };
      },
      clearPlayback() {
        for (const node of sources) {
          node.onended = null;
          try { node.stop(); } catch { /* not started */ }
          node.disconnect();
        }
        const had = sources.size > 0;
        sources.clear();
        nextAt = 0;
        if (had) idle();
      },
      level() {
        if (closed) return 0;
        if (sources.size) return Math.min(1, meter(outputMeter, data) * 5);
        return muted ? 0 : Math.min(1, meter(inputMeter, data) * 5);
      },
      speaking: () => sources.size > 0,
      close() {
        if (closed) return;
        closed = true;
        for (const node of sources) {
          node.onended = null;
          try { node.stop(); } catch { /* not started */ }
        }
        sources.clear();
        if (tap) {
          tap.port.onmessage = null;
          tap.disconnect();
        }
        source.disconnect();
        closeContext();
        if (moduleUrl) URL.revokeObjectURL(moduleUrl);
      },
    };
  } catch (error) {
    closeContext();
    throw error;
  }
}
