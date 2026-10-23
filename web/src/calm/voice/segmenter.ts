/**
 * Natural turn-taking for manual turns: decides when a spoken utterance has started and when it
 * is finished, from the loudness of each microphone frame. Pure and clocked by frame length, so
 * it is tested without a browser.
 *
 * - Speech starts once enough voiced audio has been heard (a cough or a click is not a turn).
 * - It is finished after a natural pause, or at a hard length limit.
 * - Silence alone never starts or finishes anything: nothing is ever sent as a question.
 * The noise floor adapts while nobody is speaking, so a fan or traffic does not count as voice.
 */

export interface SegmenterOptions {
  /** Absolute floor for a voiced frame (RMS of samples in [-1, 1]). */
  minRms: number;
  /** Voiced frames must be this many times louder than the measured background. */
  overNoise: number;
  /** Voiced audio needed before an utterance counts. */
  speechMs: number;
  /** Quiet after speech that ends the utterance. */
  pauseMs: number;
  /** A single utterance never runs longer than this. */
  maxMs: number;
}

export const DEFAULT_SEGMENTER: SegmenterOptions = { minRms: 0.015, overNoise: 3, speechMs: 300, pauseMs: 850, maxMs: 20_000 };

const CALIBRATION_MS = 400;

export type SegmentEvent = "none" | "start" | "end";

export class Segmenter {
  private readonly o: SegmenterOptions;
  private noise = 0;
  /** Background heard so far; the first moments only learn it (its quietest level). */
  private calibratedMs = 0;
  /** Voiced audio in the candidate or current utterance. */
  private voicedMs = 0;
  /** Time since the candidate started (voiced or not), and quiet since the last voiced frame. */
  private spanMs = 0;
  private quietMs = 0;
  private started = false;

  constructor(options: Partial<SegmenterOptions> = {}) {
    this.o = { ...DEFAULT_SEGMENTER, ...options };
  }

  /** In an utterance that will be sent (speech has started and has not ended). */
  get speaking(): boolean {
    return this.started;
  }

  /** Enough voice for a manual "Done" to send it. */
  get ready(): boolean {
    return this.started && this.voicedMs >= this.o.speechMs;
  }

  threshold(): number {
    return Math.max(this.o.minRms, this.noise * this.o.overNoise);
  }

  /**
   * One frame of `ms` milliseconds with loudness `rms`. "start" when this frame begins a real
   * utterance (the caller sends its held pre-roll then), "end" when it finishes one.
   */
  push(rms: number, ms: number): SegmentEvent {
    // Loud first speech is a candidate immediately, never a noise-floor sample. Quieter room
    // tone still calibrates, so a steady fan doesn't become a turn at startup.
    if (!this.started && this.voicedMs === 0 && this.calibratedMs < CALIBRATION_MS && rms <= this.o.minRms * this.o.overNoise) {
      this.noise = this.calibratedMs === 0 ? rms : Math.min(this.noise, rms);
      this.calibratedMs += ms;
      return "none";
    }
    const voiced = rms > this.threshold();
    if (!this.started) {
      if (!voiced) {
        // Background: follow it (down quickly, up slowly), and let a lone blip fade.
        this.noise = rms < this.noise ? this.noise * 0.7 + rms * 0.3 : this.noise * 0.95 + rms * 0.05;
        this.quietMs += ms;
        if (this.quietMs >= 300) { this.voicedMs = 0; this.spanMs = 0; }
        return "none";
      }
      this.voicedMs += ms;
      this.spanMs += ms;
      this.quietMs = 0;
      if (this.voicedMs < this.o.speechMs) return "none";
      this.started = true;
      return "start";
    }
    this.spanMs += ms;
    if (voiced) {
      this.voicedMs += ms;
      this.quietMs = 0;
    } else {
      this.quietMs += ms;
    }
    if (this.quietMs >= this.o.pauseMs || this.spanMs >= this.o.maxMs) {
      this.reset();
      return "end";
    }
    return "none";
  }

  /** Forget the utterance in progress (sent, discarded, muted). The noise floor is kept. */
  reset() {
    this.started = false;
    this.voicedMs = 0;
    this.spanMs = 0;
    this.quietMs = 0;
  }
}

/** RMS loudness of PCM16 LE bytes, in [0, 1]. */
export function pcmRms(pcm: Uint8Array): number {
  if (pcm.length < 2) return 0;
  const view = new DataView(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  const n = pcm.length >> 1;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const s = view.getInt16(i * 2, true) / 0x8000;
    sum += s * s;
  }
  return Math.sqrt(sum / n);
}
