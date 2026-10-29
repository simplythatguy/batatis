import { type Deck, type Group, WORDS_PER_MINUTE } from "./types";

/** Logo intro and outro around the recorded groups, in ms. */
export const INTRO_MS = 4200;
export const OUTRO_MS = 4000;

export function words(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

/** How long one script segment takes at the studio pace, in ms. */
export function segmentMs(text: string): number {
  return Math.round((words(text) / WORDS_PER_MINUTE) * 60_000);
}

/** A group's recording length: its words at 120 wpm plus a one-second breath. */
export function targetMs(group: Group): number {
  return group.script.reduce((sum, s) => sum + segmentMs(s), 0) + 1000;
}

export function deckMs(deck: Deck): number {
  return INTRO_MS + OUTRO_MS + deck.groups.reduce((sum, g) => sum + targetMs(g), 0);
}

export function clock(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
