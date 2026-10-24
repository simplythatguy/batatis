/**
 * Whether engine fetches carry the session cookie (`credentials: "include"`).
 *
 * A credentialed cross-origin request is rejected by the browser unless the engine answers with
 * Access-Control-Allow-Credentials. Engines before api/accounts-review do not, so sending
 * credentials unconditionally would break every call. One probe decides:
 *   - same-origin base ("/api" behind the proxy): always "include" (harmless without a session);
 *   - cross-origin base: "include" once a credentialed GET /auth/me returns any HTTP response
 *     (200, 401 or 404 all prove the browser accepted it); otherwise "same-origin" (anonymous).
 */
import { accountRequestSignal } from "./requestLifetime";

export const ENGINE_BASE: string = import.meta.env?.VITE_ENGINE_URL ?? import.meta.env?.VITE_API_BASE ?? "/api";

const sameOrigin = (() => {
  try {
    return typeof location !== "undefined" && new URL(ENGINE_BASE, location.href).origin === location.origin;
  } catch {
    return true;
  }
})();

let mode: RequestCredentials = sameOrigin ? "include" : "same-origin";

export function credentialsMode(): RequestCredentials {
  return mode;
}

/** For tests and the probe. */
export function setCredentialsMode(next: RequestCredentials) {
  mode = next;
}

export interface Probe {
  /** The browser accepted a credentialed response from the engine. */
  credentials: boolean;
  /** HTTP status of GET /auth/me, or 0 when the request never completed. */
  status: number;
  body: unknown;
}

let probe: Promise<Probe> | null = null;

/** One credentialed GET /auth/me; sets the credentials mode for every later engine fetch. */
export function probeAuth(): Promise<Probe> {
  if (!probe) {
    probe = (async () => {
      const signal = accountRequestSignal();
      try {
        const res = await fetch(`${ENGINE_BASE}/auth/me`, { credentials: "include", signal });
        mode = "include";
        let body: unknown = null;
        try { body = await res.json(); } catch { body = null; }
        return { credentials: true, status: res.status, body };
      } catch {
        // Session cancellation says nothing about the engine's CORS/credential support.
        if (signal.aborted) return { credentials: mode === "include", status: 0, body: null };
        if (!sameOrigin) mode = "same-origin";
        return { credentials: false, status: 0, body: null };
      }
    })();
  }
  return probe;
}

/** Forget the probe (sign-in or sign-out changes the session). */
export function resetProbe() {
  probe = null;
}
