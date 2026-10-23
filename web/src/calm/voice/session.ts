/**
 * One voice conversation over the server's relay (docs/api/voice.md). The browser holds no provider
 * credential and speaks only the relay's small public protocol.
 *
 * Lifecycle: microphone first (a denial opens no relay and reserves nothing) → socket →
 * `session.ready` → `session.start` → `session.started` → turns → end. Never reconnects or
 * restarts by itself: another conversation is a fresh explicit start.
 *
 * Turns are manual. Nothing is sent while the room is quiet; once the segmenter hears speech, the
 * held pre-roll and the following frames are appended, and after a natural pause (or Done) one
 * `audio.commit` finishes the utterance. No frame is appended again until the matching
 * `audio.committed`. Only the final transcript of the latest committed turn of the current
 * revision is shown or may navigate.
 *
 * Barriers: a context update and a stop (`response.cancel`) each wait for the relay's
 * acknowledgement (`context.updated` / `audio.clear`) before any other command; meanwhile only
 * `session.end` may be sent. Playback stops at once on every barrier and on every `audio.clear`.
 * Microphone frames are not used while the assistant is speaking (and briefly after), so its own
 * voice is never sent back as a question.
 *
 * Every event is checked against this session, context, case, version and revision.
 */
import { base64ToBytes, bytesToBase64, PCM_RATE } from "./pcm";
import { command, isEndReason, parseEvent, relayUrl, VOICE_PROTOCOL, type CommandType, type Destination, type EndReason, type Scope, type ServerEvent } from "./protocol";
import { pcmRms, Segmenter, type SegmenterOptions } from "./segmenter";

export interface SocketLike {
  readyState: number;
  bufferedAmount: number;
  send(data: string): void;
  close(code?: number): void;
  onmessage: ((e: { data: unknown }) => void) | null;
  onclose: ((e: { code: number }) => void) | null;
  onerror: (() => void) | null;
}

export interface MicHandle {
  stop(): void;
}

/** Capture and playback for one session (audio.ts in the browser; a fake in tests). */
export interface VoiceAudio {
  startCapture(onFrame: (pcm16: Uint8Array) => void): Promise<void>;
  setMuted(muted: boolean): void;
  play(pcm16: Uint8Array): void;
  clearPlayback(): void;
  /** Drop partial microphone frames and queued worklet blocks at an utterance boundary. */
  clearCapture(): void;
  level(): number;
  speaking(): boolean;
  close(): void;
}

export interface VoiceDeps {
  socket(url: string, protocol: string): SocketLike;
  microphone(): Promise<MicHandle>;
  audio(mic: MicHandle, events: { onIdle(): void }): VoiceAudio;
  now(): number;
  setTimer(fn: () => void, ms: number): number;
  clearTimer(id: number): void;
  /** This page's location; the relay is same-origin only. */
  page(): { protocol: string; host: string };
  segmenter?: Partial<SegmenterOptions>;
}

/**
 * idle → mic (browser asking) → connecting → listening ⇄ hearing (speech in progress) → sending
 * (committed, waiting for the answer) → speaking → listening; updating / stopping are barriers.
 */
export type VoiceStatus = "idle" | "mic" | "connecting" | "listening" | "hearing" | "sending" | "speaking" | "updating" | "stopping" | "ended";
/** Why it could not run, in product terms. */
export type VoiceProblem = "denied" | "no-mic" | "busy" | "unavailable" | null;

export interface VoiceSnapshot {
  status: VoiceStatus;
  muted: boolean;
  /** Seconds left (server expiry), or null before it starts. */
  remaining: number | null;
  reason: EndReason | null;
  problem: VoiceProblem;
  retryAfter: number | null;
  /** Speech is in progress and long enough that Done can send it. */
  canCommit: boolean;
  /** A context change discarded what was being said or answered; ask to say it again. */
  lostTurn: boolean;
  /** This conversation's control messages are nearly used up; end and start a new one. */
  spent: boolean;
  /** The scope revision the relay acknowledged. */
  revision: number;
}

export type VoiceScopeInput = Omit<Scope, "revision">;

export interface VoiceTranscript {
  turnId: string;
  text: string;
  navigation: Destination | null;
  /** The identity this turn was heard in; the caller re-checks it before acting. */
  identity: { sessionId: string; contextId: string; revision: number; caseId: string | null; caseVersion: number | null };
}

export interface VoiceEvents {
  onTranscript(t: VoiceTranscript): void;
  onResponse(r: { responseId: string; turnId: string; text: string; withheld: boolean }): void;
  onEnd?(reason: EndReason): void;
}

const READY_MS = 8000;
const STARTED_MS = 25000;
/** The relay fails its own barriers after a few seconds; this is the browser's backstop. */
const BARRIER_MS = 9000;
const COMMIT_ACK_MS = 9000;
const MAX_BUFFERED = 256 * 1024;
/** Accepted input is capped at 55 s of PCM bytes server-side; never send past it. */
const MAX_INPUT_BYTES = 55 * PCM_RATE * 2;
/** Frames kept while quiet, so the first syllable is not cut off (~300 ms). */
const PREROLL_FRAMES = 3;
/** Speech that starts while a commit waits for its acknowledgement is held (up to ~5 s). */
const MAX_HELD_FRAMES = 50;
/** After the assistant stops talking, the microphone waits this long (room echo). */
const ECHO_TAIL_MS = 450;
/**
 * The relay allows 20 non-audio upstream messages per session (configuration, each commit and its
 * response request, clear, cancel, context). The browser cannot see the count, so it keeps a
 * conservative estimate and stops offering turns before the relay would refuse one.
 */
const CONTROL_LIMIT = 20;
const COST = { config: 1, turn: 2, bargeIn: 1, cancel: 2, update: 3 } as const;

type Input =
  /** Nothing appended since the last commit/clear: frames wait in the pre-roll. */
  | { kind: "quiet" }
  /** An utterance is being appended. */
  | { kind: "open" }
  /** `audio.commit` sent; waiting for `audio.committed`. */
  | { kind: "committing"; timer: number };

type Barrier = { kind: "update"; revision: number; scope: Scope; generation: number; timer: number } | { kind: "cancel"; timer: number } | null;

export class VoiceClient {
  private epoch = 0;
  private socket: SocketLike | null = null;
  private mic: MicHandle | null = null;
  private audio: VoiceAudio | null = null;
  private sessionId: string | null = null;
  private scope: Scope | null = null;
  private startSent = false;
  private started = false;
  private input: Input = { kind: "quiet" };
  private barrier: Barrier = null;
  /** The newest scope asked for while a barrier was running. */
  private queued: { scope: VoiceScopeInput; generation: number } | null = null;
  private localGeneration = 0;
  private acknowledgedGeneration = 0;
  private scopeGeneration = 0;
  private startGeneration = 0;
  /** `audio.clear` events the relay owes for utterances and updates already sent. */
  private clearsOwed = 0;
  /** The latest committed turn; only its transcript and answer count. */
  private turn: string | null = null;
  /** A committed turn awaits its transcript or answer (a stop must cancel it upstream). */
  private answering = false;
  /** Responses of the current turn whose checked text allowed speech. */
  private speakable = new Set<string>();
  private responseId: string | null = null;
  private seenResponses = new Set<string>();
  private seenTranscripts = new Set<string>();
  private preroll: Uint8Array[] = [];
  private held: Uint8Array[] = [];
  /** The held utterance already finished (its pause came before the acknowledgement). */
  private heldDone = false;
  private segmenter: Segmenter;
  private echoUntil = 0;
  private inputBytes = 0;
  private controlUsed = 0;
  private expiresAt: number | null = null;
  private maxSeconds = 55;
  private timers = new Set<number>();
  private snap: VoiceSnapshot = VoiceClient.blank();
  private listeners = new Set<() => void>();

  private readonly deps: VoiceDeps;
  private readonly events: VoiceEvents;

  constructor(deps: VoiceDeps, events: VoiceEvents) {
    this.deps = deps;
    this.events = events;
    this.segmenter = new Segmenter(deps.segmenter);
  }

  static blank(): VoiceSnapshot {
    return { status: "idle", muted: false, remaining: null, reason: null, problem: null, retryAfter: null, canCommit: false, lostTurn: false, spent: false, revision: 0 };
  }

  snapshot(): VoiceSnapshot {
    return this.snap;
  }

  subscribe(l: () => void): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }

  level(): number {
    return this.audio?.level() ?? 0;
  }

  /** Starting or running (not idle, not ended). */
  get active(): boolean {
    return this.snap.status !== "idle" && this.snap.status !== "ended";
  }

  /** The scope the relay acknowledged (null before start). */
  currentScope(): Scope | null {
    return this.scope;
  }

  private set(next: Partial<VoiceSnapshot>) {
    const keys = Object.keys(next) as (keyof VoiceSnapshot)[];
    if (keys.every((k) => next[k] === this.snap[k])) return;
    this.snap = { ...this.snap, ...next };
    for (const l of this.listeners) l();
  }

  private timer(fn: () => void, ms: number): number {
    const id = this.deps.setTimer(() => { this.timers.delete(id); fn(); }, ms);
    this.timers.add(id);
    return id;
  }

  private cancelTimer(id: number | undefined) {
    if (id === undefined) return;
    this.deps.clearTimer(id);
    this.timers.delete(id);
  }

  /** Explicit start (after the notice). Ends with a problem instead of throwing. */
  async start(relayPath: string, input: VoiceScopeInput): Promise<void> {
    if (this.active) return;
    const epoch = ++this.epoch;
    this.reset();
    const url = relayUrl(this.deps.page(), relayPath);
    this.scope = { ...input, revision: 0 };
    this.set({ ...VoiceClient.blank(), status: "mic" });
    if (!url) return this.finish("unavailable", "unavailable");
    let mic: MicHandle;
    try {
      mic = await this.deps.microphone();
    } catch (e) {
      if (epoch !== this.epoch) return;
      const name = (e as { name?: string })?.name;
      this.finish("ended", name === "NotFoundError" || name === "OverconstrainedError" ? "no-mic" : name === "NotAllowedError" || name === "SecurityError" ? "denied" : "unavailable");
      return;
    }
    if (epoch !== this.epoch) {
      mic.stop(); // ended, switched or unmounted while the browser was still asking
      return;
    }
    this.mic = mic;
    try {
      this.audio = this.deps.audio(mic, { onIdle: () => { if (epoch === this.epoch) this.onPlaybackIdle(); } });
    } catch {
      return this.finish("unavailable", "unavailable");
    }
    const captureTimer = this.timer(() => {
      if (epoch === this.epoch) this.finish("unavailable", "unavailable");
    }, READY_MS);
    try {
      await this.audio.startCapture((pcm) => { if (epoch === this.epoch) this.onFrame(pcm); });
      this.cancelTimer(captureTimer);
    } catch {
      this.cancelTimer(captureTimer);
      if (epoch === this.epoch) this.finish("unavailable", "unavailable");
      return;
    }
    if (epoch !== this.epoch) return;
    let socket: SocketLike;
    try {
      socket = this.deps.socket(url, VOICE_PROTOCOL);
    } catch {
      return this.finish("unavailable", "unavailable");
    }
    this.socket = socket;
    this.set({ status: "connecting" });
    const ready = this.timer(() => { if (epoch === this.epoch && !this.sessionId) this.end("disconnected", "unavailable"); }, READY_MS);
    socket.onmessage = (m) => {
      if (epoch !== this.epoch) return;
      const e = parseEvent(m.data);
      if (e) this.onEvent(e, ready);
    };
    socket.onclose = () => {
      if (epoch === this.epoch && this.active) this.finish("disconnected", this.snap.problem ?? (this.started ? null : "unavailable"));
    };
    socket.onerror = () => {};
  }

  /** Stop now: tell the relay (bare before start, bound after) and release everything. */
  end(reason: EndReason = "ended", problem: VoiceProblem = this.snap.problem) {
    if (!this.active) return;
    const socket = this.socket;
    if (socket && socket.readyState === 1) {
      const bound = this.startSent && this.sessionId && this.scope;
      try {
        socket.send(JSON.stringify(bound ? { type: "session.end", session_id: this.sessionId, context_id: this.scope!.context_id } : { type: "session.end" }));
      } catch { /* closing anyway */ }
    }
    this.finish(reason, problem);
  }

  toggleMute() {
    if (!this.active) return;
    const muted = !this.snap.muted;
    this.audio?.setMuted(muted);
    if (muted) {
      this.discardSpeech();
      if (this.started && !this.barrier && (this.input.kind !== "quiet" || this.answering)) {
        if (!this.afford(COST.cancel) || !this.send("audio.clear")) { this.end("limit"); return; }
        this.controlUsed += COST.cancel;
        if (this.input.kind === "committing") this.cancelTimer(this.input.timer);
        this.input = { kind: "quiet" }; this.turn = null; this.answering = false;
        this.responseId = null; this.speakable.clear(); this.audio?.clearPlayback();
        this.barrier = { kind: "cancel", timer: this.timer(() => this.end("unavailable", "unavailable"), BARRIER_MS) };
      }
    }
    this.set({ muted });
    this.refresh();
  }

  /** Done: send the utterance in progress now instead of waiting for the pause. */
  commit(): boolean {
    if (!this.segmenter.ready || this.input.kind !== "open") return false;
    this.segmenter.reset();
    return this.sendCommit();
  }

  /**
   * Stop the assistant talking. Local playback stops at once; an answer still coming is cancelled
   * upstream (one barrier, acknowledged by `audio.clear`).
   */
  stopSpeaking(): boolean {
    this.audio?.clearPlayback();
    this.speakable.clear();
    this.echoUntil = this.deps.now() + ECHO_TAIL_MS;
    if (!this.started || this.barrier || !this.answering) {
      this.refresh();
      return true;
    }
    if (!this.afford(COST.cancel)) return false;
    if (!this.send("response.cancel")) return false;
    this.controlUsed += COST.cancel;
    this.answering = false;
    this.turn = null;
    this.discardSpeech();
    if (this.input.kind === "committing") this.cancelTimer(this.input.timer);
    this.input = { kind: "quiet" };
    this.barrier = { kind: "cancel", timer: this.timer(() => this.end("unavailable", "unavailable"), BARRIER_MS) };
    this.refresh();
    return true;
  }

  /** Pause stale local input/output immediately, before a batched upstream update is sent. */
  invalidateContext() {
    if (!this.active) return;
    this.localGeneration += 1;
    const lost = this.segmenter.speaking || this.input.kind !== "quiet" || this.answering;
    if (this.input.kind === "committing") this.cancelTimer(this.input.timer);
    this.input = { kind: "quiet" };
    this.turn = null;
    this.answering = false;
    this.responseId = null;
    this.speakable.clear();
    this.discardSpeech();
    this.audio?.clearPlayback();
    if (lost) this.set({ lostTurn: true });
    this.refresh();
  }

  /** Replace reference scope. Same case/context/version only; resume after its acknowledgement. */
  update(input: VoiceScopeInput, generation = this.localGeneration): boolean {
    if (!this.active || !this.scope) return false;
    if (input.context_id !== this.scope.context_id || input.case_id !== this.scope.case_id || input.case_version !== this.scope.case_version) return false;
    if (!this.started) {
      // Before session.start, use the latest scope in the one start message. Once sent, wait
      // for session.started before asking the relay to acknowledge a new revision.
      if (!this.startSent) { this.scope = { ...input, revision: 0 }; this.scopeGeneration = generation; }
      else this.queued = { scope: input, generation };
      return true;
    }
    if (this.barrier) {
      this.queued = { scope: input, generation };
      return true;
    }
    if (!this.afford(COST.update)) return false;
    const revision = this.scope.revision + 1;
    const scope: Scope = { ...input, revision };
    if (!this.send("context.update", { scope })) return false;
    this.controlUsed += COST.update;
    this.clearsOwed += 1; // the relay clears playback first
    // What was being said or answered belongs to the old context: discard it, say so.
    const lost = this.segmenter.speaking || this.input.kind !== "quiet" || this.answering;
    if (this.input.kind === "committing") this.cancelTimer(this.input.timer);
    this.input = { kind: "quiet" };
    this.discardSpeech();
    this.turn = null;
    this.answering = false;
    this.speakable.clear();
    this.audio?.clearPlayback();
    this.barrier = { kind: "update", revision, scope, generation, timer: this.timer(() => this.end("context_changed", "unavailable"), BARRIER_MS) };
    if (lost) this.set({ lostTurn: true });
    this.refresh();
    return true;
  }

  private afford(cost: number): boolean {
    const ok = this.controlUsed + cost <= CONTROL_LIMIT;
    if (!ok) this.set({ spent: true });
    return ok;
  }

  private send(type: CommandType, extra: { audio?: string; scope?: Scope } = {}): boolean {
    const socket = this.socket;
    if (!socket || socket.readyState !== 1 || !this.sessionId || !this.scope) return false;
    try {
      socket.send(JSON.stringify(command(type, { session_id: this.sessionId, context_id: this.scope.context_id, revision: this.scope.revision }, extra)));
      return true;
    } catch {
      return false;
    }
  }

  private discardSpeech() {
    this.audio?.clearCapture?.();
    this.segmenter.reset();
    this.preroll = [];
    this.held = [];
    this.heldDone = false;
  }

  private append(pcm: Uint8Array): boolean {
    const socket = this.socket;
    if (!socket || socket.readyState !== 1) return false;
    if (socket.bufferedAmount > MAX_BUFFERED) return true; // real time: drop rather than queue without bound
    if (this.inputBytes + pcm.length > MAX_INPUT_BYTES) {
      this.end("limit");
      return false;
    }
    if (this.input.kind === "quiet") {
      // The first frame of an utterance: the relay clears any earlier answer and says so.
      if (this.answering) {
        if (!this.afford(COST.bargeIn)) return false;
        this.controlUsed += COST.bargeIn;
      }
      this.clearsOwed += 1;
      this.turn = null;
      this.answering = false;
      this.responseId = null;
      this.speakable.clear();
      this.input = { kind: "open" };
    }
    if (!this.send("audio.append", { audio: bytesToBase64(pcm) })) return false;
    this.inputBytes += pcm.length;
    return true;
  }

  private sendCommit(): boolean {
    if (this.input.kind !== "open" || this.barrier) return false;
    if (!this.afford(COST.turn)) {
      this.discardSpeech();
      return false;
    }
    if (!this.send("audio.commit")) return false;
    this.controlUsed += COST.turn;
    this.input = { kind: "committing", timer: this.timer(() => this.end("unavailable", "unavailable"), COMMIT_ACK_MS) };
    this.answering = true;
    this.refresh();
    return true;
  }

  private onFrame(pcm: Uint8Array) {
    if (!this.started || this.snap.muted || this.localGeneration !== this.acknowledgedGeneration || !pcm.length) return;
    const now = this.deps.now();
    // Never hear our own voice: no frames while it plays, nor for a moment after.
    if (this.audio?.speaking()) this.echoUntil = now + ECHO_TAIL_MS;
    if (now < this.echoUntil) {
      if (this.segmenter.speaking) this.discardSpeech();
      return;
    }
    if (this.barrier) return; // only session.end may be sent now; this speech is discarded
    const ms = (pcm.length / 2 / PCM_RATE) * 1000;
    const event = this.segmenter.push(pcmRms(pcm), ms);
    if (this.input.kind === "committing") {
      // Waiting for the relay to acknowledge the last utterance: hold the next one briefly.
      if (this.heldDone) return; // one held utterance at a time
      if (event === "start" || this.held.length) {
        if (event === "start") this.held = [...this.preroll];
        this.held.push(pcm);
        if (this.held.length > MAX_HELD_FRAMES) this.held.shift();
      } else this.keepPreroll(pcm);
      if (event === "end") this.heldDone = this.held.length > 0;
      this.refresh();
      return;
    }
    if (!this.segmenter.speaking && event !== "end") {
      this.keepPreroll(pcm);
      this.refresh();
      return;
    }
    if (event === "start") {
      const frames = [...this.preroll, pcm];
      this.preroll = [];
      for (const f of frames) if (!this.append(f)) return;
    } else if (!this.append(pcm)) return;
    if (event === "end") this.sendCommit();
    if (this.snap.lostTurn) this.set({ lostTurn: false });
    this.refresh();
  }

  private keepPreroll(pcm: Uint8Array) {
    this.preroll.push(pcm);
    if (this.preroll.length > PREROLL_FRAMES) this.preroll.shift();
  }

  private onPlaybackIdle() {
    this.echoUntil = this.deps.now() + ECHO_TAIL_MS;
    this.refresh();
  }

  /** Same session, context, case and version as the scope the relay holds. */
  private ours(e: ServerEvent): boolean {
    const s = this.scope;
    return Boolean(s) && e.session_id === this.sessionId && e.context_id === s!.context_id && e.case_id === s!.case_id && e.case_version === s!.case_version;
  }

  /** Ours, at the acknowledged revision, with no barrier running. */
  private current(e: ServerEvent): boolean {
    return this.ours(e) && !this.barrier && this.localGeneration === this.acknowledgedGeneration && e.revision === this.scope!.revision;
  }

  private onEvent(e: ServerEvent, readyTimer: number) {
    if (!this.active) return;
    if (e.type === "session.ready") {
      if (this.sessionId || e.context_id !== null || this.socket?.readyState !== 1) return;
      this.sessionId = e.session_id;
      this.cancelTimer(readyTimer);
      try {
        this.socket.send(JSON.stringify({ type: "session.start", scope: this.scope }));
        this.startGeneration = this.scopeGeneration;
        this.startSent = true;
      } catch {
        return this.end("disconnected", "unavailable");
      }
      this.timer(() => { if (!this.started && this.active) this.end("disconnected", "unavailable"); }, STARTED_MS);
      return;
    }
    if (e.session_id !== this.sessionId) return;
    const unscoped = e.context_id === null && e.revision === null && e.case_id === null && e.case_version === null;
    switch (e.type) {
      case "session.started": {
        if (this.started || !this.ours(e) || e.revision !== 0) return;
        this.expiresAt = typeof e.expires_at === "number" ? e.expires_at : null;
        this.maxSeconds = typeof e.max_seconds === "number" && e.max_seconds > 0 ? Math.min(e.max_seconds, 600) : 55;
        this.started = true;
        this.acknowledgedGeneration = this.startGeneration;
        this.controlUsed = COST.config;
        this.discardSpeech();
        this.tick();
        this.afterBarrier();
        this.refresh();
        return;
      }
      case "session.error": {
        if (!unscoped && !this.ours(e)) return;
        const retry = typeof e.retry_after === "number" && e.retry_after > 0 ? Math.min(3600, Math.ceil(e.retry_after)) : null;
        this.set({ problem: e.status === 429 ? "busy" : "unavailable", retryAfter: retry });
        return;
      }
      case "session.ended": {
        if (!unscoped && !this.ours(e)) return;
        const reason = isEndReason(e.reason) ? e.reason : "ended";
        this.finish(reason, this.snap.problem ?? (reason === "unavailable" ? "unavailable" : null));
        return;
      }
      case "audio.clear": {
        if (!this.ours(e)) return;
        // Always stop what is playing; then settle whoever was owed this acknowledgement.
        this.audio?.clearPlayback();
        if (this.clearsOwed > 0) this.clearsOwed -= 1;
        else if (this.barrier?.kind === "cancel") {
          this.cancelTimer(this.barrier.timer);
          this.barrier = null;
          this.discardSpeech();
          this.afterBarrier();
        }
        this.refresh();
        return;
      }
      case "context.updated": {
        const b = this.barrier;
        if (!this.ours(e) || b?.kind !== "update" || e.revision !== b.revision) return;
        this.cancelTimer(b.timer);
        this.scope = b.scope;
        this.scopeGeneration = b.generation;
        this.acknowledgedGeneration = b.generation;
        this.barrier = null;
        this.discardSpeech();
        this.clearsOwed = 0; // the update's own clear came before this, in order
        this.set({ revision: b.revision });
        this.afterBarrier();
        this.refresh();
        return;
      }
      case "audio.committed": {
        if (!this.current(e) || this.input.kind !== "committing") return;
        const turnId = e.turn_id;
        if (typeof turnId !== "string" || !turnId || turnId.length > 100) return this.end("invalid_request", "unavailable");
        this.cancelTimer(this.input.timer);
        this.input = { kind: "quiet" };
        this.turn = turnId;
        // Speech that began meanwhile is the next utterance: send what was held (and finish it
        // if its pause already came). The relay then supersedes the turn just acknowledged.
        const frames = this.held, done = this.heldDone;
        this.held = [];
        this.heldDone = false;
        if (frames.length && (done || this.segmenter.speaking)) {
          let sent = true;
          for (const f of frames) if (!(sent = this.append(f))) break;
          if (sent && done) this.sendCommit();
        }
        this.refresh();
        return;
      }
      case "transcript.completed": {
        if (!this.current(e) || typeof e.turn_id !== "string" || e.turn_id !== this.turn || typeof e.text !== "string" || !e.text.trim() || this.seenTranscripts.has(e.turn_id)) return;
        this.seenTranscripts.add(e.turn_id);
        const raw = e.navigation && typeof e.navigation === "object" ? (e.navigation as { destination?: unknown }).destination : null;
        const navigation = typeof raw === "string" && raw.length <= 60 ? (raw as Destination) : null;
        // A navigation plan has no spoken answer.
        if (navigation) this.answering = false;
        const s = this.scope!;
        this.events.onTranscript({
          turnId: e.turn_id, text: e.text.slice(0, 1500), navigation,
          identity: { sessionId: this.sessionId!, contextId: s.context_id, revision: s.revision, caseId: s.case_id, caseVersion: s.case_version },
        });
        this.refresh();
        return;
      }
      case "response.text": {
        if (!this.current(e) || !this.turn || !this.answering || typeof e.response_id !== "string" || !e.response_id || typeof e.text !== "string") return;
        if (this.seenResponses.has(e.response_id)) return;
        this.seenResponses.add(e.response_id);
        this.responseId = e.response_id;
        const withheld = e.withheld_audio !== false;
        if (!withheld) this.speakable.add(e.response_id);
        this.events.onResponse({ responseId: e.response_id, turnId: this.turn, text: e.text.slice(0, 6000), withheld });
        return;
      }
      case "response.audio": {
        if (!this.current(e) || typeof e.response_id !== "string" || !this.speakable.has(e.response_id) || typeof e.audio !== "string") return;
        const pcm = base64ToBytes(e.audio);
        if (!pcm.length || pcm.length % 2) return;
        this.audio?.play(pcm);
        this.discardSpeech();
        this.refresh();
        return;
      }
      case "response.done": {
        if (!this.current(e) || typeof e.response_id !== "string" || e.response_id !== this.responseId) return;
        this.speakable.delete(e.response_id);
        this.answering = false;
        this.refresh();
        return;
      }
      default:
        return; // unknown events never act
    }
  }

  private afterBarrier() {
    const next = this.queued;
    this.queued = null;
    if (next && !this.update(next.scope, next.generation)) this.end("context_changed");
  }

  private refresh() {
    if (!this.active || this.snap.status === "mic") return;
    if (!this.started) return this.set({ status: "connecting" });
    const speaking = Boolean(this.audio?.speaking());
    const status: VoiceStatus = this.localGeneration !== this.acknowledgedGeneration || this.barrier?.kind === "update" ? "updating"
      : this.barrier?.kind === "cancel" ? "stopping"
        : speaking ? "speaking"
          : this.input.kind === "committing" || this.answering ? (this.segmenter.speaking ? "hearing" : "sending")
            : this.segmenter.speaking ? "hearing" : "listening";
    this.set({
      status,
      canCommit: !this.barrier && this.localGeneration === this.acknowledgedGeneration && this.input.kind === "open" && this.segmenter.ready,
      spent: this.controlUsed + COST.turn > CONTROL_LIMIT,
    });
  }

  /** Once a second: the time left. Past the server's expiry (plus grace) it ends here too. */
  private tick() {
    if (!this.active || this.expiresAt === null) return;
    const left = this.expiresAt - this.deps.now() / 1000;
    this.set({ remaining: Math.max(0, Math.min(this.maxSeconds, Math.ceil(left))) });
    if (left < -5) return this.end("expired");
    this.timer(() => this.tick(), 1000);
  }

  private reset() {
    this.segmenter = new Segmenter(this.deps.segmenter);
    for (const id of this.timers) this.deps.clearTimer(id);
    this.timers.clear();
    this.sessionId = null;
    this.startSent = false;
    this.started = false;
    this.localGeneration = this.acknowledgedGeneration = this.scopeGeneration = this.startGeneration = 0;
    this.input = { kind: "quiet" };
    this.barrier = null;
    this.queued = null;
    this.clearsOwed = 0;
    this.turn = null;
    this.answering = false;
    this.speakable.clear();
    this.discardSpeech();
    this.echoUntil = 0;
    this.responseId = null;
    this.seenResponses.clear();
    this.seenTranscripts.clear();
    this.inputBytes = 0;
    this.controlUsed = 0;
    this.expiresAt = null;
  }

  /** Release everything this session holds. Idempotent; never reconnects. */
  private finish(reason: EndReason, problem: VoiceProblem = this.snap.problem) {
    const socket = this.socket;
    this.socket = null;
    this.epoch += 1;
    for (const id of this.timers) this.deps.clearTimer(id);
    this.timers.clear();
    try { this.audio?.close(); } catch { /* already closed */ }
    this.audio = null;
    try { this.mic?.stop(); } catch { /* already stopped */ }
    this.mic = null;
    if (socket) {
      socket.onmessage = null;
      socket.onclose = null;
      // Let a just-sent end leave before closing; the relay cleans up either way.
      if (socket.readyState === 1) this.deps.setTimer(() => socket.close(1000), 400);
      else try { socket.close(1000); } catch { /* never opened */ }
    }
    const wasActive = this.active;
    this.started = false;
    this.barrier = null;
    this.input = { kind: "quiet" };
    this.discardSpeech();
    this.set({ status: "ended", reason, problem, canCommit: false, remaining: null });
    if (wasActive) this.events.onEnd?.(reason);
  }
}
