import { useEffect, useState } from "react";

export interface Route {
  path: string;
  params: URLSearchParams;
}

function parse(): Route {
  const raw = location.hash.replace(/^#/, "") || "/describe";
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

/** After navigation, move focus to `?focus=<element id>` so gap links land on the fix.
 *  Collapsed rows (`<details>`) around the target open first. */
export function useFocusParam(route: Route) {
  const target = route.params.get("focus");
  useEffect(() => {
    if (!target) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(target);
      if (!el) return;
      for (let d = el.parentElement?.closest("details"); d; d = d.parentElement?.closest("details")) d.open = true;
      el.scrollIntoView({ block: "center" });
      el.focus({ preventScroll: true });
    }, 0);
    return () => window.clearTimeout(t);
  }, [target, route.path]);
}
