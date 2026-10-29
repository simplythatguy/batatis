// Throwaway harness for the stage: exposes window.H so a Playwright script can step slides, grab frames and export.
// ?deck=real paints the real deck (clips that do not exist yet fall back to the real-app stand-in);
// ?clock=manual swaps the page clock for one the script steps, so transition frames land on exact times.
import { deck as realDeck } from "../../deck";
import { testDeck } from "../../testDeck";
import type { Deck, TakeMedia } from "../../types";
import { createStage, exportVideo, preload } from "../index";

const params = new URLSearchParams(location.search);
const STAND_IN = "/studio/test/app.mp4";

let vt = 0;
const rafs: FrameRequestCallback[] = [];
if (params.get("clock") === "manual") {
  performance.now = () => vt;
  window.requestAnimationFrame = (cb) => rafs.push(cb);
  window.cancelAnimationFrame = () => {};
}

async function exists(src: string) {
  const res = await fetch(src, { method: "HEAD" });
  return res.ok && !(res.headers.get("content-type") ?? "").includes("text/html");
}

async function withStandIns(d: Deck): Promise<{ deck: Deck; standIns: string[] }> {
  const standIns: string[] = [];
  const groups = await Promise.all(
    d.groups.map(async (g) => ({
      ...g,
      slides: await Promise.all(
        g.slides.map(async (s) => {
          if (s.kind !== "clip" || (await exists(s.src))) return s;
          standIns.push(s.id);
          return { ...s, src: STAND_IN };
        }),
      ),
    })),
  );
  return { deck: { ...d, groups }, standIns };
}

const { deck, standIns } = params.get("deck") === "real" ? await withStandIns(realDeck) : { deck: testDeck, standIns: [] };
const canvas = document.getElementById("c") as HTMLCanvasElement;
const stage = createStage(canvas, deck);
let fake: HTMLVideoElement | null = null;

async function take(src: string, cues: TakeMedia["cues"], durationMs: number): Promise<TakeMedia> {
  const blob = await (await fetch(src)).blob();
  return { blob, mime: blob.type || "video/mp4", cues, durationMs };
}

const blobToBase64 = (b: Blob) =>
  new Promise<string>((r) => {
    const fr = new FileReader();
    fr.onload = () => {
      const s = String(fr.result);
      r(s.slice(s.indexOf("base64,") + 7));
    };
    fr.readAsDataURL(b);
  });

const H = {
  ready: preload(deck).then(() => true),
  standIns,
  slides: deck.groups.map((g) => g.slides.map((s) => s.id)),
  show: (g: number, s: number, instant = false) => stage.show(g, s, { instant }),
  card: (c: "intro" | "outro") => stage.showCard(c),
  /** Advance the manual clock by `ms` and paint one frame. */
  step(ms: number) {
    vt += ms;
    const due = rafs.splice(0);
    for (const cb of due) cb(vt);
  },
  async camera(on: boolean) {
    if (!on) return stage.setCamera(null);
    if (!fake) {
      fake = document.createElement("video");
      fake.muted = true;
      fake.srcObject = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
      await fake.play();
    }
    stage.setCamera(fake);
  },
  frame: () => canvas.toDataURL("image/png"),
  progress: [] as [number, string][],
  /** Exports the first two groups with the fake takes, cued across their slides. */
  async export() {
    const [a, b] = deck.groups;
    const cue = (n: number, ms: number) => Array.from({ length: n }, (_, i) => ({ slide: i, atMs: Math.round((i * ms) / n) }));
    const takes = {
      [a.id]: await take("/studio/test/take1.mp4", cue(a.slides.length, 6000), 6000),
      [b.id]: await take("/studio/test/take2.mp4", cue(b.slides.length, 5000), 5000),
    };
    const t0 = performance.now();
    try {
      const { blob, mime } = await exportVideo({ deck, takes, onProgress: (f, l) => H.progress.push([f, l]) });
      return { mime, size: blob.size, wallMs: performance.now() - t0, b64: await blobToBase64(blob) };
    } catch (e) {
      return { error: `${(e as Error).name}: ${(e as Error).message}`, wallMs: performance.now() - t0 };
    }
  },
};
(window as unknown as { H: typeof H }).H = H;
