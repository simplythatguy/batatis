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
        "Every new building idea in Alberta starts the same way. It breaks a rule.",
        "Here's a real one. The City of Edmonton published it. A one-hour party wall instead of a two-hour firewall, for rowhouses with suites. And it's complete.",
        "And that firewall rule? Varied three hundred sixty-six times in six months. That's two a day.",
      ],
    },
    {
      id: "villain",
      name: "The send-back, and the reveal",
      suggested: "Omer Abdelwahab",
      slides: [
        {
          kind: "compare", id: "villain-diff", title: "Spot the difference",
          // Page 1 is identical in both; the two removed Section C rows are on page 2.
          left: {
            src: "/studio/img/form-complete-p2.png", label: "Complete",
            marks: [
              { rect: { x: 72, y: 717, w: 1077, h: 140 }, tone: "blue", label: "9.10.9.16.(4)" },
              { rect: { x: 72, y: 855, w: 1077, h: 140 }, tone: "blue", label: "9.10.19.5.(2)" },
            ],
          },
          right: {
            src: "/studio/img/form-incomplete-p2.png", label: "Two articles removed",
            marks: [{ rect: { x: 72, y: 717, w: 1077, h: 250 }, tone: "ink", label: "Missing" }],
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
        "Now watch. We quietly take out two articles: the smoke barrier and the linked smoke alarms. Can anyone spot it? Most people can't.",
        "But the officer can. Weeks later, it comes back. More information required.",
        "And every trip back costs about thirty-six hundred dollars. Mostly waiting.",
        "So today, we're introducing three things. An application writer.",
        "A code expert.",
        "And a completeness checker for officers.",
        "A writer, an expert, a checker. See where this is going? These aren't three tools. It's one app. We call it Batatis.",
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
        "So we just describe the rowhouse in plain words, and drop in that broken form. That's it.",
        "It reads both. The owner, the site, the city. Edmonton.",
        "Here are the rules, ranked. On top, the firewall being replaced. And look. The two articles we took out? Found. Isn't that cool?",
        "Then it asks only for what's still missing, one question at a time.",
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
        "And here's what we love. It knows where to stop. This needs an engineer, and it says so, and what the evidence has to cover.",
        "Section C comes straight from the 2023 code. Nothing's guessed.",
        "One click checks the whole thing before anyone else sees it.",
        "And there's the official form, filled in. Boom. Off to Edmonton.",
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
        "Now let's switch sides. Here's the safety codes officer in Edmonton, and it's already in the inbox.",
        "What's there, what's missing, and every citation links right to the code. It checks completeness, not compliance. The call is still the officer's.",
        "One decision, one clear message. The applicant fixes it and resends. No phone tag.",
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
        "So, does it really work? We tested sixty-four real Alberta cases, with the article numbers hidden.",
        "Plain search put the right article first twenty-six times. Batatis, fifty-four.",
        "Made-up articles shown to an applicant? Zero.",
        "A simulated first-timer using the official flowchart scored two out of ten. With Batatis, five point six.",
        "And it costs about sixty-one dollars an application, all in. Save one trip back in sixty, and it's paid for itself.",
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
        "Today we're live in Calgary and Edmonton. But we've already mapped four hundred thirty-five places to their office.",
        "A new office isn't new code. It's one data file. Better AI models only make us better. They won't keep an office's rules current, or earn an officer's trust. We will.",
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
        "Now, let's be straight about what we haven't proven. Our applicant scores are simulated. And ten times in sixty-four, the right article wasn't first.",
        "And no officer has reviewed a real Batatis application. Not yet.",
        "So here's the plan. One office, ninety days, right beside how they work today. Officers grade real files, and we measure every number again. In public.",
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
        "There's a Wayne Gretzky quote we love. He played right here, for the Oilers. I skate to where the puck is going to be, not where it has been.",
        "Well, the puck is going to new ideas. And every one of them breaks a rule.",
        "Batatis makes sure they show up complete. Thank you.",
      ],
    },
  ],
};
