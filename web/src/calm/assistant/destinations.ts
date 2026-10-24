/**
 * The browser's half of assistant navigation (docs/api/assistant-navigation.md): the closed list
 * of places this app can actually open, per role and application, how each one opens, and how
 * to tell that it really did.
 *
 * The server plans; it never sends a URL or a case. A plan is applied only when its id is in this
 * registry, is offered right now, and the person has not moved on since asking. Nothing here
 * saves, submits, deletes or edits: every target is a hash route, a question card or an in-page
 * panel that its owning screen registers while it can really open it.
 */
import type { AssistNavigation } from "../../api/types.gen";
import { setLibraryDetached } from "../libraryContext";

/**
 * Every id this browser knows. `comments` (U4's officer-comments plan) is declared ahead of the
 * generated union so this file compiles before and after that union grows; it is a registered
 * panel, offered only while the native comments page registers it for the current application.
 */
export type DestinationId = AssistNavigation["destination"] | "comments";
export type NavRole = "applicant" | "reviewer";

/** What a destination needs from the current binding. */
export interface NavContext {
  role: NavRole | null;
  /** The application the assistant reads (null: none, an unsaved draft, or the library's None). */
  caseId: string | null;
}

/** The page as the browser shows it now (injected, so tests need no DOM). */
export interface PageProbe {
  /** Hash path, e.g. "/questions". */
  path(): string;
  /** The deck's current card key, when the deck shows one. */
  card(): string | null;
  /** A selector matches something on the page. */
  shows(selector: string): boolean;
}

interface RouteTarget {
  kind: "route";
  label: string;
  role?: NavRole;
  case?: boolean;
  href: string;
  /** The hash path that shows once it opened (prefix for the code library). */
  path: string;
  prefix?: boolean;
  /** A question card the deck must show before the open counts. */
  card?: string;
}

interface ActionTarget {
  kind: "action";
  label: string;
  role?: NavRole;
  case?: boolean;
  /** An in-page surface opened by an event the owning screen already listens to. */
  open(): void;
  /** What the page shows once it is open. */
  shows: string;
}

/** Offered only while the screen that owns it has registered an opener (see registerPanel). */
interface PanelTarget {
  kind: "panel";
  label: string;
  role?: NavRole;
  case?: boolean;
}

type Target = RouteTarget | ActionTarget | PanelTarget;

/** Window events the shell listens to; dispatching one is the only way these surfaces open. */
export const OPEN_APPLICATIONS = "cf:open-applications";
const OPEN_PALETTE = "cf:open-palette"; // CodePalette.tsx's event (kept in sync by its test below)

const route = (label: string, href: string, extra: Partial<RouteTarget> = {}): RouteTarget => ({ kind: "route", label, href, path: href.replace(/^#/, "").split("?")[0] || "/", ...extra });
const panel = (label: string, role?: NavRole): PanelTarget => ({ kind: "panel", label, role, case: true });
const question = (label: string, card: string): RouteTarget => route(label, `#/questions?focus=${encodeURIComponent(card)}`, { role: "applicant", case: true, card });
const fire = (name: string) => () => { window.dispatchEvent(new Event(name)); };

/**
 * Every server destination id and what opens it here. A `Record` over the generated union: a new
 * server id fails the typecheck until it gets a real target.
 */
export const DESTINATIONS: Record<DestinationId, Target> = {
  applications: { kind: "action", label: "Applications", role: "applicant", open: fire(OPEN_APPLICATIONS), shows: '.cf-app[data-list="open"], dialog.cf-nav-sheet[open]' },
  description: route("Describe", "#/", { role: "applicant" }),
  questions: route("Questions", "#/questions", { role: "applicant" }),
  review: route("Review", "#/review", { role: "applicant" }),
  application: route("Application", "#/application", { role: "applicant" }),
  "code-library": route("Code library", "#/code", { prefix: true }),
  "code-search": { kind: "action", label: "Look up code", open: fire(OPEN_PALETTE), shows: "dialog.cf-palette[open]" },
  references: route("Rules you chose", "#/references", { role: "applicant", case: true }),
  downloads: route("Download options", "#/application?download=options", { role: "applicant", case: true }),
  "officer-view": route("Officer view", "#/officer", { role: "applicant", case: true }),
  settings: route("Settings", "#/settings"),
  notifications: route("Notifications", "#/notifications"),
  accuracy: route("Accuracy report", "#/accuracy"),
  "question-authority": question("Reviewing jurisdiction", "authority"),
  "question-owner": question("Owner", "field-owner"),
  "question-representative": question("Representative", "field-representative"),
  "question-mailing-address": question("Mailing address", "field-mailingAddress"),
  "question-date": question("Request date", "field-date"),
  "question-scope": question("Application scope", "field-scope"),
  "question-permit": question("Permit number", "field-permit"),
  "question-site-address": question("Site address", "field-municipalAddress"),
  "question-legal-description": question("Legal description", "field-legalDescription"),
  "question-alternative": question("Proposed alternative", "field-alternative"),
  "question-rationale": question("Rationale", "field-rationale"),
  "question-risk": question("Risk assessment", "field-risk"),
  "question-mitigation": question("Mitigating measures", "field-mitigation"),
  "question-assumptions": question("Assumptions and limits", "field-assumptions"),
  "question-maintenance": question("Maintenance", "field-maintenance"),
  "question-qualifications": question("Qualifications", "field-qualifications"),
  "question-documents": question("Supporting documents", "section-d"),
  "review-queue": route("Review queue", "#/review", { role: "reviewer" }),
  "package-review": route("Review a PDF package", "#/review/package", { role: "reviewer" }),
  // The open file's steps and drawers: offered only once the review screen registers them.
  "review-overview": panel("Overview", "reviewer"),
  "review-missing": panel("Missing", "reviewer"),
  "review-checks": panel("Checks", "reviewer"),
  "review-decide": panel("Decide", "reviewer"),
  "review-application": panel("Submitted application", "reviewer"),
  "review-messages": panel("Officer notices", "reviewer"),
  "review-request": panel("Information request", "reviewer"),
  "review-versions": panel("Review versions", "reviewer"),
  "review-close-out": panel("Close-out", "reviewer"),
  // Opened only by the comments page's own registration (#/comments?case=<captured case>).
  comments: panel("Officer comments", "applicant"),
};

export const isDestination = (id: unknown): id is DestinationId => typeof id === "string" && Object.prototype.hasOwnProperty.call(DESTINATIONS, id);

export const destinationLabel = (id: DestinationId): string => DESTINATIONS[id].label;

// —— Registered panels ————————————————————————————————————————————————————————————————
//
// A screen registers an opener while its panel can really open (the review's steps, a comments
// page once it exists); unmounting removes it, so it is no longer offered. The opener gets the
// application the plan was asked about (never a model-supplied id) and resolves true only once
// the panel shows.

export type PanelOpener = (caseId: string | null) => boolean | Promise<boolean>;
const panels = new Map<DestinationId, { caseId: string | null; open: PanelOpener }>();
const panelListeners = new Set<() => void>();

/**
 * Offer `id` while mounted, for one application (`caseId`; null for case-free panels). Returns the
 * unregister function. Routes and actions cannot be registered.
 */
export function registerPanel(id: DestinationId, caseId: string | null, open: PanelOpener): () => void {
  if (DESTINATIONS[id].kind !== "panel") throw new Error(`${id} is not a panel`);
  const entry = { caseId, open };
  panels.set(id, entry);
  for (const l of panelListeners) l();
  return () => {
    if (panels.get(id) !== entry) return;
    panels.delete(id);
    for (const l of panelListeners) l();
  };
}

export function subscribePanels(l: () => void): () => void {
  panelListeners.add(l);
  return () => { panelListeners.delete(l); };
}

/** The ids to offer the server: only what this role can open right now, for this application. */
export function offeredDestinations(ctx: NavContext): DestinationId[] {
  if (!ctx.role) return [];
  return (Object.keys(DESTINATIONS) as DestinationId[]).filter((id) => {
    const t = DESTINATIONS[id];
    if (t.role && t.role !== ctx.role) return false;
    if (t.case && ctx.caseId === null) return false;
    if (t.kind === "panel") {
      const p = panels.get(id);
      return Boolean(p) && (!t.case || p!.caseId === ctx.caseId);
    }
    return true;
  }).slice(0, 64);
}

// —— Opening and verifying ——————————————————————————————————————————————————————————————

export interface OpenDeps extends PageProbe {
  go(href: string): void;
  /** Resolve after the app has had a chance to render (and redirect). */
  settle(): Promise<void>;
}

function opened(t: RouteTarget, page: PageProbe): boolean {
  const path = page.path();
  if (t.prefix ? !(path === t.path || path.startsWith(`${t.path}/`)) : path !== t.path) return false;
  return !t.card || page.card() === t.card;
}

/**
 * Open a destination the caller already checked is offered, for the captured application.
 * True only once it is actually showing: the route is the target's after the app had its chance
 * to redirect, the question card is the one on screen, the panel or dialog is open.
 */
export async function openDestination(id: DestinationId, caseId: string | null, deps: OpenDeps): Promise<boolean> {
  const t = DESTINATIONS[id];
  if (t.kind === "panel") {
    const p = panels.get(id);
    if (!p || (t.case && p.caseId !== caseId)) return false;
    try {
      return (await p.open(caseId)) === true;
    } catch {
      return false;
    }
  }
  if (t.kind === "action") {
    t.open();
    for (let i = 0; i < 20; i++) {
      await deps.settle();
      if (deps.shows(t.shows)) return true;
    }
    return false;
  }
  // Opening code from an application keeps that application, even after an earlier None visit.
  if (id === "code-library" && caseId) setLibraryDetached(false);
  deps.go(t.href);
  for (let i = 0; i < 30; i++) {
    await deps.settle();
    if (!opened(t, deps)) continue;
    // Still there a moment later: no redirect bounced it.
    await deps.settle();
    if (opened(t, deps)) return true;
  }
  return false;
}

// —— Where the person was, to go back ————————————————————————————————————————————————

export interface ReturnPoint {
  /** The hash to restore: the deck's card is pinned with ?focus= so it reopens exactly. */
  href: string;
  path: string;
  card: string | null;
  /** The element that had focus (by id), restored when it is still there. */
  focusId: string | null;
  label: string;
}

export function capturePlace(page: PageProbe & { hash(): string; focusId(): string | null }, label: string): ReturnPoint {
  const path = page.path();
  const card = path === "/questions" ? page.card() : null;
  const href = card ? `#/questions?focus=${encodeURIComponent(card)}` : page.hash() || "#/";
  return { href, path, card, focusId: page.focusId(), label };
}

/** Go back to a captured place; true once the same route (and card) shows again. */
export async function returnTo(place: ReturnPoint, deps: OpenDeps & { focus(id: string | null): void }): Promise<boolean> {
  deps.go(place.href);
  for (let i = 0; i < 30; i++) {
    await deps.settle();
    if (deps.path() !== place.path || (place.card && deps.card() !== place.card)) continue;
    deps.focus(place.focusId);
    return true;
  }
  return false;
}

// —— Manual-navigation generation ———————————————————————————————————————————————————————
//
// Any route change, card change or rebinding bumps it. A typed plan asked in an older generation
// is never applied: the person has moved on since they asked.

let generation = 0;
export const viewGeneration = (): number => generation;
export function bumpViewGeneration() {
  generation += 1;
}

export type PlanCheck = "apply" | "moved-on" | "not-offered";

/**
 * Whether a returned plan may be applied: the same binding (account, role, application, context)
 * as the request, no manual navigation since it was asked, and the id is offered right now.
 */
export function checkPlan(plan: { destination: unknown }, asked: { key: string; generation: number }, now: { key: string; generation: number; offered: readonly DestinationId[] }): PlanCheck {
  if (asked.key !== now.key || asked.generation !== now.generation) return "moved-on";
  if (!isDestination(plan.destination) || !now.offered.includes(plan.destination)) return "not-offered";
  return "apply";
}
