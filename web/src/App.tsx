import { useEffect } from "react";
import { Application } from "./calm/Application";
import { CodeLibrary } from "./calm/CodeLibrary";
import { Comments } from "./calm/comments/Comments";
import { Deck } from "./calm/QuestionDeck";
import { Review } from "./calm/Review";
import { resolveRoute, type Screen } from "./calm/routes";
import { extraRoutes, isStandaloneRoute, useAuthRedirect } from "./calm/routes.extra";
import { updateSession, useSession } from "./calm/session";
import { Shell } from "./calm/Shell";
import { Start } from "./calm/Start";
import { useFocusParam, useRoute } from "./router";
import { Accuracy } from "./screens/Accuracy";
import { Officer } from "./screens/Officer";
import { SectionC } from "./screens/SectionC";
import { useCase } from "./store";

/** Store effects the calm screens ask for: the reading Start requested, and held PDF uploads. */
function CalmEffects() {
  const { phase, engineId, readDescription, uploadFiles } = useCase();
  const session = useSession();

  useEffect(() => {
    if (!session.readAfterStart || phase !== "case") return;
    updateSession({ readAfterStart: false });
    // Explicit user action: the applicant pressed Start.
    void readDescription();
  }, [session.readAfterStart, phase, readDescription]);

  // PDFs attached after the case exists upload in the save queue (intake reads them by id).
  useEffect(() => {
    if (!engineId || !session.held.length) return;
    void uploadFiles();
  }, [engineId, session.held, uploadFiles]);
  return null;
}

function normalHash(hash: string): string {
  const raw = hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  const q = new URLSearchParams(query).toString();
  return `#${path || "/"}${q ? `?${q}` : ""}`;
}

/** The four stages and the code library open in every state; the old screens need an application. */
const OPEN_WITHOUT_CASE: ReadonlySet<Screen> = new Set(["start", "questions", "review", "application", "code", "comments"]);

export function App() {
  const route = useRoute();
  // Signed-out visitors go to #/signin and new accounts to onboarding before any screen renders.
  const redirecting = useAuthRedirect(route);
  const { phase } = useCase();
  // Accounts, reviewer, settings and notification pages (routes.extra.tsx) come before the stages.
  const extra = extraRoutes(route);
  const calm = resolveRoute(route.path, route.params);
  const screen: Screen = phase === "case" || OPEN_WITHOUT_CASE.has(calm.screen) ? calm.screen : "start";
  const legacy = screen === "officer" || screen === "accuracy" || screen === "references";
  useFocusParam(legacy ? route : { path: route.path, params: new URLSearchParams() });

  // Legacy links (gap hrefs, old screens) are rewritten to the calm route they mean.
  // Rewrite only while the address bar still shows the route this render parsed:
  // a handler may already have navigated on (Start sets #/questions right after the role).
  const parsed = normalHash(`#${route.path}?${route.params.toString()}`);
  const target = screen === calm.screen ? calm.canonical : "#/";
  // Not for account pages, nor while the gate is moving the visitor, nor a `?case=` link the shell opens first.
  const keep = Boolean(extra) || redirecting || route.params.has("case");
  useEffect(() => {
    if (keep) return;
    if (parsed !== target && normalHash(location.hash) === parsed) location.replace(target);
  }, [target, parsed, keep]);

  if (redirecting) return null;
  if (extra && isStandaloneRoute(route)) return <>{extra}</>;
  if (extra) return <Shell active={screen} plain>{extra}</Shell>;

  let body;
  switch (screen) {
    case "questions":
      body = <Deck focus={calm.focus} codeFirst={calm.codeFirst} />;
      break;
    case "review":
      body = <Review />;
      break;
    case "application":
      body = <Application download={calm.download} />;
      break;
    case "officer":
      body = <div className="cf-legacy"><Officer /></div>;
      break;
    case "accuracy":
      body = <div className="cf-legacy"><Accuracy /></div>;
      break;
    case "references":
      body = <div className="cf-legacy"><SectionC /></div>;
      break;
    case "code":
      body = <CodeLibrary route={calm} />;
      break;
    case "comments":
      body = <Comments caseParam={route.params.get("case")} />;
      break;
    default:
      body = <Start />;
  }
  return (
    <Shell active={screen}>
      <CalmEffects />
      {body}
    </Shell>
  );
}
