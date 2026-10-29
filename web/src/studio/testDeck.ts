// A small deck that uses every slide kind with real assets only: the real form pages and a real app recording
// (public/studio/test/app.mp4, cut from docs/demo/calgary-edmonton-only-20261029.webm). For the stage harness and tests.

import type { Deck } from "./types";

const APP = "/studio/test/app.mp4";
const IMG = "/studio/img";

export const testDeck: Deck = {
  title: "Batatis test deck",
  team: ["Abdel Abdelwaly", "Omer Abdelwahab", "Alameen Elnur"],
  groups: [
    {
      id: "test-open",
      name: "Opening",
      slides: [
        { kind: "statement", id: "t-rule", text: "Every new idea\nbreaks a rule.", accent: "breaks a rule.", sub: "Weeks later." },
        { kind: "logo", id: "t-logo", line: "One app." },
        { kind: "clip", id: "t-clip", title: "Describe it. Drop it in.", src: APP, from: 0, to: 6 },
        { kind: "clip", id: "t-clip2", title: "It reads both", src: APP, from: 4 },
        { kind: "image", id: "t-form", title: "Edmonton's own application", src: `${IMG}/form-complete-p1.png`, focus: { x: 72, y: 1131, w: 1077, h: 313 } },
        {
          kind: "compare", id: "t-compare", title: "Spot the difference",
          left: {
            src: `${IMG}/form-complete-p2.png`, label: "Complete",
            marks: [
              { rect: { x: 72, y: 717, w: 1077, h: 140 }, tone: "blue", label: "9.10.9.16.(4)" },
              { rect: { x: 72, y: 855, w: 1077, h: 140 }, tone: "blue", label: "9.10.19.5.(2)" },
            ],
          },
          right: { src: `${IMG}/form-incomplete-p2.png`, label: "Two articles removed", marks: [{ rect: { x: 72, y: 717, w: 1077, h: 250 }, tone: "ink", label: "Missing" }] },
        },
      ],
      script: [
        "Every new building idea in Alberta starts the same way.",
        "One app.",
        "Describe it and drop it in.",
        "It reads both.",
        "Here's a real one.",
        "Spot the difference.",
      ],
    },
    {
      id: "test-results",
      name: "Results",
      slides: [
        {
          kind: "bars", id: "t-bars", title: "Right article, first", max: 64, unit: "of 64",
          bars: [{ label: "Plain search", value: 26 }, { label: "Batatis", value: 54, highlight: true }],
          note: "64 real Alberta variances, appeals and rulings.",
        },
        { kind: "count", id: "t-count", title: "Records matched", value: 54, of: 64, label: "real Alberta variance records" },
        { kind: "count", id: "t-count2", value: 3600, prefix: "$", label: "estimated cost of one extra round trip, mostly waiting" },
        { kind: "dots", id: "t-dots", title: "Every place, mapped", total: 435, lit: 2, label: "435 places", litLabel: "Live today" },
        {
          kind: "flow", id: "t-flow", title: "A new office is a file",
          steps: [{ label: "13,743 provisions", sub: "one database" }, { label: "One office", sub: "one data file" }, { label: "Same app" }],
          active: [1],
        },
      ],
      script: [
        "Plain search, twenty-six. Batatis, fifty-four.",
        "Fifty-four of sixty-four.",
        "Thirty-six hundred dollars.",
        "Four hundred thirty-five places.",
        "A new office is a file.",
      ],
    },
  ],
};
