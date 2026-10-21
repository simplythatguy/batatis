import { useEffect } from "react";
import { engine, EngineError } from "./api/client";
import { Application } from "./calm/Application";
import { CodeLibrary } from "./calm/CodeLibrary";
import { Deck } from "./calm/QuestionDeck";
import { Review } from "./calm/Review";
import { resolveRoute } from "./calm/routes";
import { getSession, updateSession, useSession } from "./calm/session";
import { Shell } from "./calm/Shell";
import { Start } from "./calm/Start";
import { useFocusParam, useRoute } from "./router";
import { uploadMessage } from "./rules";
import { Accuracy } from "./screens/Accuracy";
import { Officer } from "./screens/Officer";
import { SectionC } from "./screens/SectionC";
import { useCase } from "./store";
// U2 test wiring (replace with U1's App): accounts, reviewer and settings routes plus the auth gate.
import { extraRoutes, isStandaloneRoute, useAuthRedirect } from "./calm/routes.extra";

/** Store effects the calm screens ask for: the check Start requested, and held PDF uploads. */
function CalmEffects() {
  const { c, phase, engineId, requestCheck, dispatch } = useCase();
  const session = useSession();

  useEffect(() => {
    if (!session.checkAfterStart || phase !== "case") return;
    updateSession({ checkAfterStart: false });
    // Explicit user action: the applicant pressed Start.
    void requestCheck();
  }, [session.checkAfterStart, phase, c, requestCheck]);

  useEffect(() => {
    if (!engineId || !session.held.length) return;
    const held = getSession().held;
    updateSession((s) => ({ held: [], uploading: [...s.uploading, ...held.map((h) => h.id)] }));
    for (const { id, file } of held) {
      if (!c.files.some((f) => f.id === id)) {
        updateSession((s) => ({ uploading: s.uploading.filter((x) => x !== id) }));
        continue;
      }
      engine
        .upload(engineId, file)
        .then(() => dispatch({ type: "setFileResult", id, error: null, read: true }))
        .catch((e: unknown) => {
          const status = e instanceof EngineError ? e.status : 0;
          const detail = e instanceof EngineError ? e.detail : String(e);
          dispatch({ type: "setFileResult", id, error: uploadMessage(status, detail), unreachable: status === 0 });
        })
        .finally(() => updateSession((s) => ({ uploading: s.uploading.filter((x) => x !== id) })));
    }
  }, [engineId, session.held, c.files, dispatch]);
  return null;
}

function normalHash(hash: string): string {
  const raw = hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  const q = new URLSearchParams(query).toString();
  return `#${path || "/"}${q ? `?${q}` : ""}`;
}

export function App() {
  const route = useRoute();
  const redirecting = useAuthRedirect(route); // U2 test wiring
  const extra = extraRoutes(route); // U2 test wiring
  const { phase } = useCase();
  const calm = resolveRoute(route.path, route.params);
  const screen = phase === "case" ? calm.screen : "start";
  const legacy = screen === "officer" || screen === "accuracy" || screen === "references";
  useFocusParam(legacy ? route : { path: route.path, params: new URLSearchParams() });

  // Legacy links (gap hrefs, old screens) are rewritten to the calm route they mean.
  // Rewrite only while the address bar still shows the route this render parsed:
  // a handler may already have navigated on (Start sets #/questions right after the role).
  const parsed = normalHash(`#${route.path}?${route.params.toString()}`);
  useEffect(() => {
    if (extra) return; // U2 test wiring: U2 routes are not legacy links
    const target = phase === "case" ? calm.canonical : "#/";
    if (parsed !== target && normalHash(location.hash) === parsed) location.replace(target);
  }, [calm.canonical, phase, parsed, extra]);

  // U2 test wiring
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
    default:
      body = <Start focus={calm.focus} />;
  }
  return (
    <Shell active={screen}>
      <CalmEffects />
      {body}
    </Shell>
  );
}
