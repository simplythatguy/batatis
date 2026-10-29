// The room: slide groups on the left; the selected group's stage, controls and transcript in the middle.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./icons";
import { startRecording, type Recording } from "./recorder";
import { Render } from "./Render";
import { roomApi } from "./room";
import { createStage, preload, type Stage } from "./stage";
import { CopyLink, type Camera } from "./parts";
import { clock, deckMs, targetMs } from "./timing";
import { VIDEO_LIMIT_MS, type Cue, type Deck, type Group, type Person, type RoomState, type TakeInfo, type TakeMedia } from "./types";
import { uploads, useUploads } from "./uploads";

type Phase =
  | { k: "idle" }
  | { k: "countdown"; n: number }
  | { k: "recording"; startedAt: number; slide: number }
  | { k: "review"; media: TakeMedia };

const busy = (p: Phase) => p.k !== "idle";
const complete = (t: TakeInfo | undefined) => !!t && t.received >= t.chunks;

/** The slide on screen `ms` into a take. */
function slideAt(cues: Cue[], ms: number): number {
  let slide = 0;
  for (const c of cues) if (c.atMs <= ms) slide = c.slide;
  return slide;
}

export function Room({ deck, room, me, camera, apply, onLeave }: {
  deck: Deck;
  room: RoomState;
  me: Person;
  camera: Camera;
  apply(next: RoomState): void;
  onLeave(): void;
}) {
  const [selected, setSelected] = useState(() => {
    const mine = deck.groups.findIndex((g) => room.assignments[g.id] === me.id && !complete(room.takes[g.id]));
    return Math.max(0, mine);
  });
  const [phase, setPhase] = useState<Phase>({ k: "idle" });
  const [rendering, setRendering] = useState(false);
  const progress = useUploads();

  useEffect(() => {
    void preload(deck).catch(() => undefined);
  }, [deck]);

  useEffect(() => {
    void uploads.resume(room.code, room);
    // Once per room: later polls must not restart uploads in flight.
  }, [room.code]);

  const missing = deck.groups.filter((g) => !complete(room.takes[g.id]) || progress[g.id] !== undefined);
  const total = deckMs(deck);

  return (
    <div className="st-room">
      <aside className="st-side">
        <header className="st-side-head">
          <span className="st-brand">Studio</span>
          <CopyLink code={room.code} />
        </header>
        <nav className="st-groups" aria-label="Slide groups">
          {deck.groups.map((g, i) => (
            <GroupRow
              key={g.id}
              group={g}
              room={room}
              upload={progress[g.id]}
              selected={!rendering && i === selected}
              locked={busy(phase)}
              onSelect={() => {
                setRendering(false);
                setSelected(i);
              }}
              onAssign={(personId) => void roomApi.assign(room.code, g.id, personId).then(apply)}
            />
          ))}
        </nav>
        <div className={`st-total${total > VIDEO_LIMIT_MS ? " is-over" : ""}`} title="Planned length with intro and outro">
          <Icon name="clock" size={13} />
          {clock(total)} / {clock(VIDEO_LIMIT_MS)}
        </div>
        <People room={room} me={me} locked={busy(phase)} onRemove={(id) => void roomApi.leave(room.code, id).then((next) => {
          apply(next);
          if (id === me.id) onLeave();
        })} />
        <div className="st-make">
          <button
            type="button"
            className={`cf-btn${missing.length ? "" : " is-primary"}`}
            disabled={missing.length > 0 || busy(phase) || rendering}
            title={missing.length ? `Missing: ${missing.map((g) => g.name).join(", ")}` : undefined}
            onClick={() => setRendering(true)}
          >
            <Icon name="film" size={15} />
            Make the video
          </button>
          {missing.length > 0 && <span className="st-make-left">{missing.length} to go</span>}
        </div>
      </aside>
      <main className="st-main">
        {rendering ? (
          <Render deck={deck} room={room} onClose={() => setRendering(false)} />
        ) : (
          <Booth
            key={deck.groups[selected].id}
            deck={deck}
            index={selected}
            room={room}
            me={me}
            camera={camera}
            phase={phase}
            setPhase={setPhase}
            onAssign={(personId) => void roomApi.assign(room.code, deck.groups[selected].id, personId).then(apply)}
          />
        )}
      </main>
    </div>
  );
}

function GroupRow({ group, room, upload, selected, locked, onSelect, onAssign }: {
  group: Group;
  room: RoomState;
  upload: number | undefined;
  selected: boolean;
  locked: boolean;
  onSelect(): void;
  onAssign(personId: string | null): void;
}) {
  const take = room.takes[group.id];
  const who = room.assignments[group.id] ?? "";
  const state = upload !== undefined
    ? <span className="st-g-up">{Math.round(upload * 100)}%</span>
    : take && !complete(take)
      ? <span className="st-g-up">{Math.round((take.received / take.chunks) * 100)}%</span>
      : take
        ? <span className="st-g-done"><Icon name="check" size={13} stroke={2.2} />{clock(take.durationMs)}</span>
        : <span className="st-g-empty" aria-label="Not recorded" />;
  return (
    <div className={`st-g${selected ? " is-sel" : ""}${locked && !selected ? " is-locked" : ""}`}>
      <button type="button" className="st-g-hit" onClick={onSelect} disabled={locked} aria-current={selected || undefined}>
        <span className="st-g-name">{group.name}</span>
        {state}
      </button>
      <div className="st-g-meta">
        <select
          className={`st-who${who ? "" : " is-none"}`}
          value={who}
          onChange={(e) => onAssign(e.target.value || null)}
          aria-label={`Who records ${group.name}`}
          disabled={locked}
        >
          <option value="">Nobody</option>
          {room.people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {!complete(take) && <span className="st-g-len">{clock(targetMs(group))}</span>}
      </div>
    </div>
  );
}

function People({ room, me, locked, onRemove }: { room: RoomState; me: Person; locked: boolean; onRemove(id: string): void }) {
  return (
    <ul className="st-people" aria-label="People">
      {room.people.map((p) => (
        <li key={p.id}>
          <Icon name="user" size={13} />
          <span>{p.name}{p.id === me.id ? " (you)" : ""}</span>
          <button type="button" className="st-x" disabled={locked} aria-label={`Remove ${p.name}`} title="Remove" onClick={() => onRemove(p.id)}>
            <Icon name="x" size={12} />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** The canvas the stage paints. `onStage` hands the live Stage to the parent. */
export function StageCanvas({ deck, onStage, children }: { deck: Deck; onStage(stage: Stage | null): void; children?: React.ReactNode }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvas.current!;
    c.width = 1920;
    c.height = 1080;
    const stage = createStage(c, deck);
    onStage(stage);
    return () => {
      onStage(null);
      stage.destroy();
    };
  }, [deck, onStage]);
  return (
    <div className="st-stage">
      <canvas ref={canvas} />
      {children}
    </div>
  );
}

function Booth({ deck, index, room, me, camera, phase, setPhase, onAssign }: {
  deck: Deck;
  index: number;
  room: RoomState;
  me: Person;
  camera: Camera;
  phase: Phase;
  setPhase(p: Phase): void;
  onAssign(personId: string): void;
}) {
  const group = deck.groups[index];
  const target = targetMs(group);
  const last = group.slides.length - 1;
  const [stage, setStage] = useState<Stage | null>(null);
  const [preview, setPreview] = useState(0);
  const [replaySlide, setReplaySlide] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const rec = useRef<Recording | null>(null);
  const cues = useRef<Cue[]>([]);
  const timers = useRef<number[]>([]);
  const attempt = useRef(0);
  const replay = useRef<HTMLVideoElement | null>(null);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const assignee = room.people.find((p) => p.id === room.assignments[group.id]);
  const mine = assignee?.id === me.id;
  const take = room.takes[group.id];

  const clearTimers = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  };

  // Idle: the selected slide with this device's live camera.
  useEffect(() => {
    if (!stage || phase.k === "review") return;
    stage.setCamera(camera.live);
  }, [stage, camera.live, phase.k]);
  useEffect(() => {
    if (stage && phase.k === "idle") stage.show(index, preview, { instant: true });
  }, [stage, index, preview, phase.k]);

  const finish = useCallback(async (auto: boolean) => {
    const r = rec.current;
    if (!r || phaseRef.current.k !== "recording") return;
    rec.current = null;
    clearTimers();
    const durationMs = auto ? target : Math.min(target, Math.round(performance.now() - r.startedAt));
    const { blob, mime } = await r.stop();
    setPhase({ k: "review", media: { blob, mime, cues: cues.current, durationMs } });
  }, [setPhase, target]);

  const start = useCallback(() => {
    if (!mine || !camera.stream || !stage || (phaseRef.current.k !== "idle" && phaseRef.current.k !== "review")) return;
    const token = ++attempt.current;
    (document.activeElement as HTMLElement | null)?.blur?.();
    stage.setCamera(camera.live);
    stage.show(index, 0, { instant: true });
    setReplaySlide(0);
    setElapsed(0);
    setPhase({ k: "countdown", n: 3 });
    const stream = camera.stream;
    timers.current.push(
      window.setTimeout(() => setPhase({ k: "countdown", n: 2 }), 1000),
      window.setTimeout(() => setPhase({ k: "countdown", n: 1 }), 2000),
      window.setTimeout(() => {
        void startRecording(stream).then((r) => {
          if (token !== attempt.current) return r.cancel();
          rec.current = r;
          cues.current = [{ slide: 0, atMs: 0 }];
          stage.show(index, 0, { instant: true });
          setPhase({ k: "recording", startedAt: r.startedAt, slide: 0 });
          timers.current.push(window.setTimeout(() => void finish(true), target - (performance.now() - r.startedAt)));
        }, () => setPhase({ k: "idle" }));
      }, 3000),
    );
  }, [camera.live, camera.stream, finish, index, mine, setPhase, stage, target]);

  const cancel = useCallback(() => {
    attempt.current++;
    clearTimers();
    rec.current?.cancel();
    rec.current = null;
    setPhase({ k: "idle" });
  }, [setPhase]);

  const step = useCallback((d: 1 | -1) => {
    const p = phaseRef.current;
    if (p.k !== "recording" || !stage) return;
    const slide = Math.min(last, Math.max(0, p.slide + d));
    if (slide === p.slide) return;
    cues.current = [...cues.current, { slide, atMs: Math.round(performance.now() - p.startedAt) }];
    stage.show(index, slide);
    setPhase({ ...p, slide });
  }, [index, last, setPhase, stage]);

  // Leaving the group mid-take (or unmounting) never leaves a recorder running.
  useEffect(() => () => {
    attempt.current++;
    clearTimers();
    rec.current?.cancel();
  }, []);

  // The countdown timer.
  useEffect(() => {
    if (phase.k !== "recording") return;
    const t = window.setInterval(() => setElapsed(performance.now() - phase.startedAt), 100);
    return () => window.clearInterval(t);
  }, [phase]);

  // Review: the take is the camera and its cues drive the slides.
  const media = phase.k === "review" ? phase.media : null;
  useEffect(() => {
    if (!media || !stage) return;
    const url = URL.createObjectURL(media.blob);
    const v = document.createElement("video");
    v.playsInline = true;
    v.src = url;
    replay.current = v;
    let shown = -1;
    let raf = 0;
    const tick = () => {
      const ms = v.currentTime * 1000;
      const slide = slideAt(media.cues, ms);
      if (slide !== shown) {
        stage.show(index, slide, { instant: shown === -1 });
        shown = slide;
        setReplaySlide(slide);
      }
      setElapsed(Math.min(ms, media.durationMs));
      if (ms >= media.durationMs && !v.paused) v.pause();
      raf = requestAnimationFrame(tick);
    };
    stage.setCamera(v);
    void v.play().catch(() => undefined);
    tick();
    return () => {
      cancelAnimationFrame(raf);
      v.pause();
      v.removeAttribute("src");
      v.load();
      URL.revokeObjectURL(url);
      replay.current = null;
      stage.setCamera(camera.live);
    };
  }, [media, stage, index, camera.live]);

  const keep = useCallback(async () => {
    if (!media) return;
    setPhase({ k: "idle" });
    await uploads.keep(room.code, group.id, me.id, media);
  }, [group.id, me.id, media, room.code, setPhase]);

  const again = () => {
    const v = replay.current;
    if (!v) return;
    v.currentTime = 0;
    void v.play();
  };

  // Keys: R record, Space/→ next slide, ← back, Esc cancel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input, select, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
      const p = phaseRef.current;
      if (e.key === "Escape" && (p.k === "countdown" || p.k === "recording")) {
        e.preventDefault();
        cancel();
      } else if (p.k === "recording" && (e.key === " " || e.key === "ArrowRight")) {
        e.preventDefault();
        step(1);
      } else if (p.k === "recording" && e.key === "ArrowLeft") {
        e.preventDefault();
        step(-1);
      } else if ((e.key === "r" || e.key === "R") && (p.k === "idle" || p.k === "review") && !e.repeat) {
        e.preventDefault();
        start();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cancel, start, step]);

  const current = phase.k === "recording" ? phase.slide : phase.k === "review" ? replaySlide : phase.k === "countdown" ? 0 : null;
  const remaining = phase.k === "recording" ? target - elapsed : target;

  return (
    <div className="st-booth">
      <header className="st-booth-head">
        <h1 className="st-title">{group.name}</h1>
        <span className="st-booth-who">
          {assignee ? <><Icon name="user" size={14} />{assignee.id === me.id ? "You" : assignee.name}</> : null}
        </span>
      </header>
      <StageCanvas deck={deck} onStage={setStage}>
        {phase.k === "countdown" && <div className="st-count" aria-live="assertive">{phase.n}</div>}
        {phase.k === "recording" && <div className="st-progress" style={{ transform: `scaleX(${Math.min(1, elapsed / target)})` }} />}
        {phase.k === "review" && <div className="st-progress is-review" style={{ transform: `scaleX(${Math.min(1, elapsed / phase.media.durationMs)})` }} />}
      </StageCanvas>

      <div className="st-bar">
        {phase.k === "idle" && (mine ? (
          <button type="button" className={`cf-btn is-lg st-rec${take ? "" : " is-primary"}`} onClick={start} disabled={!camera.stream || !stage}>
            <span className="st-dot" />{take ? "Record again" : "Record"}<kbd className="cf-kbd">R</kbd>
          </button>
        ) : assignee ? (
          <span className="st-blocked"><Icon name="user" size={14} />{assignee.name} records this</span>
        ) : (
          <button type="button" className="cf-btn is-lg" onClick={() => onAssign(me.id)}>Record this one</button>
        ))}
        {phase.k === "countdown" && (
          <button type="button" className="cf-btn is-lg" onClick={cancel}>Cancel<kbd className="cf-kbd">Esc</kbd></button>
        )}
        {phase.k === "recording" && (
          <>
            <button type="button" className="cf-btn is-lg" onClick={() => void finish(false)} aria-label="Stop">
              <span className="st-square" />Stop
            </button>
            <span className="st-steps">
              <button type="button" className="cf-icon-btn st-step" onClick={() => step(-1)} disabled={phase.slide === 0} aria-label="Previous slide" title="Previous slide (←)">
                <Icon name="prev" size={18} />
              </button>
              <span className="st-step-n">{phase.slide + 1} / {last + 1}</span>
              <button type="button" className="cf-icon-btn st-step" onClick={() => step(1)} disabled={phase.slide === last} aria-label="Next slide" title="Next slide (Space)">
                <Icon name="next" size={18} />
              </button>
            </span>
          </>
        )}
        {phase.k === "review" && (
          <>
            <button type="button" className="cf-btn is-primary is-lg" onClick={() => void keep()}>
              <Icon name="check" size={16} stroke={2.2} />Keep
            </button>
            <button type="button" className="cf-btn is-lg" onClick={start}>
              <Icon name="restart" size={15} />Retake
            </button>
            <button type="button" className="cf-icon-btn" onClick={again} aria-label="Play again" title="Play again">
              <Icon name="play" size={16} />
            </button>
            <button type="button" className="cf-icon-btn" onClick={() => setPhase({ k: "idle" })} aria-label="Discard take" title="Discard">
              <Icon name="x" size={16} />
            </button>
          </>
        )}
        <span className={`st-timer${phase.k === "recording" ? " is-live" : ""}`} aria-live="off">
          {phase.k === "recording" && <span className="st-live" aria-label="Recording" />}
          {phase.k === "review" ? `${clock(elapsed)} / ${clock(phase.media.durationMs)}` : clock(remaining)}
        </span>
      </div>

      <Transcript
        group={group}
        current={current}
        onPick={phase.k === "idle" ? setPreview : undefined}
        picked={phase.k === "idle" ? preview : null}
      />
    </div>
  );
}

function Transcript({ group, current, picked, onPick }: { group: Group; current: number | null; picked: number | null; onPick?: (slide: number) => void }) {
  const refs = useRef<(HTMLElement | null)[]>([]);
  useEffect(() => {
    if (current !== null) refs.current[current]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [current]);
  const last = group.script.length - 1;
  const items = useMemo(() => group.script.map((text, i) => ({ text, i })), [group.script]);
  return (
    <ol className={`st-script${current !== null ? " is-following" : ""}`} aria-label="Transcript">
      {items.map(({ text, i }) => (
        <li key={i} ref={(el) => { refs.current[i] = el; }} className={`st-seg${current === i ? " is-now" : ""}${picked === i ? " is-picked" : ""}`}>
          <button type="button" className="st-seg-hit" onClick={onPick ? () => onPick(i) : undefined} disabled={!onPick} aria-label={`Slide ${i + 1}`}>
            <span className="st-seg-n">{i + 1}</span>
            <span className="st-seg-text">{text}</span>
          </button>
          {i < last ? <span className="st-next" aria-label="Next slide">→</span> : <span className="st-stop" aria-label="Stop" />}
        </li>
      ))}
    </ol>
  );
}
