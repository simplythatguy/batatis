// The stage: paints the deck on a 1920×1080 canvas, live in the studio and frame-exact in the export.

import type { Deck, TakeMedia } from "../types";
import { preload as preloadAssets } from "./assets";
import { exportVideo as renderVideo } from "./export";
import { makeStage, type Stage } from "./stage";

export { STAGE_W, STAGE_H, type Stage } from "./stage";

/** Paints `deck` into `canvas` (backing store 1920×1080, CSS-scaled by the caller) on its own rAF loop. */
export function createStage(canvas: HTMLCanvasElement, deck: Deck): Stage {
  return makeStage(canvas, deck);
}

/** Loads fonts, images and clips (as blob URLs, for exact seeking). Call before recording or exporting. */
export function preload(deck: Deck, onProgress?: (fraction: number) => void): Promise<void> {
  return preloadAssets(deck, onProgress);
}

/** Real-time render of the whole video: intro card (INTRO_MS), every group that has a take in deck order (slides switched at the take's cues, the take's video as the camera tile, the take's audio as the only audio), outro card (OUTRO_MS). */
export function exportVideo(opts: {
  deck: Deck;
  takes: Record<string, TakeMedia>;
  onProgress?: (fraction: number, label: string) => void;
  signal?: AbortSignal;
}): Promise<{ blob: Blob; mime: string }> {
  return renderVideo(opts);
}
