/**
 * Calm-flow routes over the existing hash router.
 * Store gap hrefs still point at the old screens; `resolveRoute` translates them,
 * so every "Fix" or "Answer" link lands on the matching question card.
 */

export type Screen = "start" | "questions" | "review" | "application" | "officer" | "accuracy" | "references" | "code" | "comments";

export interface CalmRoute {
  screen: Screen;
  /** Deck item key for `questions`, or `authority` on Start. */
  focus: string | null;
  /** `#/code-check` without a focus: show code-check cards first. */
  codeFirst: boolean;
  /** Application: open the download panel ("options") or start a draft PDF ("draft"). */
  download: "" | "options" | "draft";
  /** Code library: the open article (`#/code/<id>`) and the relevance filter. */
  article: string | null;
  filter: "" | "all" | "attention" | "maybe";
  /** The calm hash for this route. Differs from the current hash when it was a legacy link. */
  canonical: string;
}

export const STAGES: { screen: Screen; n: string; label: string }[] = [
  { screen: "start", n: "01", label: "Describe" },
  { screen: "questions", n: "02", label: "Questions" },
  { screen: "review", n: "03", label: "Review" },
  { screen: "application", n: "04", label: "Application" },
];

/** The last stage page this tab showed, so pages off the stages (comments) can go back to it. */
let lastStage = "#/questions";
export function rememberStage(hash: string) {
  lastStage = hash || "#/";
}
export function lastStageHash(): string {
  return lastStage;
}

/** Legacy focus ids map onto deck keys. Professional fields live on the Section D card. */
export function deckFocus(focus: string | null): string | null {
  if (!focus) return null;
  if (focus.startsWith("prof-")) return "section-d";
  return focus;
}

function build(screen: Screen, focus: string | null = null, extra: Partial<CalmRoute> = {}): CalmRoute {
  const base = screen === "start" ? "#/" : screen === "code" && extra.article ? `#/code/${encodeURIComponent(extra.article)}` : `#/${screen}`;
  const query = new URLSearchParams();
  if (focus) query.set("focus", focus);
  if (extra.codeFirst) query.set("first", "code");
  if (extra.download) query.set("download", extra.download);
  if (extra.filter) query.set("filter", extra.filter);
  const q = query.toString();
  return { screen, focus, codeFirst: false, download: "", article: null, filter: "", ...extra, canonical: q ? `${base}?${q}` : base };
}

/** `#/code/<article id>` for links. Ids keep their dots and brackets readable after decoding. */
export function codeHref(articleId?: string | null, filter?: CalmRoute["filter"]): string {
  return build("code", null, { article: articleId ?? null, filter: filter ?? "" }).canonical;
}

const FILTERS = new Set(["all", "attention", "maybe"]);

export function resolveRoute(path: string, params: URLSearchParams): CalmRoute {
  const focus = deckFocus(params.get("focus"));
  if (path === "/code" || path.startsWith("/code/")) {
    let article: string | null = null;
    try {
      article = decodeURIComponent(path.slice("/code/".length)) || null;
    } catch {
      article = null;
    }
    const f = params.get("filter") ?? "";
    return build("code", null, { article, filter: FILTERS.has(f) ? (f as CalmRoute["filter"]) : "" });
  }
  switch (path) {
    case "":
    case "/":
    case "/start":
      return build("start");
    case "/describe":
      // Describe held the authority picker, captured facts and question chips; each is a card now.
      if (focus && (focus === "authority" || focus.startsWith("fact-") || focus.startsWith("q-"))) return build("questions", focus);
      return build("start");
    case "/questions":
      return build("questions", focus, { codeFirst: params.get("first") === "code" });
    case "/code-check":
      return focus ? build("questions", focus) : build("questions", null, { codeFirst: true });
    case "/review":
      return build("review", focus?.startsWith("draft:") ? focus : null);
    case "/application": {
      const tab = params.get("tab");
      // Without a field, a tab means its end: Section D's "Previous" lands on the last process card.
      if (tab) return build("questions", focus ?? (tab === "D" ? "section-d" : tab === "alt" ? "field-qualifications" : null));
      if (params.get("review") === "1") return build("review");
      const download = params.get("download");
      if (download === "draft") return build("application", null, { download: "draft" });
      if (download) return build("application", null, { download: "options" });
      return build("application");
    }
    case "/officer":
      return build("officer");
    case "/comments":
      return build("comments");
    case "/accuracy":
      return build("accuracy");
    case "/section-c":
    case "/references":
      return build("references");
    default:
      return build("start");
  }
}

/** Translate any app href (legacy or calm) into the calm hash it should open. */
export function calmHref(href: string): string {
  const raw = href.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  return resolveRoute(path, new URLSearchParams(query)).canonical;
}
