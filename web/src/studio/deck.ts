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
      suggested: "Abdel Abdelwaly",
      slides: [
        { kind: "statement", id: "open-rule", text: "Every new idea\nbreaks a rule.", accent: "breaks a rule." },
        {
          kind: "image", id: "open-real", title: "Edmonton's own application", src: "/studio/img/form-complete-p1.png",
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
        "🙂 Here's a real one from Edmonton. It lets rowhouses with suites use a one-hour party wall instead of a two-hour firewall.",
        "😮 Alberta recorded three hundred sixty-six variances against that firewall rule in six months. ⏸️ That's TWO a day.",
      ],
    },
    {
      id: "villain",
      name: "The send-back, and the reveal",
      suggested: "Omer Abdelwahab",
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
        { kind: "count", id: "villain-cost", value: 3600, prefix: "$", label: "estimated cost of one extra round trip, mostly waiting" },
        { kind: "statement", id: "three-writer", text: "An application\nwriter." },
        { kind: "statement", id: "three-expert", text: "A code\nexpert." },
        { kind: "statement", id: "three-checker", text: "A completeness\nchecker.", sub: "For officers." },
        { kind: "logo", id: "three-one", line: "One app." },
      ],
      script: [
        "😏 NOW watch. We delete Section C, the rule this design varies and why. 🤔 Would a first-time builder know what goes there? ⏸️ Most DON'T.",
        "😬 But the officer does, and WEEKS later the application comes back.",
        "😬 Every trip back costs about thirty-six hundred dollars, and most of that is just... WAITING.",
        "🙂 So today, we're introducing THREE things. An application writer.",
        "🙂 A code expert.",
        "🙂 And a completeness checker for officers.",
        "😏 A writer, an expert, a checker. 🤔 See where this is going? ⏸️ 🔥 It's... ONE... app, and we call it Batatis.",
      ],
    },
    {
      id: "apply-in",
      name: "Applicant: intake and rules",
      suggested: "Alameen Elnur",
      slides: [
        { kind: "clip", id: "apply-start", title: "Describe it. Drop it in.", src: "/studio/clips/c01-start.mp4" },
        { kind: "clip", id: "apply-read", title: "It reads both", src: "/studio/clips/c02-understood.mp4" },
        { kind: "clip", id: "apply-rules", title: "The right rules, ranked", src: "/studio/clips/c03-rules.mp4" },
        { kind: "clip", id: "apply-ask", title: "Only what's missing", src: "/studio/clips/c04-questions.mp4" },
      ],
      script: [
        "🙂 We describe the rowhouse in plain words and drop in the broken form.",
        "🙂 It reads both and finds the owner, the site and the city.",
        "🙂 Here are the rules it found, ranked. ⏸️ 😮 At the TOP... the exact rule we deleted. 😄 Isn't that COOL? Ten runs out of ten.",
        "🙂 Then it asks ONLY for what's still missing, one question at a time.",
      ],
    },
    {
      id: "apply-out",
      name: "Applicant: engineer to form",
      suggested: "Abdel Abdelwaly",
      slides: [
        { kind: "clip", id: "apply-stop", title: "It knows where to stop", src: "/studio/clips/c05-engineer.mp4" },
        { kind: "clip", id: "apply-c", title: "Section C, by lookup", src: "/studio/clips/c06-section-c.mp4" },
        { kind: "clip", id: "apply-check", title: "Checked before it's sent", src: "/studio/clips/c07-check.mp4" },
        { kind: "clip", id: "apply-form", title: "The official form", src: "/studio/clips/c08-form.mp4" },
      ],
      script: [
        "💪 It also knows where to STOP. This project needs an engineer, and Batatis lists what the evidence must cover.",
        "💪 Here's Section C, straight from the 2023 code. ⏸️ Same article, same objectives, same function as the City's.",
        "🙂 One click checks the application before anyone else sees it.",
        "😄 And there's the official form, filled in. ⏸️ 🔥 BOOM. It goes to Edmonton.",
      ],
    },
    {
      id: "officer",
      name: "Officer",
      suggested: "Alameen Elnur",
      slides: [
        { kind: "clip", id: "officer-queue", title: "The officer's inbox", src: "/studio/clips/c09-queue.mp4" },
        { kind: "clip", id: "officer-review", title: "Complete at a glance", src: "/studio/clips/c10-officer-review.mp4" },
        { kind: "clip", id: "officer-decide", title: "Decide. Message once.", src: "/studio/clips/c11-decide.mp4" },
      ],
      script: [
        "🙂 Now let's switch sides. The application is in the Edmonton officer's inbox.",
        "😌 The officer sees what's there and what's missing, with every citation linked to the code. Batatis checks completeness, and the compliance call stays with the officer.",
        "🙂 The officer sends one clear message, and the applicant fixes it and resends.",
      ],
    },
    {
      id: "proof",
      name: "Proof",
      suggested: "Omer Abdelwahab",
      slides: [
        { kind: "statement", id: "proof-q", text: "Does it\nreally work?" },
        {
          kind: "bars", id: "proof-rank", title: "Right article, first", max: 64, unit: "of 64",
          bars: [
            { label: "Plain search", value: 26 },
            { label: "Batatis", value: 54, highlight: true },
          ],
          note: "64 real Alberta variances, appeals and rulings. Article numbers removed from the descriptions.",
        },
        { kind: "count", id: "proof-zero", value: 0, label: "made-up articles shown to an applicant, same 64 cases" },
        {
          kind: "bars", id: "proof-novice", title: "First-time applicants", max: 10, unit: "/ 10",
          bars: [
            { label: "Official flowchart", value: 2.0 },
            { label: "Batatis", value: 5.6, highlight: true },
          ],
          note: "Simulated applicants, not people. Blind model grader, one run, same 64 cases.",
        },
        {
          kind: "count", id: "proof-cost", value: 61, prefix: "$",
          label: "estimated all-in cost per application. Pays for itself if 1 in 60 custom applications skips a trip back.",
        },
      ],
      script: [
        "🤔 Does it REALLY work? We tested sixty-four real Alberta cases with the article numbers hidden.",
        "💪 Plain search put the right article first TWENTY-SIX times. ⏸️ Batatis put it first... FIFTY-FOUR... times.",
        "💪 And it showed applicants... ZERO... made-up articles.",
        "😌 A simulated first-time applicant scored two out of ten with the official flowchart, and FIVE POINT SIX with Batatis.",
        "💪 It costs about sixty-one dollars an application, so saving one trip back in sixty pays for it.",
      ],
    },
    {
      id: "scale",
      name: "Ready to scale",
      suggested: "Alameen Elnur",
      slides: [
        {
          kind: "dots", id: "scale-places", title: "Every place, mapped", total: 435, lit: 2,
          label: "435 places mapped to the office that reviews them", litLabel: "Live today: Calgary, Edmonton",
        },
        {
          kind: "flow", id: "scale-file", title: "A new office is a file",
          steps: [
            { label: "13,743 provisions", sub: "NBC(AE) 2023, one database" },
            { label: "One office", sub: "one checked data file" },
            { label: "Same app", sub: "no code changes" },
          ],
          active: [1],
        },
      ],
      script: [
        "🙂 Today we're live in Calgary and Edmonton, and we've mapped four hundred thirty-five places to their office.",
        "💪 Adding an office takes one data file, NOT new code. Better AI models make Batatis better, but they won't keep each office's rules up to date or earn an officer's trust. ⏸️ We... WILL.",
      ],
    },
    {
      id: "honest",
      name: "What we haven't proven",
      suggested: "Omer Abdelwahab",
      slides: [
        { kind: "statement", id: "honest-gaps", text: "What we\nhaven't proven.", accent: "haven't proven." },
        { kind: "count", id: "honest-officers", value: 0, label: "real Batatis applications reviewed by an officer, so far" },
        {
          kind: "flow", id: "honest-plan", title: "How we'll prove it",
          steps: [
            { label: "One office", sub: "ninety days, side by side" },
            { label: "Real files, graded", sub: "every officer correction" },
            { label: "Every number, again", sub: "measured, then published" },
          ],
          active: [0, 1, 2],
        },
      ],
      script: [
        "😌 Here's what we HAVEN'T proven. Our applicant scores come from simulated applicants, and in ten of sixty-four cases the right article wasn't first.",
        "😌 And no officer has reviewed a real Batatis application... YET.",
        "💪 So we'll run a ninety-day pilot with one office alongside its current process. Officers will grade real files, and we'll measure EVERY number again and publish it.",
      ],
    },
    {
      id: "close",
      name: "Close",
      suggested: "Abdel Abdelwaly",
      slides: [
        { kind: "statement", id: "close-quote", text: "“I skate to where\nthe puck is going to be.”", sub: "Wayne Gretzky, Edmonton Oilers" },
        { kind: "statement", id: "close-ideas", text: "New ideas\nare coming.", accent: "coming." },
        { kind: "statement", id: "close-line", text: "Complete before\nit's ever sent.", accent: "Complete" },
      ],
      script: [
        "🙂 There's a Wayne Gretzky quote we love. ⏸️ I skate to where the puck is going to be, not where it has been.",
        "😌 The puck is going to new ideas, and every... single... one of them breaks a rule.",
        "🔥 Batatis makes sure they show up... COMPLETE. ⏸️ 🙂 Thank you.",
      ],
    },
  ],
};
