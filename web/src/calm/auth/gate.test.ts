import assert from "node:assert/strict";
import test from "node:test";
import type { User } from "../../api/accounts.ts";
import { gateRedirect, gateStatus, homeFor, returnTarget } from "./gate.ts";
import { USE_CHOICES, codeNeeded, nextStep, onboardingPayload, previousStep, stepsFor } from "./onboardingSteps.ts";

const user = (over: Partial<User> = {}): User => ({
  id: "u1", email: "mira@example.test", name: "Mira Kaur", role: "applicant", applicant_type: "homebuilder",
  authority: null, onboarded: true, created_at: "2026-10-21T00:00:00Z", ...over,
});

test("gate status follows the account phase", () => {
  assert.equal(gateStatus("probing", null), "loading");
  assert.equal(gateStatus("signed-out", null), "signed-out");
  assert.equal(gateStatus("anonymous", null), "ready");
  assert.equal(gateStatus("signed-in", null), "signed-out");
  assert.equal(gateStatus("signed-in", user({ onboarded: false, role: null })), "needs-onboarding");
  assert.equal(gateStatus("signed-in", user()), "ready");
});

test("gate redirects: sign-in, onboarding, home, and no accounts", () => {
  assert.equal(gateRedirect("loading", null, "/questions"), null);
  assert.equal(gateRedirect("signed-out", null, "/questions"), "#/signin");
  assert.equal(gateRedirect("signed-out", null, "/accuracy"), "#/signin");
  assert.equal(gateRedirect("signed-out", null, "/signup"), null);
  assert.equal(gateRedirect("needs-onboarding", user({ onboarded: false }), "/"), "#/onboarding");
  assert.equal(gateRedirect("needs-onboarding", user({ onboarded: false }), "/onboarding"), null);
  assert.equal(gateRedirect("ready", user(), "/signin"), "#/");
  assert.equal(gateRedirect("ready", user(), "/signin", "#/code"), "#/code");
  assert.equal(gateRedirect("ready", user({ role: "reviewer", authority: "edmonton" }), "/onboarding"), "#/review");
  assert.equal(gateRedirect("ready", user({ role: "reviewer", authority: "edmonton" }), "/"), "#/review");
  assert.equal(gateRedirect("ready", user(), "/"), null);
  assert.equal(gateRedirect("ready", null, "/signin"), "#/", "no accounts on this server: back to the single-visit flow");
  assert.equal(gateRedirect("ready", null, "/questions"), null);
  assert.equal(homeFor(null), "#/");
});

test("signed-out visitors can prepare a draft on Start; other application routes stay gated", () => {
  assert.equal(gateRedirect("signed-out", null, "/"), null);
  assert.equal(gateRedirect("signed-out", null, ""), null);
  for (const path of ["/questions", "/review", "/application", "/settings", "/code", "/onboarding", "/review/case_1"]) {
    assert.equal(gateRedirect("signed-out", null, path), "#/signin", path);
  }
});

test("return targets skip the auth pages and home", () => {
  assert.equal(returnTarget("#/review/case_1"), "#/review/case_1");
  assert.equal(returnTarget("#/code/9.10.9.16.?filter=all"), "#/code/9.10.9.16.?filter=all");
  assert.equal(returnTarget("#/signin"), null);
  assert.equal(returnTarget("#/onboarding"), null);
  assert.equal(returnTarget(""), null);
});

test("onboarding steps branch on the first answer and build the request", () => {
  assert.deepEqual(stepsFor({ code: "" }), ["use"]);
  assert.deepEqual(stepsFor({ use: "applicant", code: "" }), ["use"]);
  assert.deepEqual(stepsFor({ use: "reviewer", code: "" }), ["use", "authority", "code"]);
  assert.equal(nextStep("use", { use: "reviewer", code: "" }), "authority");
  assert.equal(nextStep("authority", { use: "reviewer", authority: "edmonton", code: "" }), "code");
  assert.equal(nextStep("code", { use: "reviewer", authority: "edmonton", code: "x" }), null);
  assert.equal(nextStep("use", { use: "applicant", code: "" }), null);
  assert.equal(previousStep("code", { use: "reviewer", code: "" }), "authority");
  assert.equal(previousStep("use", { code: "" }), null);
  assert.deepEqual(onboardingPayload({ use: "applicant", code: "" }), { role: "applicant" });
  assert.deepEqual(onboardingPayload({ use: "reviewer", authority: "calgary", code: "  abc  " }), { role: "reviewer", authority: "calgary", access_code: "abc" });
  assert.equal(onboardingPayload({ use: "reviewer", authority: "calgary", code: " " }), null);
  assert.equal(onboardingPayload({ code: "" }), null);
  assert.deepEqual(USE_CHOICES[0], { value: "applicant", label: "I have a building project", sub: "Owner, designer, builder, engineer or manufacturer" });
});

test("settings asks for a code when becoming or leaving a reviewer", () => {
  assert.deepEqual(codeNeeded({ role: "applicant", authority: null }, "reviewer", "edmonton"), { authority: "edmonton" });
  assert.deepEqual(codeNeeded({ role: "reviewer", authority: "calgary" }, "applicant"), { authority: "calgary" });
  assert.equal(codeNeeded({ role: "applicant", authority: null }, "applicant"), null);
  assert.equal(codeNeeded({ role: "applicant", authority: null }, "reviewer", null), null);
});
