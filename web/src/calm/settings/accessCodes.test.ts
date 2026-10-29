import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";

const info = { name: "qa1-team", source: "managed", max_users: 3, accounts: 2, in_use: 2, revoked: false, created_at: null };
const byType = (tree: unknown, type: string) => nodes(tree, (n: { type: unknown }) => n.type === type);
const button = (tree: unknown, label: string) => byType(tree, "button").find((b: unknown) => text(b) === label);

test("Remove asks first, shows how many use the code, and removes only on confirm", async () => {
  const removed: string[] = [];
  const h = await componentHarness(new URL("./AccessCodes.tsx", import.meta.url), "CodeRow", {
    "../../api/accounts": { AccountsError: class {}, adminCodes: { remove: async (name: string) => { removed.push(name); } } },
    "../ui": { ConfirmDialog: "ConfirmDialog" },
  });
  const gone: string[] = [];
  const props = { info, onChange() {}, onRemove: (name: string) => gone.push(name), onError() {} };
  let tree = await h.render(props);
  assert.equal(byType(tree, "ConfirmDialog").length, 0);
  button(tree, "Remove").props.onClick();
  tree = await h.render(props);
  const [dialog] = byType(tree, "ConfirmDialog");
  assert.equal(dialog.props.title, "Remove qa1-team?");
  assert.match(text(dialog.props.body), /2 in use/);
  assert.deepEqual(removed, [], "nothing is removed before the confirmation");
  dialog.props.onClose();
  tree = await h.render(props);
  assert.equal(byType(tree, "ConfirmDialog").length, 0);
  assert.deepEqual(removed, []);
  button(tree, "Remove").props.onClick();
  tree = await h.render(props);
  byType(tree, "ConfirmDialog")[0].props.onConfirm();
  await h.render(props);
  assert.deepEqual(removed, ["qa1-team"]);
  assert.deepEqual(gone, ["qa1-team"]);
  h.unmount();
});

async function settings(admin: boolean) {
  const h = await componentHarness(new URL("./Settings.tsx", import.meta.url), "Settings", {
    "../account": { useAccount: () => ({ user: { id: "u", email: "a@code.batatis.invalid", name: "Ada", role: "applicant", applicant_type: null, authority: null, admin }, codeLogin: true }) },
    "../auth/bits": { PageHead: "PageHead" },
    "../auth/signOutGuard": { useSignOutStatus: () => ({ pending: false, error: "" }) },
    "../auth/codeAccount": { hasRealEmail: () => false },
    "../auth/onboardingSteps": { APPLICANT_LABEL: {} },
    "../../privacy": { PRIVACY_NOTICE: "" },
    "./AccessCodes": { AccessCodesSection: "AccessCodesSection" },
    "./AiAccess": { AiAccessSection: "AiAccessSection" },
    "./ArchivedApplications": { ArchivedApplications: "ArchivedApplications" },
    "./rows": { Row: "Row", Chips: "Chips" },
  });
  const tree = await h.render({});
  h.unmount();
  return tree;
}

test("only the site admin's Settings asks for the access-code list", async () => {
  assert.equal(byType(await settings(false), "AccessCodesSection").length, 0);
  assert.equal(byType(await settings(true), "AccessCodesSection").length, 1);
});
