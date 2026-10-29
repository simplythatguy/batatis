import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import { CODE_TURNED_OFF } from "../../api/accounts.ts";
import { getAccountState, refreshApplications, setAccountState } from "../account.ts";

class FakeAccountsError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function codeLogin(signInWithCode: () => Promise<unknown>, endedReason = "") {
  const h = await componentHarness(new URL("./AuthPage.tsx", import.meta.url), "CodeLogin", {
    "../../api/accounts": { AccountsError: FakeAccountsError, auth: {} },
    "./useAuthGate": { signInWithCode, afterSignIn: () => "#/", signIn() {}, signUp() {}, rememberedReturn: () => null },
    "../account": { useAccount: () => ({ codeLogin: true, endedReason }) },
    "../session": { useSession: () => ({}) },
    "./bits": { ProviderMark: "ProviderMark", clockText: String, useCountdown: () => [0, () => {}] },
  }, { location: { hash: "#/signin" } });
  return h;
}

const button = (tree: unknown) => nodes(tree, (n: { type: string }) => n.type === "button")[0];

test("too many wrong codes from one address leaves Continue on, so the right code still signs in", async () => {
  let calls = 0;
  const h = await codeLogin(async () => {
    calls++;
    if (calls === 1) throw new FakeAccountsError(429, "Too many attempts right now. Try again in a moment.");
    return { onboarded: true };
  });
  let tree = await h.render({});
  const [code, name] = nodes(tree, (n: { type: string }) => n.type === "input");
  code.props.onChange({ target: { value: "a-wrong-code-xxxxxxxxxxxx" } });
  name.props.onChange({ target: { value: "Ada" } });
  tree = await h.render({});
  nodes(tree, (n: { type: string }) => n.type === "form")[0].props.onSubmit({ preventDefault() {} });
  tree = await h.render({});
  assert.match(text(tree), /Too many wrong codes/);
  assert.equal(button(tree).props.disabled, false, "a lockout must not disable Continue");
  nodes(tree, (n: { type: string }) => n.type === "form")[0].props.onSubmit({ preventDefault() {} });
  await h.render({});
  assert.equal(calls, 2, "the next try reaches the server");
  h.unmount();
});

test("the sign-in page says why a code account was signed out", async () => {
  const h = await codeLogin(async () => ({}), CODE_TURNED_OFF);
  const tree = await h.render({});
  assert.match(text(tree), /Your access code was turned off\./);
  h.unmount();
});

test("a request refused because the account's code was turned off signs the person out with that reason", async () => {
  const realFetch = globalThis.fetch;
  try {
    for (const [detail, reason] of [[CODE_TURNED_OFF, CODE_TURNED_OFF], ["Sign in to continue", ""]] as const) {
      setAccountState({ phase: "signed-in", user: { id: "gina", email: "x@code.batatis.invalid", name: "Gina" } as never, endedReason: "" });
      globalThis.fetch = (async () => new Response(JSON.stringify({ detail }), { status: 401, headers: { "Content-Type": "application/json" } })) as typeof fetch;
      await refreshApplications();
      assert.equal(getAccountState().phase, "signed-out");
      assert.equal(getAccountState().user, null);
      assert.equal(getAccountState().endedReason, reason);
    }
  } finally {
    globalThis.fetch = realFetch;
  }
});
