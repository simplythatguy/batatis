import type { Deck } from "./types";

// The pitch, told like a 2007 keynote. Spoken at 120 words a minute; timing.ts turns the words into each group's
// recording length. Sources and limits for every number: docs/studio/script.md.
export const deck: Deck = {
  title: "Batatis",
  team: ["Abdel Abdelwaly", "Omer Abdelwahab", "Alameen Elnur"],
  groups: [
    {
      id: "open",
      name: "Open: the real form",
      speaker: 0,
      slides: [
        { kind: "statement", id: "open-rule", text: "Every new idea\nbreaks a rule.", accent: "breaks a rule." },
        {
          kind: "image", id: "open-real", title: "Edmonton's own solution", src: "/studio/img/form-complete-p1.png",
          // Section C, first row: 9.10.11.2.(2), the firewall (rects from /studio/img/forms.json).
          focus: { x: 72, y: 1131, w: 1077, h: 313 },
        },
        {
          kind: "count", id: "open-varied", title: "That firewall rule", value: 366,
          label: "variances on Article 9.10.11.2. in Alberta, January to June 2026",
        },
      ],
      script: [
        "🙂 Every new building idea in Alberta starts the same way. ⏸️ It breaks... a... RULE.",
        "🙂 Here's a real solution from the City of Edmonton. It lets rowhouses with basement suites use a one-hour party wall instead of a two-hour firewall.",
        "😮 Alberta recorded three hundred sixty-six variances on that one firewall rule in six months. ⏸️ That's TWO a day.",
      ],
    },
    {
      id: "sendback",
      name: "The send-back",
      speaker: 1,
      slides: [
        {
          kind: "compare", id: "villain-diff", title: "Section C, deleted",
          // The one Section C row sits at the foot of page 1 (rects from /studio/img/forms.json).
          left: {
            src: "/studio/img/form-complete-p1.png", label: "Complete",
            marks: [{ rect: { x: 72, y: 1316, w: 1077, h: 129 }, tone: "blue", label: "9.10.11.2.(2)" }],
          },
          right: {
            src: "/studio/img/form-incomplete-p1.png", label: "Section C removed",
            marks: [{ rect: { x: 72, y: 1316, w: 1077, h: 129 }, tone: "ink", label: "Missing" }],
          },
        },
        { kind: "statement", id: "villain-back", text: "More information\nrequired.", accent: "required.", sub: "Weeks later." },
        { kind: "count", id: "villain-cost", value: 3600, prefix: "$", label: "estimated cost of one extra round trip, in Canadian dollars, mostly waiting" },
      ],
      script: [
        "😏 A builder fills in this form. Section C names the rule you're changing. ⏸️ Now watch. We delete it. 🤔 Would a first-time builder know what goes there?",
        "😬 The officer would. WEEKS later, the application comes back.",
        "😬 Every trip back costs about thirty-six hundred dollars, mostly waiting.",
      ],
    },
    {
      id: "reveal",
      name: "The reveal",
      speaker: 0,
      slides: [
        { kind: "statement", id: "three-writer", text: "An application\nwriter." },
        { kind: "statement", id: "three-expert", text: "A code\nexpert." },
        { kind: "statement", id: "three-checker", text: "A completeness\nchecker.", sub: "For officers." },
        { kind: "logo", id: "three-one", line: "One app." },
      ],
      script: [
        "🙂 So we built THREE things. An application writer.",
        "🙂 A code expert.",
        "🙂 And a completeness checker for officers.",
        "😏 A writer, an expert, a checker. 🤔 See where this is going? ⏸️ 🔥 It's... ONE... app. We call it Batatis.",
      ],
    },
    {
      id: "apply-in",
      name: "Applicant: intake and rules",
      speaker: 2,
      slides: [
        { kind: "clip", id: "apply-start", title: "Describe it. Drop it in.", src: "/studio/clips/c01-start.mp4", from: 1.8, to: 10.6, rate: 1.25 },
        { kind: "clip", id: "apply-read", title: "It reads both", src: "/studio/clips/c02-understood.mp4", from: 0.6, to: 11.0, rate: 1.6 },
        { kind: "clip", id: "apply-rules", title: "The right rules, ranked", src: "/studio/clips/c03-rules.mp4", from: 0.4, to: 18.2, rate: 1.55 },
        { kind: "clip", id: "apply-ask", title: "Only what's missing", src: "/studio/clips/c04-questions.mp4", from: 0.5, to: 9.0, rate: 1.3 },
      ],
      script: [
        "🙂 We describe the rowhouse in plain words and attach the form without Section C.",
        "🙂 Batatis reads both. It finds the site in Edmonton and every safety measure.",
        "🙂 First, it names the rule this design breaks. ⏸️ 😮 EXACTLY the one we deleted. 😄 Isn't that COOL? Then come the rules it still follows.",
        "🙂 Next, it asks only what's still missing, one question at a time.",
      ],
    },
    {
      id: "apply-out",
      name: "Applicant: engineer to form",
      speaker: 0,
      slides: [
        { kind: "clip", id: "apply-stop", title: "It doesn't guess", src: "/studio/clips/c05-engineer.mp4", from: 0.4, to: 16.5, rate: 1.35 },
        { kind: "clip", id: "apply-c", title: "Section C, looked up", src: "/studio/clips/c06-section-c.mp4", from: 3.4, to: 15.5, rate: 1.15 },
        { kind: "clip", id: "apply-check", title: "Checked before it's sent", src: "/studio/clips/c07-check.mp4", from: 3.6, to: 18.8, rate: 1.5 },
        { kind: "clip", id: "apply-form", title: "The official form", src: "/studio/clips/c08-form.mp4", from: 5.8, to: 18.0, rate: 1.6 },
      ],
      script: [
        "💪 When it isn't sure, it doesn't GUESS. It flags the engineer question for the officer and lists what the proof must cover.",
        "💪 Here's Section C, rebuilt from the 2023 Alberta Edition, second printing. ⏸️ Same rule, same objectives, same function as the City's.",
        "🙂 One click checks the whole application. It spots a missing study, we add the City's report, and now it's ready.",
        "😄 And there's the official Safety Codes form, filled in. ⏸️ 🔥 BOOM. Off to Edmonton.",
      ],
    },
    {
      id: "officer",
      name: "Officer",
      speaker: 2,
      slides: [
        { kind: "clip", id: "officer-queue", title: "The officer's inbox", src: "/studio/clips/c09-queue.mp4", from: 1.2, to: 9.6, rate: 1.5 },
        { kind: "clip", id: "officer-review", title: "What's missing, at a glance", src: "/studio/clips/c10-officer-review.mp4", from: 0.3, to: 15.5, rate: 1.09 },
        { kind: "clip", id: "officer-decide", title: "One clear message", src: "/studio/clips/c11-decide.mp4", from: 0.3, to: 11.5, rate: 1.5 },
      ],
      script: [
        "🙂 Now the other side. It lands in the Edmonton officer's inbox.",
        "😌 The officer sees what's done and what's missing. Batatis checks completeness; safety is still the officer's call. ⏸️ Each item shows its page and links the exact code.",
        "🙂 The officer sends it back with one clear message. The builder fixes it and resends.",
      ],
    },
    {
      id: "proof",
      name: "Proof",
      speaker: 1,
      slides: [
        { kind: "statement", id: "proof-q", text: "Does it\nreally work?" },
        {
          kind: "bars", id: "proof-rank", title: "Right rule, first", max: 64, unit: "of 64",
          bars: [
            { label: "Plain search", value: 26 },
            { label: "Batatis", value: 54, highlight: true },
          ],
          note: "64 real Alberta variances, appeals and rulings. Article numbers removed from the descriptions.",
        },
        { kind: "count", id: "proof-zero", value: 0, label: "made-up rules shown to an applicant, same 64 cases" },
        {
          kind: "bars", id: "proof-novice", title: "First-time applicants", max: 10, unit: "/ 10",
          bars: [
            { label: "Official flowchart", value: 2.0 },
            { label: "Batatis", value: 5.6, highlight: true },
          ],
          note: "Simulated applicants, not people. Blind model grader, one run, same 64 cases.",
        },
        { kind: "count", id: "proof-cost", value: 1.23, prefix: "$", decimals: 2, label: "of AI per application, in Canadian dollars, averaged over 3 metered runs. The officer's review uses none." }
      ],
      script: [
        "🤔 Does it REALLY work? We tested sixty-four real Alberta cases, variances and appeals, rule numbers hidden.",
        "💪 Plain search ranked the right rule first TWENTY-SIX times. ⏸️ Batatis did it... FIFTY-FOUR... times.",
        "💪 And it never showed a made-up rule. ⏸️ ZERO.",
        "😌 Simulated first-time builders scored two out of ten with the official flowchart. With Batatis, FIVE POINT SIX.",
        "💪 The AI for one application costs about... a DOLLAR twenty. The officer's review is free.",
      ],
    },
    {
      id: "scale",
      name: "Ready to scale",
      speaker: 2,
      slides: [
        {
          kind: "dots", id: "scale-places", title: "Live in two cities", total: 435, lit: 2,
          label: "The rest of Alberta, in progress", litLabel: "Calgary, Edmonton",
        },
        {
          kind: "flow", id: "scale-file", title: "Adding a city",
          steps: [
            { label: "New city" },
            { label: "Add one file", sub: "its forms and steps" },
            { label: "Same app", sub: "no new code" },
          ],
          active: [1],
        },
      ],
      script: [
        "🙂 Right now Batatis only works in Calgary and Edmonton. We're working on adding the rest of Alberta.",
        "🙂 Adding a new city is pretty easy. We just add a file with that city's forms and steps. ⏸️ No new code.",
      ],
    },
    {
      id: "honest",
      name: "What we haven't proven",
      speaker: 1,
      slides: [
        { kind: "statement", id: "honest-gaps", text: "What we\nhaven't proven.", accent: "haven't proven." },
        { kind: "count", id: "honest-officers", value: 0, label: "real Batatis applications reviewed by an officer, so far" },
        {
          kind: "flow", id: "honest-plan", title: "How we'll prove it",
          steps: [
            { label: "Officers and applicants", sub: "their feedback" },
            { label: "Real-world data", sub: "how Batatis performs" },
            { label: "Larger scale", sub: "more offices" },
          ],
          active: [0, 1, 2],
        },
      ],
      script: [
        "😌 Now, what we HAVEN'T proven. Our first-time builder scores are simulated, and ten times out of sixty-four the right rule wasn't first.",
        "😌 And no officer has reviewed a real Batatis application... YET.",
        "💪 Once we can scale, phase one is feedback from safety codes officers and applicants, to see how Batatis performs on real-world data, at scale.",
      ],
    },
    {
      id: "close",
      name: "Close",
      speaker: 0,
      slides: [
        { kind: "statement", id: "close-complete", text: "Complete the\nfirst time.", accent: "Complete" },
        { kind: "statement", id: "close-once", text: "Reviewed once.", accent: "once." },
        { kind: "statement", id: "close-thanks", text: "Thank you." },
      ],
      script: [
        "🙂 So that's Batatis. Builders send a complete application the first time.",
        "🙂 Officers review it once, instead of sending it back.",
        "🙂 Thank you.",
      ],
    },
  ],
};
