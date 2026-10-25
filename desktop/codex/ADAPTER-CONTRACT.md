# Local Codex adapter

The implementation exports `codexProviderFactory(options?): HostProviderFactory` from `src/main/codex.ts` and satisfies core's `src/main/providers.ts`. It is an AI connection, separate from the Batatis user, role, workspace and database.

The default completion gate is closed as `context_unverified`. Offline fixture tests exercise the implementation. They do not establish native context isolation, keyring operation, account entitlement or Windows packaged-app acceptance. No native account request, login or inference was used to implement or test this adapter. The parent owns native proof, UI integration, independent review and Windows CI.

## Integration

```ts
import { codexProviderFactory } from "./codex";

const provider = codexProviderFactory()({
  stateDir: /* persistent app-owned provider home */,
  workDir: /* empty app-owned directory outside every Git checkout */,
  resourcesDir: /* process.resourcesPath when packaged; repository root in development */,
  appVersion: app.getVersion(),
  log: /* scrubbed fixed-message logger */,
});
```

Main owns provider installation, settings routing and disposal. Do not accept paths, executables, model settings, environment overrides or verification evidence from the renderer. The adapter returns the pending device URL/code; main opens the URL in the system browser only when the person clicks it.

`CodexProviderOptions` supports privileged runtime/spawn injection for offline fixtures, an environment source filtered by the fixed allow-list, platform/architecture, bounded test deadlines, and optional `verifiedContext`. Production uses `bundledRuntime()` and Node's `spawn` with `shell:false`. `bundledRuntime({executable})` supports a developer-installed executable only if its digest is pinned in `release.ts`.

`verifiedContext` contains `evidence`, `runtimeSha256` and `contextFingerprint`. The fingerprint must equal exported `CODEX_CONTEXT_FINGERPRINT`; the runtime digest must equal the verified executable actually resolved. The fingerprint hashes startup arguments, initialize/thread/turn templates, process TOML, catalog digest, model/effort and the environment allow-list. Path, version, prompt and schema placeholders are expanded with the host/request values. There is no production `true` bypass. A signed-in account does not open the gate.

## Files and ownership

| File | Responsibility |
| --- | --- |
| `src/main/codex.ts` | Provider lifecycle, account-operation queue, pending login, runtime slot, context gate and completion orchestration. |
| `src/main/codex/config.ts` | Exact TOML, allowed model/effort, initialize/thread/turn parameters and context fingerprint. |
| `src/main/codex/protocol.ts` | Wire-value parsing, safe errors, model/account metadata, and strict Ajv output validation. |
| `src/main/codex/rpc.ts` | Owned child, UTF-8 JSONL framing, request IDs, deadlines, byte/pending limits, refusal of server requests, shutdown escalation. |
| `src/main/codex/turn.ts` | Correlated authoritative final-answer acceptance, cancellation, usage and schema checks. |
| `src/main/codex/binary.ts` | Resource/digest verification, canonical private paths, owned configuration files and child-environment filtering. |
| `src/main/codex/release.ts` | Pinned release/archive/executable/catalog provenance. |
| `codex/fetch.mjs` | Build-time verified archive extraction and exact six-field catalog derivation. |
| `codex/bind-evidence.py` | Offline binding of actual adapter templates to the saved synthetic native request captures. |
| `tests/codex*.test.ts` | Offline unit checks and actual scripted stdio child-process fixtures. |

Core owns all package, lock, build, CI, main installation, UI and engine files. Engine domain checks, deterministic Section C and human-owned professional conclusions remain in the existing engine.

## Runtime and resources

Pinned Codex `0.164.0`, release `rust-v0.164.0`, source `6aaac694803004a63c6f393d153c96d22521a6b9`.

Required targets with verified archive and extracted-executable digests are macOS ARM64 and Windows x64. Other archive pins are retained from the original draft; those targets cannot run until an executable digest is explicitly pinned. A writable manifest alone cannot authorize a binary.

Run from the repository root with Node 24 or later:

```sh
node desktop/codex/fetch.mjs catalog
node desktop/codex/fetch.mjs runtime darwin-arm64
node desktop/codex/fetch.mjs runtime win32-x64
node desktop/codex/fetch.mjs notices
```

An already-downloaded archive can be the third argument to `runtime`; its size and digest are still checked before extraction. `catalog` can take an already-downloaded pinned original source. No executable is run by the helper. Extraction uses a fixed system `tar` executable and an explicit member argument with `shell:false`. Native Windows CI must verify the Windows system-tar/zip extraction path.

Package these resources under `<resources>/codex/`:

- `luna-models.json`, `LICENSE`, `NOTICE`.
- `runtime/<platform>-<arch>/codex` or `codex.exe` and `codex-runtime.json`.

The catalog retains all 11 original entries and every other original byte. Only the six reviewed Luna metadata values change. Candidate digest `dca46de82fef92c2d3f7212467181b2d17cf8e5a3d468ade38d555280bf37fb8`; source digest `943ca7fe1d19ed019054158303f0dbbd80b3bef43b3aa425a71aa7cb3fb52c2b`. Metadata does not grant model access, establish entitlement, provide prices or impose a token ceiling.

## Isolation and protocol

The sidecar runs `app-server --listen stdio:// --strict-config` in the canonical empty private working directory. Stdio is `[pipe, pipe, ignore]`, with no listener and no shell. The app-owned canonical `CODEX_HOME` cannot be the person's ordinary Codex home or an inherited `CODEX_HOME`. No existing authentication is imported or copied. Credentials require `cli_auth_credentials_store="keyring"`; plaintext `auth.json` is refused by metadata inspection without reading its contents.

The environment carries only `CODEX_HOME`, a fixed system `PATH`, and the exact OS keys in `ENVIRONMENT_POLICY`. Provider keys, proxies, T3/agent variables, extra `CODEX_*`, `RUST_LOG` and `XDG_*` are excluded. The exact verified catalog and isolation TOML are installed before startup. The catalog override is process-scoped, never a thread override.

Frames are UTF-8 JSON lines with CRLF accepted, at most 4 MiB. The adapter uses positive safe-integer request IDs, at most 32 pending RPCs and 8 queued provider operations. Unknown/duplicate response IDs, invalid UTF-8/JSON/envelopes and truncated streams stop the process. Every server request is answered with `-32601` and stops the process. This defensive refusal does not prove that an internal built-in tool could not already have executed.

Only `account/login/start {type:"chatgptDeviceCode"}` is used. Pending URL must be exactly `https://auth.openai.com/codex/device`; code and ID are validated. Completion must correlate to the pending ID. Early notifications are bounded and correlated; stale login IDs do not complete another login. Cancellation reports the actual account if login won the race. Disabled device login shows the account/workspace prerequisite. There is no browser-callback, custom-client, internal token or API-key fallback.

Logout cancels active and queued workflow work and pending device login, requires `account/logout` success, a signed-out notification during that operation and a confirming signed-out `account/read`, then stops the owned child. Failure is reported rather than claimed as sign-out. This is local credential removal, not remote revocation. Disposal cancels work, ends stdin, then escalates to SIGTERM/SIGKILL on bounded deadlines and waits for child exit.

## Completion acceptance

Only exact `gpt-6-luna` with `medium` is supported. Model listing is paginated and bounded; a catalog entry is not treated as account entitlement. Unsupported IDs/efforts or provider rerouting fail without substitution.

Each call creates a fresh ephemeral thread. `baseInstructions` is the exact workflow system string; developer instructions are empty. User input is one exact text item and `outputSchema` is the exact workflow schema. Dynamic tools, environments and runtime/capability roots are empty; `allowProviderModelFallback` is false. No resume, history, file attachment, skill, MCP or plugin context is supplied. Config requirements and echoed thread metadata are checked; missing observability and managed instructions fail closed. Unexpected runtime warnings, discovery changes, tool items or server requests stop the child. Only the exact observed disabled remote-control notice, memory-tool alias deprecation and skip-host-skill-discovery warning are accepted as known notices. Other warnings remain failures.

Success requires one completed agent-message item, a matching terminal turn ID and thread ID, `status:"completed"`, no terminal/non-retried error, and matching final ID/text/phase in the terminal item list. Commentary is ignored rather than concatenated. Partial answers, incomplete/refused/non-object JSON, async delivery, questions, memory citations and schema mismatches fail. Ajv 8.20.0 runs in strict mode without coercion, defaults, field removal, remote schema loading or JSON repair. The engine must still apply its existing domain validation.

Reported token totals are preserved; absent usage is `null`. No price or zero-usage default is invented. `maxOutputTokens` is not an upstream parameter or ceiling; an observed overrun is rejected locally. Default completion deadline is 170 seconds. Abort/deadline sends one correlated interrupt where possible, waits up to 5 seconds, then stops an uncooperative child. Late output is discarded. Requests are never retried.

## Outstanding acceptance

The saved no-auth macOS native probe captures two fresh candidate requests with exact synthetic instruction text, user text and schema, and no exposed tool definitions. The stock positive control exposes tools and is rejected. Native Codex puts the supplied system instructions in the developer role and retains attribution IDs. Response Lite can expose tools through top-level `tools` or `input` items of type `additional_tools`; the binding check rejects both. This establishes a local request-boundary observation, not an identical API system-role contract or a universal internal handler deny-list.

Run the offline binding helper with Python 3.11 or later after the adapter source is frozen:

```sh
python3 desktop/codex/bind-evidence.py /absolute/path/to/native-probe --output /absolute/path/to/adapter/native-binding.json
```

The helper checks the pinned artifact-manifest digest, original capture bytes, actual adapter process configuration, actual thread and turn builders, runtime/catalog hashes, required response parsers and the stock control. It maps native assembly fingerprint `2e35120991aa50a2ede1b65ac70182aa2f46f2e511f2bff1c484561f2020f0a6` to the separately exported adapter fingerprint. It starts no Codex process, opens no network connection and enables no production gate. The proposed `verifiedContext` in its output is for parent review and privileged installation only.

The parent must review the documented deviations before enabling local request-boundary mode. Production uses the keyring and official endpoint; the no-auth probe used ephemeral credentials, a denied loopback endpoint, private HOME/XDG and synthetic tracing. Client identity and native attribution metadata also differ. Provider-owned policy remains outside request-byte parity. Native keyring login/logout, account entitlement and inference need an authorized user action. Windows packaged-app CI acceptance is required separately; macOS evidence and fake-process checks are not Windows acceptance. This nonvisual adapter slice supplies no UI screenshots or demo.
