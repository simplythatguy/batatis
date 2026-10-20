import { useEffect, useState } from "react";

export interface Route {
  path: string;
  params: URLSearchParams;
}

function parse(): Route {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  return { path, params: new URLSearchParams(query) };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => setRoute(parse());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

/** After navigation, move focus to `?focus=<element id>` so gap links land on the fix. */
export function useFocusParam(route: Route) {
  const target = route.params.get("focus");
  useEffect(() => {
    if (!target) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(target);
      if (!el) return;
      el.scrollIntoView({ block: "center" });
      el.focus({ preventScroll: true });
    }, 0);
    return () => window.clearTimeout(t);
  }, [target, route.path]);
}
