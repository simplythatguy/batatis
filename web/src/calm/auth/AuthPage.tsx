/** #/signin and #/signup: one centered column, email first, providers only when the server has them. */
import { useEffect, useId, useState, type FormEvent } from "react";
import { AccountsError, auth, type AuthProvider } from "../../api/accounts";
import { ProviderMark, clockText, useCountdown } from "./bits";
import { afterSignIn, rememberedReturn, signIn, signUp } from "./useAuthGate";
import { DesktopEntry } from "../../desktop/Entry";

export const PASSWORD_MIN = 10;

function useProviders(): AuthProvider[] {
  const [list, setList] = useState<AuthProvider[]>([]);
  useEffect(() => {
    const ctl = new AbortController();
    auth.providers(ctl.signal).then(
      (p) => setList(p.filter((x) => x.id === "google" || x.id === "microsoft")),
      () => setList([]),
    );
    return () => ctl.abort();
  }, []);
  return list;
}

function errorText(e: unknown, mode: "signin" | "signup"): string {
  if (!(e instanceof AccountsError)) return "Something went wrong. Try again.";
  if (e.status === 401) return "Email or password is incorrect.";
  if (e.status === 409 && mode === "signup") return "An account with this email already exists.";
  if (e.status === 422) return mode === "signup" ? "Check your name, email and password." : "Enter your email and password.";
  if (e.status === 0) return "Batatis couldn’t reach the server. Check your connection and try again.";
  return e.detail || "Something went wrong. Try again.";
}

export function AuthPage({ mode }: { mode: "signin" | "signup" }) {
  const providers = useProviders();
  const id = useId();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [duplicate, setDuplicate] = useState(false);
  const [wait, startWait] = useCountdown();
  const [touched, setTouched] = useState(false);
  const signup = mode === "signup";
  const shortPassword = signup && password.length < PASSWORD_MIN;

  useEffect(() => {
    setError("");
    setDuplicate(false);
  }, [mode]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (busy || wait > 0) return;
    if (!email.trim() || !password || (signup && (!name.trim() || shortPassword))) {
      setError(signup && shortPassword && password ? "" : signup ? "Enter your name, email and a password." : "Enter your email and password.");
      return;
    }
    setBusy(true);
    setError("");
    setDuplicate(false);
    try {
      const user = signup ? await signUp(name, email, password) : await signIn(email, password);
      location.hash = afterSignIn(user);
    } catch (err) {
      if (err instanceof AccountsError && err.status === 429) {
        startWait(err.retryAfter);
        setError("");
      } else {
        setError(errorText(err, mode));
        setDuplicate(err instanceof AccountsError && err.status === 409 && signup);
      }
    } finally {
      setBusy(false);
    }
  }

  // The OAuth callback lands on the web origin plus this path; the gate takes it from there.
  const redirect = `/${rememberedReturn() ?? "#/"}`;

  return (
    <div className="ac-auth">
      <form className="ac-auth-box" onSubmit={submit} noValidate aria-labelledby={`${id}-title`}>
        <span className="cf-mark ac-auth-mark" aria-hidden="true" />
        <h1 id={`${id}-title`} className="ac-auth-title">{signup ? "Create account" : "Sign in"}</h1>
        {!signup && <DesktopEntry />}

        {signup && (
          <div className="ac-field">
            <label htmlFor={`${id}-name`}>Name</label>
            <input id={`${id}-name`} className="ac-in" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
        )}
        <div className="ac-field">
          <label htmlFor={`${id}-email`}>Email</label>
          <input id={`${id}-email`} className="ac-in" type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus={!signup} />
        </div>
        <div className="ac-field">
          <label htmlFor={`${id}-pw`}>Password</label>
          <input
            id={`${id}-pw`}
            className="ac-in"
            type="password"
            autoComplete={signup ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-describedby={signup ? `${id}-rule` : undefined}
            aria-invalid={signup && touched && shortPassword ? true : undefined}
          />
          {signup && (
            <p id={`${id}-rule`} className={`ac-rule${password && !shortPassword ? " is-met" : touched && shortPassword ? " is-unmet" : ""}`}>
              <span className="ac-rule-dot" aria-hidden="true" />
              At least {PASSWORD_MIN} characters{password ? ` · ${password.length}` : ""}
            </p>
          )}
        </div>

        {error && (
          <p className="ac-error" role="alert">
            {error}
            {duplicate && <> <a href="#/signin">Sign in instead</a></>}
          </p>
        )}
        {wait > 0 && (
          <p className="ac-error" role="status">Too many attempts. Try again in {clockText(wait)}.</p>
        )}

        <button type="submit" className="cf-btn is-primary is-center ac-auth-go" disabled={busy || wait > 0}>
          {busy ? (signup ? "Creating account…" : "Signing in…") : signup ? "Create account" : "Sign in"}
        </button>

        {providers.length > 0 && (
          <>
            <div className="ac-or">or</div>
            {providers.map((p) => (
              <a key={p.id} className="cf-btn is-center ac-oauth" href={auth.oauthStart(p.id, redirect)}>
                <ProviderMark id={p.id} />
                Continue with {p.label}
              </a>
            ))}
          </>
        )}

        <p className="ac-auth-switch">
          {signup ? <a href="#/signin">Sign in</a> : <a href="#/signup">Create an account</a>}
        </p>
      </form>
    </div>
  );
}
