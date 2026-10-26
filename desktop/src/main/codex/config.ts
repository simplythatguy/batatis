import { createHash } from "node:crypto";
import { isModelId, isReasoningEffort, type CompleteJsonRequest } from "../providers";
import { CATALOG, CODEX_VERSION } from "./release";

function approvedModel() {
  const value = "gpt-6-luna";
  if (!isModelId(value)) throw new Error("Invalid adapter model");
  return value;
}

function approvedEffort() {
  const value = "medium";
  if (!isReasoningEffort(value)) throw new Error("Invalid adapter effort");
  return value;
}

export const MODEL = approvedModel();
export const EFFORT = approvedEffort();
export const RUNTIME_ARGS = Object.freeze(["app-server", "--listen", "stdio://", "--strict-config"]);
export const DEVICE_URL = "https://auth.openai.com/codex/device";
export const ENVIRONMENT_POLICY = Object.freeze({
  darwinKeys: Object.freeze(["HOME", "USER", "LOGNAME", "TMPDIR"]),
  windowsKeys: Object.freeze(["SystemRoot", "windir", "SystemDrive", "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "ProgramData", "USERNAME", "USERDOMAIN", "COMPUTERNAME", "PATHEXT", "ComSpec", "OS", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS"]),
  darwinPath: "/usr/bin:/bin:/usr/sbin:/sbin",
  windowsPath: Object.freeze(["System32", "", "System32/Wbem"]),
});

const CONFIG_LINES = [
  'model = "gpt-6-luna"',
  'model_provider = "openai"',
  'model_reasoning_effort = "medium"',
  'model_catalog_json = "$CATALOG"',
  'notify = []',
  'cli_auth_credentials_store = "keyring"',
  'forced_login_method = "chatgpt"',
  'developer_instructions = ""',
  'project_doc_max_bytes = 0',
  'project_doc_fallback_filenames = []',
  'include_apps_instructions = false',
  'include_collaboration_mode_instructions = false',
  'include_environment_context = false',
  'include_environment_context_time = false',
  'include_permissions_instructions = false',
  'web_search = "disabled"',
  'check_for_update_on_startup = false',
  'mcp_servers = {}',
  '[history]',
  'persistence = "none"',
  '[skills]',
  'include_instructions = false',
  'bundled.enabled = false',
  '[memories]',
  'use_memories = false',
  'generate_memories = false',
  'dedicated_tools = false',
  '[plugins._default]',
  'enabled = false',
  '[tools.update_plan]',
  'enabled = false',
  '[tools.experimental_request_user_input]',
  'enabled = false',
  '[cloud.skills]',
  'enabled = false',
  '[orchestrator.mcp]',
  'enabled = false',
  '[features]',
  'skip_host_skill_discovery = true',
  'shell_tool = false',
  'view_image = false',
  'deferred_executor = false',
  'request_permissions_tool = false',
  'token_budget = { enabled = false, use_history_notes_extension = false }',
  'current_time_reminder = false',
  'sleep_tool = false',
  'tool_suggest = false',
  'multi_agent = false',
  'multi_agent_v2 = false',
  'agent_message_board = false',
  'send_message_to_user_async = false',
  'code_mode = false',
  'code_mode_only = false',
  'tool_search = false',
  'search_tool = false',
  'standalone_web_search = false',
  'image_generation = false',
  'apps = false',
  'plugins = false',
  'hooks = false',
  'plugin_hooks = false',
  'memories = false',
  'memory_tool = false',
  'skill_search = false',
  'recommended_plugins = false',
  'model_catalog_in_context = false',
  'browser_use = false',
  'computer_use = false',
  'goals = false',
  'incremental_tools = false',
  'multi_env_copy_file = false',
  'executor_capability_discovery = false',
  'executor_capability_discovery_v2 = false',
  'code_mode_prewarm = false',
  'deferred_tool_world_state = false',
];

export function processConfig(catalogPath: string): string {
  // JSON basic-string escaping is also valid TOML for these absolute paths.
  return CONFIG_LINES.map((line) => line.startsWith("model_catalog_json =")
    ? `model_catalog_json = ${JSON.stringify(catalogPath)}` : line).join("\n") + "\n";
}

export function initializeParams(version: string) {
  return { clientInfo: { name: "batatis_desktop", title: "Batatis", version }, capabilities: { experimentalApi: true } };
}

export function threadParams(cwd: string, system: string) {
  return {
    model: MODEL, modelProvider: "openai", cwd, approvalPolicy: "never", approvalsReviewer: "user",
    sandbox: "read-only", baseInstructions: system, developerInstructions: "", ephemeral: true,
    dynamicTools: [], environments: [], runtimeWorkspaceRoots: [], selectedCapabilityRoots: [],
    allowProviderModelFallback: false,
  };
}

export function turnParams(threadId: string, request: Pick<CompleteJsonRequest, "user" | "schema">) {
  return {
    threadId, input: [{ type: "text", text: request.user }], model: MODEL, effort: EFFORT,
    outputSchema: request.schema, environments: [], runtimeWorkspaceRoots: [],
  };
}

export const CODEX_CONTEXT_FINGERPRINT = createHash("sha256").update(JSON.stringify({
  version: 1, runtimeVersion: CODEX_VERSION, args: RUNTIME_ARGS, catalogSha256: CATALOG.sha256,
  initialize: initializeParams("$APP_VERSION"), config: processConfig("$CATALOG"),
  thread: threadParams("$WORKDIR", "$SYSTEM"), turn: turnParams("$THREAD", { user: "$USER", schema: { $placeholder: "SCHEMA" } }),
  environmentPolicy: ENVIRONMENT_POLICY, model: MODEL, effort: EFFORT,
})).digest("hex");
