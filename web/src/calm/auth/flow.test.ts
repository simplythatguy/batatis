import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import * as steps from "./onboardingSteps.ts";
import { hasRealEmail } from "./codeAccount.ts";
import { getSession, resetSession, updateSession } from "../session.ts";
import type { OnboardingRequest, User } from "../../api/accounts.ts";

const person: User = { id: "u1", email: "owner@example.test", name: "Owner", role: "applicant", applicant_type: null, authority: null, onboarded: true, created_at: "2026-10-26" };

test("Start returns home through account creation and onboarding without consuming another route's return target", async () => {
  const values = new Map<string, string>([["batatis.returnTo", "#/application?case=previous"]]);
  const location = { hash: "#/" };
  const h = await componentHarness(new URL("./useAuthGate.ts", import.meta.url), "useAuthGate", {
    "../session": { updateSession, resetSession },
    "./gate": { homeFor: (u: User) => u.role === "reviewer" ? "#/review" : "#/" },
  }, { location, sessionStorage: { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => { values.set(k, v); }, removeItem: (k: string) => { values.delete(k); } } });
  resetSession({ draft: "My addition" });
  h.exports.requestStartSignIn();
  assert.equal(location.hash, "#/signin");
  assert.equal(h.exports.rememberedReturn(), "#/");
  assert.equal(h.exports.afterSignIn({ ...person, onboarded: false }), "#/onboarding");
  assert.equal(h.exports.rememberedReturn(), "#/", "onboarding preserves the return place");
  assert.equal(h.exports.afterSignIn(person), "#/");
  assert.equal(h.exports.rememberedReturn(), null);
  assert.equal(getSession().draft, "My addition");
  assert.equal(getSession().startRequested, true);
  values.set("batatis.returnTo", "#/code/9.10.9.16.");
  assert.equal(h.exports.afterSignIn(person), "#/code/9.10.9.16.", "ordinary protected-route sign-in still returns there");
  resetSession();
});

test("the applicant finishes onboarding with one choice and sends no applicant type", async () => {
  const sent: OnboardingRequest[] = [];
  const location = { hash: "#/onboarding" };
  const h = await componentHarness(new URL("./Onboarding.tsx", import.meta.url), "Onboarding", {
    "../account": { useAccount: () => ({ user: { ...person, onboarded: false } }) },
    "./codeAccount": { hasRealEmail },
    "./onboardingSteps": steps,
    "./bits": { AcIcon: "AcIcon", useCountdown: () => [0, () => {}] },
    "./useAuthGate": { saveOnboarding: async (body: OnboardingRequest) => { sent.push(body); return person; }, afterSignIn: () => "#/" },
  }, { location, document: { addEventListener() {}, removeEventListener() {} } });
  let tree = await h.render();
  const choices = nodes(tree, (n: { props?: { choices?: unknown } }) => Boolean(n.props?.choices))[0];
  assert.deepEqual(Array.from(choices.props.choices, (c: { value: string }) => c.value), ["applicant", "reviewer"]);
  choices.props.onPick("applicant");
  tree = await h.render();
  assert.doesNotMatch(text(tree), /Which describes you|variance/);
  const finish = nodes(tree, (n: { type: string; props?: { className?: string } }) => n.type === "button" && n.props?.className?.includes("is-primary"))[0];
  assert.match(text(finish), /Finish/);
  finish.props.onClick();
  await h.render();
  assert.deepEqual(sent, [{ role: "applicant" }]);
  assert.equal(location.hash, "#/");
  h.unmount();
});
