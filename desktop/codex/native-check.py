#!/usr/bin/env python3
"""Capture the pinned native no-auth request boundary. Python 3.11+, Node 24+.

Run with --resources-dir <repository or packaged resources> --output <new directory>.
Replay with --replay <saved directory> [--manifest-sha256 <trusted digest>].
Windows additionally requires a parent-installed --windows-firewall-rule on GitHub CI.
No authentication or inference success is required or attempted.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
import uuid

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
CATALOG_SHA = "dca46de82fef92c2d3f7212467181b2d17cf8e5a3d468ade38d555280bf37fb8"
SOURCE_SHA = "943ca7fe1d19ed019054158303f0dbbd80b3bef43b3aa425a71aa7cb3fb52c2b"
CONTROL_SHA = "58ea4bba73138ac35578ddccaec77c0fcf80ba99a53b73736e39e7e3b82397a1"
ASSEMBLY_SHA = "2e35120991aa50a2ede1b65ac70182aa2f46f2e511f2bff1c484561f2020f0a6"
CONTEXT_SHA = "6f3aa205db02c55e79cb120090c99d17ae33db696fb306f3470e220ec61ef708"
RUNTIME_SHA = {
    "darwin-arm64": "d8990e3ee7acfbc26f91265b12a1a83f0fee40d0e0f8f1f40a37d4ec21f499cf",
    "win32-x64": "6f267830b029ee25d9339864aa867cd45de9f8fd4c5ea007d2e63c13a0c66d36",
}
SOURCE_PINS = {
    "desktop/src/main/codex/config.ts": "b43406a24a5c8a8a8efbb9694979728d654b252acb3656e045fdeb8da274e9a4",
    "desktop/src/main/codex/release.ts": "15b246a3847f0c79215a76d5d26dd64d3fdf285254c9179272357de8fe555da5",
    "desktop/src/main/codex/binary.ts": "0266824a4afbebbcdc33c3b36ea70d2b4e6b4c53f9cd0c9ad6d220860b82285a",
    "desktop/src/main/codex/protocol.ts": "2c7531da4dd9ab70931a8fbf47f18ec411277280ac4e2daa8693fdd36c3700de",
    "desktop/scripts/register-ts.mjs": "f55ea34b5f9c8376ca69e9e95ceae774989050228ea0fa9c2673aa109b8f91c6",
    "desktop/scripts/ts-ext.mjs": "2ad6a35c6168a4bcce426223f2b4575754cc426a3c5a9adecf799156379e57d6",
}
OBSERVED_SOURCES = ("desktop/src/main/providers.ts",)
METHODS = {"initialize", "initialized", "configRequirements/read", "model/list",
           "thread/start", "turn/start", "turn/interrupt"}
CASES = ("candidate-a", "candidate-b", "stock-control")
STOCK_TOOLS = (
    "functions.exec", "functions.wait", "collaboration.followup_task",
    "collaboration.interrupt_agent", "collaboration.list_agents",
    "collaboration.send_message", "collaboration.spawn_agent", "collaboration.wait_agent",
)
MAX_FILE = 2_000_000
MAX_STREAM = 3_000_000
MAX_LINE = 500_000
NETWORK_PROFILE = "(version 1)\n(allow default)\n(deny network*)\n"


class Rejected(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json_bytes(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise Rejected("Nonfinite JSON number " + value)
    return json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=pairs, parse_constant=constant)


def read_bytes(path, limit=MAX_FILE):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Expected regular evidence file " + str(path))
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Evidence file exceeds byte limit")
    return raw


def load(path):
    return load_json_bytes(read_bytes(path))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def checked_sources(repo=REPO):
    observed = {}
    for relative in (*SOURCE_PINS, *OBSERVED_SOURCES):
        raw = read_bytes(repo / relative)
        normalized = digest(raw.replace(b"\r\n", b"\n"))
        if relative in SOURCE_PINS:
            require(normalized == SOURCE_PINS[relative], "Adapter source fingerprint changed " + relative)
        observed[relative] = {"rawSha256": digest(raw), "lfSha256": normalized}
    return observed


def assembly_config(config):
    result = dict(config)
    result.pop("cli_auth_credentials_store", None)
    result.pop("openai_base_url", None)
    result["model_catalog_json"] = "<APP_PRIVATE_CATALOG>"
    return result


def probe_config(actual, catalog):
    parsed = tomllib.loads(actual)
    require(parsed["cli_auth_credentials_store"] == "keyring" and "openai_base_url" not in parsed,
            "Production authentication configuration changed")
    require(digest(canonical(assembly_config(parsed))) == ASSEMBLY_SHA, "Assembly config fingerprint changed")
    require(parsed["model_catalog_json"] == str(catalog), "Builder selected a different catalog")
    require(actual.count('cli_auth_credentials_store = "keyring"') == 1, "Unexpected credential setting")
    value = actual.replace('cli_auth_credentials_store = "keyring"', 'cli_auth_credentials_store = "ephemeral"')
    value = 'openai_base_url = "http://127.0.0.1:0/v1"\n' + value
    require(assembly_config(tomllib.loads(value)) == assembly_config(parsed), "Unexpected probe config delta")
    return value


def control_catalog(candidate):
    require(digest(candidate) == CATALOG_SHA, "Candidate catalog bytes changed")
    original = load_json_bytes(candidate)
    patched = load_json_bytes(candidate)
    fixture = load(Path(__file__).with_name("native-control.json"))
    require(digest(canonical(fixture)) == CONTROL_SHA, "Original control metadata changed")
    require(set(fixture) == {"apply_patch_tool_type", "tool_mode", "multi_agent_version", "shell_type",
                             "experimental_supported_tools", "supports_search_tool"}, "Control must have exactly six original fields")
    luna = [row for row in patched["models"] if row["slug"] == "gpt-6-luna"]
    require(len(original["models"]) == 11 and len(luna) == 1, "Catalog model identities changed")
    luna[0].update(fixture)
    edits = []
    for index, (before, after) in enumerate(zip(original["models"], patched["models"], strict=True)):
        edits.extend((index, key) for key in before if before[key] != after[key])
    require(len(edits) == 6 and {key for _, key in edits} == set(fixture), "Control changed more than six Luna values")
    return json.dumps(patched, indent=2, ensure_ascii=False).encode() + b"\n"


def verify_control_source(source):
    raw = read_bytes(source)
    require(digest(raw) == SOURCE_SHA, "Original upstream catalog hash changed")
    stock = load_json_bytes(raw)
    fixture = load(Path(__file__).with_name("native-control.json"))
    require(digest(canonical(fixture)) == CONTROL_SHA, "Original control metadata changed")
    luna = next(row for row in stock["models"] if row["slug"] == "gpt-6-luna")
    require(fixture == {key: luna[key] for key in fixture}, "Control fixture differs from pinned upstream")


def tool_names(body):
    tools = body.get("tools", [])
    require(isinstance(tools, list), "Malformed top-level tools")
    tools = list(tools)
    require(isinstance(body.get("input"), list), "Malformed request input")
    for item in body["input"]:
        require(isinstance(item, dict), "Malformed input item")
        if item.get("type") == "additional_tools":
            require(isinstance(item.get("tools"), list), "Malformed additional_tools")
            tools.extend(item["tools"])
    names = []
    def visit(tool, prefix="", depth=0):
        require(depth < 8 and isinstance(tool, dict), "Malformed tool definition")
        name = ".".join(filter(None, [prefix, tool.get("name", "")]))
        if tool.get("type") == "namespace":
            require(isinstance(tool.get("tools"), list), "Malformed tool namespace")
            for child in tool["tools"]:
                visit(child, name, depth + 1)
        else:
            names.append(name or "<unnamed>")
    for item in tools:
        visit(item)
    return names


def assert_candidate(body, expected):
    require(tool_names(body) == [], "Model-visible tools exposed")
    require(not body.get("tools"), "Top-level tool declarations exposed")
    allowed = {"model", "stream", "input", "tool_choice", "parallel_tool_calls", "reasoning", "store",
               "include", "prompt_cache_key", "text", "client_metadata", "tools"}
    require(set(body) <= allowed, "Extra request fields can supply context")
    require(len(body["input"]) == 2, "Extra prompt, context, history, attachment or additional_tools input")
    for message, role, text in zip(body["input"], ("developer", "user"), (expected["system"], expected["user"]), strict=True):
        require(message.get("type") == "message" and message.get("role") == role, "Changed native message role")
        require(message.get("content") == [{"type": "input_text", "text": text}], "Changed or added prompt content")
        require(set(message) == {"type", "id", "role", "content", "internal_chat_message_metadata_passthrough"},
                "Unexpected message fields")
        require(isinstance(message["id"], str) and message["id"], "Missing native message ID")
    require(body.get("model") == "gpt-6-luna", "Changed request model")
    require(body.get("reasoning") == {"effort": "medium", "context": "all_turns"}, "Changed reasoning effort")
    require(body.get("text", {}).get("format") == {"type": "json_schema", "strict": True,
            "schema": expected["schema"], "name": "codex_output_schema"}, "Changed output schema")
    require(set(body["text"]) <= {"format", "verbosity"}, "Extra output instructions")
    require(body.get("tool_choice") == "auto" and body.get("parallel_tool_calls") is False, "Changed tool routing")
    require(body.get("stream") is True and body.get("store") is False, "Changed request lifecycle")
    require(body.get("include") == ["reasoning.encrypted_content"], "Unexpected included data")
    metadata = body.get("client_metadata")
    require(isinstance(metadata, dict) and all(isinstance(metadata.get(k), str) and metadata[k]
            for k in ("thread_id", "turn_id", "session_id")), "Missing native attribution IDs")


def assert_thread(thread, requirements):
    require(thread.get("instructionSources") == [], "Native loaded instruction sources")
    require(thread.get("model") == "gpt-6-luna" and thread.get("modelProvider") == "openai", "Changed native model/provider")
    require(thread.get("reasoningEffort") == "medium", "Changed native effort")
    view = thread["thread"]
    require(view.get("cliVersion") == "0.164.0", "Native runtime version changed")
    require(view.get("model") == "gpt-6-luna" and view.get("modelProvider") == "openai" and
            view.get("reasoningEffort") == "medium", "Changed thread model/provider/effort")
    require(view.get("forkedFromId") is None and view.get("parentThreadId") is None, "Native thread inherited history")
    require(view.get("ephemeral") is True and view.get("turns") == [] and view.get("environments") == [], "Native loaded history or environments")
    require(thread.get("runtimeWorkspaceRoots") == [], "Native loaded workspace roots")
    require("requirements" in requirements, "Missing requirements echo")
    req = requirements["requirements"]
    require(req is None or (isinstance(req, dict) and "additionalDeveloperInstructions" in req and
            req["additionalDeveloperInstructions"] in (None, "")), "Requirements added developer instructions")


def contained(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative,
            "Invalid evidence relative path")
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    require(not posix.is_absolute() and not windows.drive and ".." not in posix.parts,
            "Evidence reference escaped owned root")
    target = root.joinpath(*posix.parts)
    require(target.resolve().is_relative_to(root.resolve()), "Evidence symlink escaped owned root")
    for parent in [target, *target.parents]:
        if parent == root.parent:
            break
        require(not parent.is_symlink(), "Evidence symlink is not allowed")
    return target


def captured_requests(trace):
    captures = []
    require(not trace.is_symlink(), "Trace root symlink is not allowed")
    files = list(trace.rglob("*"))
    require(len(files) < 512, "Trace file count exceeded")
    require(not any(p.is_symlink() for p in files), "Trace symlink is not allowed")
    total = 0
    for spine in sorted(trace.rglob("trace.jsonl")):
        raw = read_bytes(spine)
        total += len(raw)
        require(total < 12_000_000, "Trace byte cap exceeded")
        for line in raw.splitlines():
            event = load_json_bytes(line)
            payload = event.get("payload", {})
            if payload.get("type") != "inference_started":
                continue
            path = contained(spine.parent, payload["request_payload"]["path"])
            require(path.resolve().is_relative_to(trace.resolve()), "Capture escaped trace")
            request = read_bytes(path)
            total += len(request)
            require(total < 12_000_000 and len(captures) < 16, "Capture count or byte cap exceeded")
            wrapped = load_json_bytes(request)
            require(isinstance(wrapped, dict), "Trace payload is not an object")
            require("body" not in wrapped or not ({"model", "input"} & set(wrapped)), "Ambiguous trace body wrapper")
            body = wrapped.get("body", wrapped)
            if isinstance(body, str):
                body = load_json_bytes(body.encode())
            require(isinstance(body, dict), "Trace body is not an object")
            captures.append({"path": path.relative_to(trace).as_posix(), "sha256": digest(request),
                             "event": event, "body": body})
    return captures


class Deadline:
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    def remaining(self, cap=None):
        remaining = self.end - time.monotonic()
        require(remaining > 0, "Finite run deadline exceeded")
        return min(remaining, cap) if cap is not None else remaining


class WindowsJob:
    """Assign suspended children before any native code runs; close kills descendants."""
    def __init__(self):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [("user", ctypes.c_int64), ("job", ctypes.c_int64), ("flags", w.DWORD),
                        ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("read", "write", "other", "readBytes", "writeBytes", "otherBytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("processMemory", ctypes.c_size_t),
                        ("jobMemory", ctypes.c_size_t), ("peakProcess", ctypes.c_size_t), ("peakJob", ctypes.c_size_t)]
        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in ("user", "kernel", "periodUser", "periodKernel")] + [
                (name, w.DWORD) for name in ("faults", "total", "active", "terminated")]
        self.accounting = Accounting
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
        self.api.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        require(bool(self.handle), "CreateJobObject failed")
        limits = Extended()
        limits.basic.flags = 0x2000
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.api.CloseHandle(self.handle)
            raise Rejected("KILL_ON_JOB_CLOSE could not be enforced")

    def attach_resume(self, process):
        require(bool(self.api.AssignProcessToJobObject(self.handle, int(process._handle))), "Job Object assignment failed")
        native = ctypes.WinDLL("ntdll")
        native.NtResumeProcess.argtypes = [ctypes.c_void_p]
        native.NtResumeProcess.restype = ctypes.c_long
        require(native.NtResumeProcess(int(process._handle)) >= 0, "Suspended child could not resume")

    def active(self):
        value = self.accounting()
        require(bool(self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(value), ctypes.sizeof(value), None)),
                "Cannot query owned process Job Object")
        return value.active

    def close(self):
        try:
            require(bool(self.api.TerminateJobObject(self.handle, 1)), "Cannot terminate owned Job Object")
            end = time.monotonic() + 3
            while self.active() and time.monotonic() < end:
                time.sleep(0.02)
            require(self.active() == 0, "Owned Windows process tree remains")
        finally:
            self.api.CloseHandle(self.handle)


class OwnedProcess:
    def __init__(self, argv, cwd, env):
        self.job = WindowsJob() if sys.platform == "win32" else None
        self.argv = argv
        options = {"start_new_session": True} if not self.job else {
            "creationflags": 0x4 | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
        self.process = None
        try:
            self.process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, bufsize=0, **options)
            if self.job:
                self.job.attach_resume(self.process)
        except BaseException:
            if self.process:
                self.process.kill()
                self.process.wait(timeout=3)
            if self.job:
                self.job.close()
            raise

    def close(self):
        process, actions = self.process, []
        try:
            process.stdin.close()
            actions.append("stdin EOF")
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        if self.job:
            self.job.close()
            actions.append("terminate owned Job Object and confirm active processes zero")
        else:
            def group_present():
                try:
                    os.killpg(process.pid, 0)
                    return True
                except ProcessLookupError:
                    return False
                except PermissionError:
                    return True
            for sig, delay in ((signal.SIGINT, 1), (signal.SIGTERM, 1), (signal.SIGKILL, 2)):
                if not group_present():
                    break
                try:
                    os.killpg(process.pid, sig)
                    actions.append(signal.Signals(sig).name + " to owned process group")
                except ProcessLookupError:
                    break
                except PermissionError:
                    actions.append("signal permission denied; group must still disappear before acceptance")
                try:
                    process.wait(timeout=delay)
                except subprocess.TimeoutExpired:
                    pass
                end = time.monotonic() + delay
                while time.monotonic() < end and group_present():
                    time.sleep(0.02)
            require(not group_present(), "Owned process group remains or cannot be inspected")
        process.wait(timeout=3)
        return {"pid": process.pid, "exitCode": process.returncode, "actions": actions, "ownedTreeAbsent": True}


class Pipes:
    def __init__(self, owned, directory, rpc=False):
        self.owned, self.directory, self.rpc = owned, directory, rpc
        self.incoming, self.errors = queue.Queue(maxsize=256), []
        self.writes = queue.Queue(maxsize=1)
        self.threads = [threading.Thread(target=self.read, args=(name,), daemon=True) for name in ("stdout", "stderr")]
        self.threads.append(threading.Thread(target=self.write, daemon=True))
        for thread in self.threads:
            thread.start()

    def read(self, name):
        try:
            stream, total = getattr(self.owned.process, name), 0
            filename = "rpc-received.jsonl" if name == "stdout" and self.rpc else name + ".txt"
            with (self.directory / filename).open("wb") as saved:
                while True:
                    chunk = stream.readline(MAX_LINE + 1) if self.rpc and name == "stdout" else stream.read(4096)
                    if not chunk:
                        break
                    total += len(chunk)
                    require(total <= MAX_STREAM and len(chunk) <= MAX_LINE, "Native stdio byte or line cap exceeded")
                    saved.write(chunk)
                    saved.flush()
                    if self.rpc and name == "stdout":
                        self.incoming.put_nowait(load_json_bytes(chunk))
        except BaseException as error:
            self.errors.append(str(error) or type(error).__name__)

    def write(self):
        try:
            while True:
                item = self.writes.get()
                if item is None:
                    return
                data, ack = item
                pending = memoryview(data)
                while pending:
                    count = self.owned.process.stdin.write(pending)
                    if not count:
                        raise BrokenPipeError("Native stdin closed")
                    pending = pending[count:]
                self.owned.process.stdin.flush()
                ack.set()
        except (OSError, ValueError) as error:
            self.errors.append(str(error))

    def check(self):
        require(not self.errors, "Native pipe failure " + "; ".join(self.errors))

    def send_bytes(self, data, deadline):
        require(len(data) <= 64_000, "Outgoing stdio byte cap exceeded")
        ack = threading.Event()
        self.writes.put((data, ack), timeout=deadline.remaining(3))
        require(ack.wait(deadline.remaining(3)), "Native stdin deadline exceeded")
        self.check()

    def close(self):
        try:
            self.writes.put_nowait(None)
        except queue.Full:
            pass
        try:
            cleanup = self.owned.close()
        finally:
            for thread in self.threads:
                thread.join(timeout=2)
            self.owned.process.stdout.close()
            self.owned.process.stderr.close()
        require(not any(t.is_alive() for t in self.threads), "Owned stdio threads remain")
        cleanup["stdioThreadsFinished"] = True
        cleanup["pipeErrors"] = list(self.errors)
        return cleanup


def command(argv, paths, env, directory, deadline, input_data=None):
    directory.mkdir(mode=0o700)
    owned = OwnedProcess(argv, paths["cwd"], env)
    pipes = Pipes(owned, directory)
    result = {"argv": argv}
    try:
        if input_data:
            pipes.send_bytes(input_data, deadline)
        owned.process.stdin.close()
        while owned.process.poll() is None:
            pipes.check()
            time.sleep(min(0.03, deadline.remaining()))
        result["exitCode"] = owned.process.returncode
    finally:
        try:
            result["cleanup"] = pipes.close()
        except Exception as error:
            result["cleanupError"] = str(error)
            raise
        finally:
            save(directory / "command.json", result)
    require(not result["cleanup"]["pipeErrors"], "Helper pipe failure; see " + str(directory))
    require(result["exitCode"] == 0, "Helper command failed; see " + str(directory))
    return read_bytes(directory / "stdout.txt")


def private_environment(directory):
    paths = {name: directory / name for name in ("home", "codex-home", "tmp", "cwd", "trace", "xdg-config", "xdg-data", "xdg-cache", "xdg-state", "xdg-runtime")}
    for path in paths.values():
        path.mkdir(mode=0o700)
    env = {"HOME": str(paths["home"]), "CODEX_HOME": str(paths["codex-home"]),
           "TMPDIR": str(paths["tmp"]), "TMP": str(paths["tmp"]), "TEMP": str(paths["tmp"]),
           "CODEX_ROLLOUT_TRACE_ROOT": str(paths["trace"]), "LANG": "en_US.UTF-8",
           "RUST_LOG": "info", "NO_COLOR": "1", "CLICOLOR": "0"}
    for key, name in (("XDG_CONFIG_HOME", "xdg-config"), ("XDG_DATA_HOME", "xdg-data"),
                      ("XDG_CACHE_HOME", "xdg-cache"), ("XDG_STATE_HOME", "xdg-state"), ("XDG_RUNTIME_DIR", "xdg-runtime")):
        env[key] = str(paths[name])
    if sys.platform == "win32":
        root = next((v for k, v in os.environ.items() if k.lower() == "systemroot"), "")
        require(Path(root).is_absolute() and Path(root).is_dir(), "Missing trusted Windows SystemRoot")
        env.update({"SystemRoot": root, "windir": root, "SystemDrive": os.path.splitdrive(root)[0],
                    "USERPROFILE": str(paths["home"]), "APPDATA": str(paths["home"] / "AppData" / "Roaming"),
                    "LOCALAPPDATA": str(paths["home"] / "AppData" / "Local"), "ProgramData": str(paths["home"] / "ProgramData"),
                    "USERNAME": "native-check", "USERDOMAIN": "NATIVE_CHECK", "COMPUTERNAME": "NATIVE_CHECK",
                    "OS": "Windows_NT", "PATH": str(Path(root) / "System32") + ";" + root})
        for key in ("APPDATA", "LOCALAPPDATA", "ProgramData"):
            Path(env[key]).mkdir(parents=True, mode=0o700)
    else:
        env.update({"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "USER": "native-check", "LOGNAME": "native-check"})
    save(directory / "environment.json", env)
    return paths, env


BRIDGE = """
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
if (Number(process.versions.node.split('.')[0]) < 24) throw new Error('Node 24+ required');
const q = JSON.parse(fs.readFileSync(0, 'utf8'));
const c = await import(pathToFileURL(q.repo + '/desktop/src/main/codex/config.ts'));
const { bundledRuntime } = await import(pathToFileURL(q.repo + '/desktop/src/main/codex/binary.ts'));
const r = await bundledRuntime(q.executable ? {executable:q.executable} : {})({resourcesDir:q.resources}, process.platform, process.arch);
console.log(JSON.stringify({config:c.processConfig(q.catalog), initialize:c.initializeParams('0.1.0'),
  thread:c.threadParams(q.cwd,q.expected.system), turn:c.turnParams('$THREAD',q.expected),
  args:c.RUNTIME_ARGS, contextFingerprint:c.CODEX_CONTEXT_FINGERPRINT, model:c.MODEL, effort:c.EFFORT,
  runtime:{executable:r.executable, sha256:r.sha256}, catalogSha256:(await import('node:crypto')).createHash('sha256').update(r.catalog).digest('hex'),
  nodeVersion:process.version}));
"""


def builder(args, paths, env, directory, expected, deadline):
    request = {"repo": str(REPO), "resources": str(args.resources_dir), "executable": args.executable,
               "catalog": str(paths["codex-home"] / "luna-models.json"), "cwd": str(paths["cwd"]), "expected": expected}
    argv = [args.node, "--experimental-strip-types", "--disable-warning=MODULE_TYPELESS_PACKAGE_JSON",
            "--import", str(REPO / "desktop/scripts/register-ts.mjs"), "--input-type=module", "--eval", BRIDGE]
    value = load_json_bytes(command(argv, paths, env, directory / "builder", deadline, canonical(request)))
    require(value["contextFingerprint"] == CONTEXT_SHA, "Adapter context fingerprint changed")
    require(value["model"] == "gpt-6-luna" and value["effort"] == "medium", "Builder changed model or effort")
    require(value["catalogSha256"] == CATALOG_SHA, "Bundled catalog changed")
    key = native_key()
    require(value["runtime"]["sha256"] == RUNTIME_SHA[key], "Bundled runtime hash changed")
    require(sha(value["runtime"]["executable"]) == RUNTIME_SHA[key], "Executable bytes changed")
    save(directory / "builder.json", value)
    return value


def native_key():
    machine = platform.machine().lower()
    key = sys.platform + "-" + ({"arm64": "arm64", "aarch64": "arm64", "amd64": "x64", "x86_64": "x64"}.get(machine, machine))
    require(key in RUNTIME_SHA, "Native run requires darwin-arm64 or win32-x64; simulation is not acceptance")
    return key


def firewall_preflight(rule, executable, paths, env, directory, deadline):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_OS") == "Windows",
            "Windows native run is restricted to the parent's disposable GitHub runner")
    require(rule and re.fullmatch(r"BatatisNativeCodex-[A-Za-z0-9-]{1,100}", rule), "Explicit scoped Windows firewall rule required")
    quoted = lambda value: "'" + value.replace("'", "''") + "'"
    script = """
$ErrorActionPreference='Stop'
if ((Get-Service MpsSvc).Status -ne 'Running') { throw 'Windows Firewall service not running' }
$profiles=@(Get-NetFirewallProfile -PolicyStore ActiveStore)
if ($profiles.Count -ne 3 -or @($profiles | Where-Object { $_.Enabled -ne $true }).Count) { throw 'All firewall profiles must already be enabled' }
$r=@(Get-NetFirewallRule -PolicyStore ActiveStore -Name RULE)
if ($r.Count -ne 1 -or $r[0].Enabled -ne 'True' -or $r[0].Direction -ne 'Outbound' -or $r[0].Action -ne 'Block' -or $r[0].Profile -ne 'Any') { throw 'Effective outbound block rule missing' }
$app=@($r | Get-NetFirewallApplicationFilter)
if ($app.Count -ne 1 -or -not [string]::Equals($app[0].Program, PROGRAM, [StringComparison]::OrdinalIgnoreCase)) { throw 'Firewall program path mismatch' }
$port=$r | Get-NetFirewallPortFilter
$address=$r | Get-NetFirewallAddressFilter
if ($port.Protocol -ne 'Any' -or $port.LocalPort -ne 'Any' -or $port.RemotePort -ne 'Any' -or $address.LocalAddress -ne 'Any' -or $address.RemoteAddress -ne 'Any') { throw 'Firewall rule is narrower than all outbound endpoints' }
@{rule=$r[0].Name;program=$app[0].Program;profilesEnabled=$true;outboundProgramBlock=$true;scope='Windows Firewall program rule; loopback exemptions and other programs are not universally denied'} | ConvertTo-Json -Compress
""".replace("RULE", quoted(rule)).replace("PROGRAM", quoted(executable))
    powershell = str(Path(env["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
    return load_json_bytes(command([powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                                   paths, env, directory, deadline))


class Rpc:
    def __init__(self, owned, directory, deadline):
        self.pipes = Pipes(owned, directory, rpc=True)
        self.deadline, self.counter = deadline, 0
        self.sent = (directory / "rpc-sent.jsonl").open("wb")

    def send(self, method, params=None, notification=False):
        require(method in METHODS, "Forbidden RPC method")
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notification:
            self.counter += 1
            message["id"] = self.counter
        wire = canonical(message) + b"\n"
        self.sent.write(wire)
        self.sent.flush()
        self.pipes.send_bytes(wire, self.deadline)
        return message.get("id")

    def receive(self, timeout):
        self.pipes.check()
        message = self.pipes.incoming.get(timeout=min(timeout, self.deadline.remaining()))
        require(not ("method" in message and "id" in message), "Unexpected native server request")
        require(not message.get("method", "").startswith("account/"), "Unexpected account flow")
        require(not message.get("method", "").startswith("item/agentMessage"), "Unexpected successful model response")
        return message

    def call(self, method, params, cap=10):
        ident = self.send(method, params)
        end = time.monotonic() + self.deadline.remaining(cap)
        while time.monotonic() < end:
            try:
                message = self.receive(min(0.1, end - time.monotonic()))
            except queue.Empty:
                require(self.pipes.owned.process.poll() is None, "Native exited before RPC reply")
                continue
            if message.get("id") == ident:
                require("error" not in message, "Native rejected " + method + "; see RPC transcript")
                return message["result"]
        raise Rejected("RPC deadline exceeded " + method)

    def close(self):
        try:
            return self.pipes.close()
        finally:
            self.sent.close()


def effective_features(directory, config, key):
    stderr = read_bytes(directory / "stderr.txt", MAX_STREAM).decode("utf-8", errors="strict")
    stderr = re.sub(r"\x1b\[[0-9;]*m", "", stderr)
    require(not re.search(r"auth[._]header_attached=true", stderr), "Native attached an auth header")
    rows = []
    for line in stderr.splitlines():
        if "tags_json=" in line:
            data, _ = json.JSONDecoder().raw_decode(line.split("tags_json=", 1)[1])
            rows.append({k.removeprefix("feature."): v for k, v in data.items() if k.startswith("feature.")})
    require(rows, "Missing native effective feature telemetry")
    observed, absent = {}, []
    for name, value in config["features"].items():
        if name not in rows[-1]:
            absent.append(name)
            continue
        expected = value["enabled"] if isinstance(value, dict) else value
        require(rows[-1][name] == str(expected).lower(), "Native effective feature changed " + name)
        observed[name] = rows[-1][name]
    require(set(absent) <= {"multi_agent", "memory_tool"}, "Unobserved effective feature flags")
    denied = "Operation not permitted (os error 1)" in stderr
    if key == "darwin-arm64":
        require(denied, "Missing native sandbox network denial")
    return {"observed": observed, "aliasesNotSeparatelyLogged": absent,
            "authHeaderAttachedFalseObserved": bool(re.search(r"auth[._]header_attached=false", stderr)),
            "osError1Observed": denied, "loggedUrls": sorted(set(re.findall(r'(?:https?|wss?)://[^\s\"<>]+', stderr)))}


def validate_case(directory, result, key):
    require(not result.get("error"), result.get("error", "Native case failed"))
    expected = load(directory / "expected.json")
    require(expected == result["expected"], "Saved synthetic inputs changed")
    require(expected == synthetic_inputs(expected["sentinel"]), "Case is not the fixed synthetic request")
    config = tomllib.loads(read_bytes(directory / "codex-home/config.toml").decode())
    require(config["openai_base_url"] == "http://127.0.0.1:0/v1" and config["cli_auth_credentials_store"] == "ephemeral",
            "No-auth dead endpoint overrides changed")
    require(digest(canonical(assembly_config(config))) == ASSEMBLY_SHA, "Effective config fingerprint changed")
    spec = load(directory / "builder.json")
    require(spec["contextFingerprint"] == CONTEXT_SHA and spec["runtime"] == result["runtime"], "Recorded builder fingerprints changed")
    production_config = tomllib.loads(spec["config"])
    expected_config = probe_config(spec["config"], Path(production_config["model_catalog_json"]))
    require(config == tomllib.loads(expected_config), "Effective config differs from actual builder")
    require(sha(directory / "codex-home/config.toml") == result["configSha256"], "Config bytes differ from report")
    captures = captured_requests(directory / "trace")
    require(captures, "No native request bytes captured")
    thread = result["threadStart"]
    assert_thread(thread, result["requirements"])
    inventories, rejections = [], []
    for capture in captures:
        body = capture["body"]
        inventories.append(tool_names(body))
        if result["case"] != "stock-control":
            assert_candidate(body, expected)
        else:
            try:
                assert_candidate(body, expected)
            except Rejected as error:
                rejections.append(str(error))
            else:
                raise Rejected("Candidate gate accepted the stock control")
        require(body["client_metadata"]["thread_id"] == thread["thread"]["id"], "Trace thread attribution changed")
    if result["case"] == "stock-control":
        require(all(sorted(names) == sorted(STOCK_TOOLS) for names in inventories),
                "Stock tool inventory differs from the pinned eight tools")
    sent = [load_json_bytes(line) for line in read_bytes(directory / "rpc-sent.jsonl", MAX_STREAM).splitlines()]
    require(all(row["method"] in METHODS for row in sent), "Unexpected sent RPC method")
    calls = {row["method"]: row.get("params") for row in sent}
    for method in ("initialize", "initialized", "configRequirements/read", "thread/start", "turn/start"):
        require(sum(row["method"] == method for row in sent) == 1, "Missing or repeated native method " + method)
    require(calls["initialize"] == spec["initialize"] and calls["thread/start"] == spec["thread"] and
            calls["turn/start"] == {**spec["turn"], "threadId": thread["thread"]["id"]}, "Sent RPC differs from actual builders")
    require(thread["cwd"] == spec["thread"]["cwd"] and thread["thread"]["cwd"] == thread["cwd"], "Native cwd echo changed")
    received = [load_json_bytes(line) for line in read_bytes(directory / "rpc-received.jsonl", MAX_STREAM).splitlines()]
    require(not any(row.get("method", "").startswith(("account/", "item/agentMessage")) for row in received),
            "Unexpected auth flow or successful model response")
    require(not any("id" in row and "method" in row for row in received), "Native issued a server request")
    require(not any(p.name.lower() == "auth.json" for p in directory.rglob("*")), "Unexpected credential artifact")
    require(result["cleanup"]["ownedTreeAbsent"] and result["cleanup"]["stdioThreadsFinished"], "Native cleanup incomplete")
    require(not result["cleanup"]["pipeErrors"], "Native stdio failed")
    result["captures"] = [{k: v for k, v in c.items() if k != "body"} for c in captures]
    result["toolInventories"], result["stockRejections"] = inventories, rejections
    result["effectiveFeatures"] = effective_features(directory, config, key)
    result["status"] = "VERIFIED"
    return captures


def synthetic_inputs(sentinel):
    require(isinstance(sentinel, str) and re.fullmatch(r"[0-9a-f]{32}", sentinel), "Invalid synthetic sentinel")
    return {"system": "BATATIS_NATIVE_SYSTEM_" + sentinel, "user": "BATATIS_NATIVE_USER_" + sentinel,
            "schema": {"type": "object", "properties": {"probe": {"type": "string", "const": sentinel}},
                       "required": ["probe"], "additionalProperties": False}, "sentinel": sentinel}


def run_case(args, run, name, deadline, profile):
    directory = run / name
    directory.mkdir(mode=0o700)
    paths, env = private_environment(directory)
    expected = synthetic_inputs(uuid.uuid4().hex)
    save(directory / "expected.json", expected)
    result = {"case": name, "expected": expected, "status": "FAILED"}
    rpc = None
    try:
        spec = builder(args, paths, env, directory, expected, deadline)
        result["runtime"] = spec["runtime"]
        catalog_path = paths["codex-home"] / "luna-models.json"
        resource = args.resources_dir / "codex/luna-models.json"
        if not resource.is_file():
            resource = args.resources_dir / "desktop/codex/luna-models.json"
        candidate = read_bytes(resource)
        require(digest(candidate) == CATALOG_SHA, "Actual resource catalog changed")
        catalog_path.write_bytes(control_catalog(candidate) if name == "stock-control" else candidate)
        config = probe_config(spec["config"], catalog_path)
        (paths["codex-home"] / "config.toml").write_text(config, encoding="utf-8", newline="\n")
        result["catalogSha256"], result["configSha256"] = sha(catalog_path), digest(config.encode())
        result["assemblyConfigSha256"] = ASSEMBLY_SHA
        executable = spec["runtime"]["executable"]
        if sys.platform == "win32":
            result["firewallBefore"] = firewall_preflight(args.windows_firewall_rule, executable, paths, env,
                                                         directory / "firewall-before", deadline)
        argv = [executable, *spec["args"]]
        if sys.platform == "darwin":
            argv = ["/usr/bin/sandbox-exec", "-f", str(profile), *argv]
        result["argv"] = argv
        rpc = Rpc(OwnedProcess(argv, paths["cwd"], env), directory, deadline)
        result["initialize"] = rpc.call("initialize", spec["initialize"])
        rpc.send("initialized", notification=True)
        result["requirements"] = rpc.call("configRequirements/read", {})
        models, cursor = [], None
        for _ in range(4):
            params = {"limit": 100, "includeHidden": True}
            if cursor:
                params["cursor"] = cursor
            page = rpc.call("model/list", params)
            models.extend(page["data"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        require(not cursor and len(models) < 400 and any(m.get("model") == "gpt-6-luna" for m in models), "Pinned native model unavailable")
        result["models"] = models
        result["threadStart"] = rpc.call("thread/start", spec["thread"])
        assert_thread(result["threadStart"], result["requirements"])
        thread_id = result["threadStart"]["thread"]["id"]
        turn_params = {**spec["turn"], "threadId": thread_id}
        result["turnStart"] = rpc.call("turn/start", turn_params)
        end = time.monotonic() + deadline.remaining(16)
        while time.monotonic() < end:
            try:
                message = rpc.receive(0.1)
                if message.get("method") == "turn/completed":
                    result["turnCompleted"] = message
                    break
            except queue.Empty:
                pass
            try:
                if captured_requests(paths["trace"]):
                    break
            except (json.JSONDecodeError, UnicodeError):
                pass
        if not result.get("turnCompleted"):
            result["interrupt"] = rpc.call("turn/interrupt", {"threadId": thread_id, "turnId": result["turnStart"]["turn"]["id"]}, 5)
    except Exception as error:
        result["error"] = str(error)
    finally:
        if rpc:
            try:
                result["cleanup"] = rpc.close()
            except Exception as error:
                result["error"] = "Cleanup failed " + str(error)
        try:
            if sys.platform == "win32" and result.get("runtime"):
                result["firewallAfter"] = firewall_preflight(args.windows_firewall_rule, result["runtime"]["executable"],
                                                            paths, env, directory / "firewall-after", deadline)
            validate_case(directory, result, native_key())
        except Exception as error:
            result["error"] = str(error)
            result["status"] = "FAILED"
        save(directory / "result.json", result)
    return result


def write_manifest(run):
    entries = {}
    for path in sorted(run.rglob("*")):
        require(not path.is_symlink(), "Run contains a symlink")
        if path.is_file() and path.name != "artifact-manifest.json":
            entries[path.relative_to(run).as_posix()] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    save(run / "artifact-manifest.json", entries)
    return sha(run / "artifact-manifest.json")


def replay(run, manifest_sha=None):
    sources = checked_sources()
    if manifest_sha:
        require(sha(run / "artifact-manifest.json") == manifest_sha, "Run manifest digest changed")
    manifest = load(run / "artifact-manifest.json")
    require(len(manifest) < 2048, "Manifest file count exceeded")
    for relative, metadata in manifest.items():
        path = contained(run, relative)
        require(path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"], "Evidence artifact changed " + relative)
    summary = load(run / "summary.json")
    require(summary["status"] == "VERIFIED" and summary["platform"] in RUNTIME_SHA, "Native run did not pass")
    require(summary["harnessSha256"] == sha(Path(__file__)), "Checker changed since capture; run native acceptance again")
    require(summary["controlFixtureSha256"] == sha(Path(__file__).with_name("native-control.json")), "Control fixture changed since capture")
    require({p: v["lfSha256"] for p, v in sources.items()} ==
            {p: v["lfSha256"] for p, v in summary["sourceFingerprints"].items()}, "Builder source changed since capture")
    require([r["case"] for r in summary["cases"]] == list(CASES), "Required fresh candidates/control missing")
    seen_threads, seen_sentinels, bodies = set(), set(), []
    for result in summary["cases"]:
        directory = run / result["case"]
        require(result == load(directory / "result.json"), "Case report differs from summary")
        require(result["runtime"]["sha256"] == RUNTIME_SHA[summary["platform"]], "Recorded runtime pin changed")
        require(result["catalogSha256"] == sha(directory / "codex-home/luna-models.json"), "Saved catalog changed")
        if result["case"] != "stock-control":
            require(result["catalogSha256"] == CATALOG_SHA, "Candidate catalog pin changed")
        saved = result.get("captures")
        captures = validate_case(directory, result, summary["platform"])
        require(saved == result["captures"], "Captured raw bytes differ from report")
        thread = result["threadStart"]["thread"]["id"]
        sentinel = result["expected"]["sentinel"]
        require(thread not in seen_threads and sentinel not in seen_sentinels, "Cases reused a native thread or synthetic input")
        seen_threads.add(thread)
        seen_sentinels.add(sentinel)
        bodies.append(canonical([capture["body"] for capture in captures]))
    for i, result in enumerate(summary["cases"]):
        require(all(result["expected"]["sentinel"].encode() not in body for j, body in enumerate(bodies) if i != j), "Cross-case context leaked")
    return {"status": "VERIFIED", "platform": summary["platform"], "cases": list(CASES),
            "manifestSha256": sha(run / "artifact-manifest.json"), "mode": "offline-byte-replay"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources-dir", type=Path, default=REPO)
    parser.add_argument("--executable", help="Trusted CLI-only override; exact native executable digest still required")
    parser.add_argument("--node", default=shutil.which("node"), help="Absolute Node 24+ executable")
    parser.add_argument("--output", type=Path, help="New owned artifact directory, outside application sources")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--verify-control-source", type=Path, help="Offline provenance check of six original metadata values")
    parser.add_argument("--windows-firewall-rule")
    parser.add_argument("--deadline-seconds", type=int, default=150, choices=range(30, 301), metavar="30..300")
    args = parser.parse_args()
    if args.verify_control_source:
        verify_control_source(args.verify_control_source)
        print(json.dumps({"status": "VERIFIED", "sourceSha256": SOURCE_SHA, "fields": 6}))
        return
    if args.replay:
        print(json.dumps(replay(args.replay.resolve(), args.manifest_sha256)))
        return
    require(args.output is not None and args.node is not None, "--output and Node 24+ are required")
    key = native_key()
    sources = checked_sources()
    args.resources_dir = args.resources_dir.resolve(strict=True)
    args.node = str(Path(args.node).resolve(strict=True))
    if args.executable:
        args.executable = str(Path(args.executable).resolve(strict=True))
    run = args.output.resolve()
    require(not run.is_relative_to(REPO), "Generated evidence must be outside the source checkout")
    run.mkdir(parents=True, mode=0o700, exist_ok=False)
    deadline = Deadline(args.deadline_seconds - 25)
    profile = run / "network-deny.sb"
    profile.write_text(NETWORK_PROFILE, encoding="utf-8")
    summary = {"status": "FAILED", "platform": key, "startedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
               "sourceFingerprints": sources, "harnessSha256": sha(Path(__file__)), "controlFixtureSha256": sha(Path(__file__).with_name("native-control.json")),
               "resourcesDir": str(args.resources_dir), "deadlineSeconds": args.deadline_seconds, "cases": [],
               "cleanupReserveSeconds": 25,
               "scope": "Native no-auth request boundary only; no auth, entitlement, successful inference, accuracy or universal internal deny-list proof"}
    try:
        preflight = run / "preflight"
        preflight.mkdir(mode=0o700)
        paths, env = private_environment(preflight)
        if key == "darwin-arm64":
            check = "import socket,json; s=socket.socket(); r=s.connect_ex(('127.0.0.1',0)); print(json.dumps({'connect_errno':r})); assert r==1,r"
            summary["networkPreflight"] = load_json_bytes(command(["/usr/bin/sandbox-exec", "-f", str(profile), sys.executable, "-B", "-c", check],
                                                                  paths, env, preflight / "network", deadline))
        for name in CASES:
            result = run_case(args, run, name, deadline, profile)
            summary["cases"].append(result)
            print(json.dumps({"case": name, "status": result["status"], "error": result.get("error"),
                              "captures": len(result.get("captures", [])), "cleanup": result.get("cleanup")}), flush=True)
            require(result["status"] == "VERIFIED", "Native case failed " + name)
        require(checked_sources() == sources, "Adapter source bytes changed during the run")
        for row in summary["cases"]:
            require(sha(row["runtime"]["executable"]) == RUNTIME_SHA[key], "Runtime changed during execution")
        summary["status"] = "VERIFIED"
    except Exception as error:
        summary["error"] = str(error)
    finally:
        summary["finishedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save(run / "summary.json", summary)
        manifest = write_manifest(run)
    require(summary["status"] == "VERIFIED", summary.get("error", "Native acceptance failed"))
    replay(run, manifest)
    print(json.dumps({"status": "VERIFIED", "platform": key, "output": str(run), "manifestSha256": manifest,
                      "windowsNativeExecuted": key == "win32-x64", "productionGateEnabled": False}), flush=True)


if __name__ == "__main__":
    def interrupted(signum, frame):
        signal.signal(signum, signal.SIG_IGN)
        raise KeyboardInterrupt("Interrupted; cleaning owned subprocesses")
    for stopping_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(stopping_signal, interrupted)
    try:
        main()
    except KeyboardInterrupt as error:
        print(json.dumps({"status": "FAILED", "error": str(error)}), file=sys.stderr)
        sys.exit(130)
    except (Rejected, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "FAILED", "error": str(error)}), file=sys.stderr)
        sys.exit(1)
