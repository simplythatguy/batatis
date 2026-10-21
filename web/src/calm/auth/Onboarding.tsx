/** #/onboarding: one question at a time, letter keys pick, Enter continues (Typeform style). */
import { useEffect, useId, useRef, useState } from "react";
import { AccountsError } from "../../api/accounts";
import { useAccount } from "../account";
import { AcIcon, clockText, useCountdown } from "./bits";
import { homeFor } from "./gate";
import {
  APPLICANT_CHOICES,
  AUTHORITY_CHOICES,
  KEYS,
  USE_CHOICES,
  answered,
  nextStep,
  onboardingPayload,
  previousStep,
  stepsFor,
  type Answers,
  type Choice,
  type StepId,
} from "./onboardingSteps";
import { saveOnboarding, signOut } from "./useAuthGate";

const QUESTION: Record<StepId, { text: string; help?: string }> = {
  use: { text: "How will you use Batatis?", help: "You can change this later in settings." },
  applicantType: { text: "Which describes you best?", help: "This helps us ask the right questions about your project." },
  authority: { text: "Which authority do you review for?", help: "You’ll see the applications sent there." },
  code: { text: "Enter your authority’s access code.", help: "Your authority gives this to its Safety Codes Officers." },
};

function ChoiceList<T extends string>({ choices, value, onPick, tall, label }: { choices: Choice<T>[]; value: T | undefined; onPick: (v: T) => void; tall?: boolean; label: string }) {
  return (
    <div className={`ac-choices${tall ? " is-wide" : ""}`} role="group" aria-label={label}>
      {choices.map((c, i) => (
        <button
          key={c.value}
          type="button"
          aria-pressed={value === c.value}
          className={`ac-choice${tall ? " is-tall" : ""}`}
          onClick={() => onPick(c.value)}
        >
          <span className="ac-key" aria-hidden="true">{KEYS[i]}</span>
          <span className="ac-choice-text">
            {c.label}
            {c.sub && <span className="ac-choice-sub">{c.sub}</span>}
          </span>
          <span className="ac-choice-chk"><AcIcon name="check" size={16} /></span>
        </button>
      ))}
    </div>
  );
}

export function Onboarding() {
  const account = useAccount();
  const id = useId();
  const [answers, setAnswers] = useState<Answers>({ code: "" });
  const [step, setStep] = useState<StepId>("use");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [wait, startWait] = useCountdown();
  const codeRef = useRef<HTMLInputElement>(null);
  const steps = stepsFor(answers);
  const n = steps.indexOf(step) + 1;
  const ready = answered(step, answers);

  const choices: Choice<string>[] = step === "use" ? USE_CHOICES : step === "applicantType" ? APPLICANT_CHOICES : step === "authority" ? AUTHORITY_CHOICES : [];

  function pick(value: string) {
    setError("");
    setAnswers((a) => {
      if (step === "use") return { ...a, use: value as Answers["use"] };
      if (step === "applicantType") return { ...a, applicantType: value as Answers["applicantType"] };
      if (step === "authority") return { ...a, authority: value as Answers["authority"], code: a.authority === value ? a.code : "" };
      return a;
    });
  }

  async function ok() {
    if (!ready || busy || wait > 0) return;
    const next = nextStep(step, answers);
    if (next) {
      setError("");
      setStep(next);
      return;
    }
    const body = onboardingPayload(answers);
    if (!body) return;
    setBusy(true);
    setError("");
    try {
      const user = await saveOnboarding(body);
      location.hash = homeFor(user);
    } catch (e) {
      if (e instanceof AccountsError && e.status === 429) startWait(e.retryAfter);
      else if (e instanceof AccountsError && e.status === 403) setError(e.detail || "That access code didn’t work.");
      else if (e instanceof AccountsError && e.status === 401) setError("Your session ended. Sign in again to continue.");
      else setError(e instanceof AccountsError && e.detail ? e.detail : "That didn’t save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function back() {
    const prev = previousStep(step, answers);
    if (prev) {
      setError("");
      setStep(prev);
    }
  }

  // Letter keys pick a choice; Enter continues. Typing in the code field keeps its letters.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const typing = (e.target as HTMLElement)?.closest?.("input, textarea");
      if (e.key === "Enter") {
        const control = (e.target as HTMLElement)?.closest?.("button, a");
        if (control && !control.classList.contains("ac-choice")) return; // OK, Back and links handle their own Enter
        // Enter on an unpressed choice selects it (native click); only a pressed one continues.
        if (control && control.getAttribute("aria-pressed") !== "true") return;
        e.preventDefault();
        void ok();
        return;
      }
      if (typing || !choices.length) return;
      const i = KEYS.indexOf(e.key.toUpperCase());
      if (e.key.length === 1 && i >= 0 && i < choices.length) {
        e.preventDefault();
        pick(choices[i].value);
      }
    };
    document.addEventListener("keydown", on);
    return () => document.removeEventListener("keydown", on);
  });

  useEffect(() => {
    if (step === "code") codeRef.current?.focus();
  }, [step]);

  const value = step === "use" ? answers.use : step === "applicantType" ? answers.applicantType : step === "authority" ? answers.authority : undefined;
  const q = QUESTION[step];
  const last = !nextStep(step, answers) && step !== "use";

  return (
    <div className="ac-onb">
      <div className="ac-onb-top">
        <span className="cf-mark" aria-hidden="true" />
        {account.user && (
          <span className="ac-onb-who">
            <span className="cf-faint">{account.user.email}</span>
            <button type="button" className="cf-btn is-ghost is-xs" onClick={() => void signOut()}>Sign out</button>
          </span>
        )}
      </div>
      <div className="ac-onb-stage">
        <div className="ac-q" key={step}>
          <div className="ac-q-num"><span>{n}</span><AcIcon name="right" size={14} /></div>
          <h1 className="ac-q-text" id={`${id}-q`}>{q.text}</h1>
          {q.help && <p className="ac-q-help">{q.help}</p>}

          {step === "code" ? (
            <input
              ref={codeRef}
              className="ac-underline"
              aria-labelledby={`${id}-q`}
              aria-describedby={error ? `${id}-err` : undefined}
              aria-invalid={error ? true : undefined}
              autoComplete="off"
              spellCheck={false}
              placeholder="Type the code here…"
              value={answers.code}
              onChange={(e) => { setError(""); setAnswers((a) => ({ ...a, code: e.target.value })); }}
            />
          ) : (
            <ChoiceList choices={choices} value={value} onPick={pick} tall={step === "use"} label={q.text} />
          )}

          {error && <p id={`${id}-err`} className="ac-error is-onb" role="alert">{error}</p>}
          {wait > 0 && <p className="ac-error is-onb" role="status">Too many attempts. Try again in {clockText(wait)}.</p>}

          <div className="ac-ok-row">
            <button type="button" className="cf-btn is-primary" disabled={!ready || busy || wait > 0} onClick={() => void ok()}>
              {busy ? "Saving…" : last ? "Finish" : "OK"}
              <AcIcon name="check" size={16} />
            </button>
            <span className="ac-ok-hint">press <b>Enter ↵</b></span>
            {n > 1 && <button type="button" className="cf-btn is-ghost is-sm ac-back" onClick={back}><AcIcon name="back" size={14} />Back</button>}
          </div>
        </div>
      </div>
      <div className="ac-onb-progress" aria-hidden="true">
        {steps.map((s, i) => <i key={s} className={i < n - 1 ? "is-done" : i === n - 1 ? "is-cur" : ""} />)}
      </div>
    </div>
  );
}
