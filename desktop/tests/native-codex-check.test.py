"""Behavioral tests against saved real native bytes, with no Codex or provider calls.

python3 -B desktop/tests/native-codex-check.test.py --proof-root <native-probe> --scratch <external directory>
Add --saved-run <native-check output> to exercise full manifest replay and tampering.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("native_check", REPO / "desktop/codex/native-check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class NativeCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = OPTIONS.proof_root / "artifact-manifest.json"
        if check.sha(manifest) != "552f9b2ccbf9a9edd61122b75c7876e0ae18a388c14032eae265fbe21066fcdb":
            raise RuntimeError("Original native proof manifest changed")
        entries = {row["path"]: row for row in check.load(manifest)["added_files"]}
        summary_path = OPTIONS.proof_root / "runs/20261025T190515Z-c824cb3e/summary.json"
        relative = summary_path.relative_to(OPTIONS.proof_root).as_posix()
        if check.sha(summary_path) != entries[relative]["sha256"]:
            raise RuntimeError("Original native summary changed")
        cls.original = check.load(summary_path)
        cls.bodies = []
        for row in cls.original:
            capture = row["trace_events"][0]
            path = Path(capture["request_path"])
            relative = path.relative_to(OPTIONS.proof_root).as_posix()
            if check.sha(path) != entries[relative]["sha256"]:
                raise RuntimeError("Original captured request bytes changed")
            raw = check.load(path)
            cls.bodies.append(raw.get("body", raw))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native-check-test-", dir=OPTIONS.scratch)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def reject_body(self, mutate):
        body = copy.deepcopy(self.bodies[0])
        mutate(body)
        with self.assertRaises(check.Rejected):
            check.assert_candidate(body, self.original[0]["expected"])

    def test_two_actual_native_candidate_requests_pass(self):
        for body, row in zip(self.bodies[:2], self.original[:2], strict=True):
            check.assert_candidate(body, row["expected"])
        self.assertNotEqual(self.bodies[0]["client_metadata"]["thread_id"], self.bodies[1]["client_metadata"]["thread_id"])

    def test_actual_stock_eight_tool_request_is_rejected(self):
        self.assertEqual(len(check.tool_names(self.bodies[2])), 8)
        self.assertIn("functions.exec", check.tool_names(self.bodies[2]))
        with self.assertRaises(check.Rejected):
            check.assert_candidate(self.bodies[2], self.original[2]["expected"])

    def copied_stock_case(self):
        if not OPTIONS.saved_run:
            self.skipTest("Add --saved-run for stock control acceptance regressions")
        summary = check.load(OPTIONS.saved_run / "summary.json")
        result = copy.deepcopy(next(row for row in summary["cases"] if row["case"] == "stock-control"))
        directory = self.directory / "stock-control"
        shutil.copytree(OPTIONS.saved_run / "stock-control", directory)
        check.validate_case(directory, result, summary["platform"])
        return directory, result, summary["platform"]

    def reject_stock_inventory(self, mutate):
        directory, result, platform_key = self.copied_stock_case()
        for capture in check.captured_requests(directory / "trace"):
            payload = directory / "trace" / capture["path"]
            wrapped = check.load(payload)
            body = wrapped.get("body", wrapped)
            tools = next(item for item in body["input"] if item.get("type") == "additional_tools")
            mutate(tools)
            check.save(payload, wrapped)
        with self.assertRaisesRegex(check.Rejected, "Stock tool inventory"):
            check.validate_case(directory, result, platform_key)

    def test_live_stock_gate_rejects_one_tool(self):
        def only_exec(item):
            namespace = next(tool for tool in item["tools"] if tool.get("name") == "functions")
            namespace["tools"] = [tool for tool in namespace["tools"] if tool.get("name") == "exec"]
            item["tools"] = [namespace]
        self.reject_stock_inventory(only_exec)

    def test_live_stock_gate_rejects_nine_tools(self):
        self.reject_stock_inventory(lambda item: item["tools"].append({"type": "function", "name": "unexpected_extra_tool"}))

    def test_live_stock_gate_rejects_eight_different_tools(self):
        def replace_wait(item):
            namespace = next(tool for tool in item["tools"] if tool.get("name") == "functions")
            tool = next(tool for tool in namespace["tools"] if tool.get("name") == "wait")
            tool["name"] = "unexpected_tool"
        self.reject_stock_inventory(replace_wait)

    def test_top_level_tools_and_empty_namespace_are_rejected(self):
        for tools in ([{"type": "function", "name": "shell"}], [{"type": "namespace", "name": "functions", "tools": []}]):
            with self.subTest(tools=tools):
                self.reject_body(lambda b: b.update(tools=tools))

    def test_additional_tools_cannot_replace_a_message(self):
        for tools in ([], [{"type": "function", "name": "shell"}]):
            self.reject_body(lambda b: b["input"].__setitem__(0, {"type": "additional_tools", "tools": tools}))

    def test_no_literal_empty_tools_field_is_required(self):
        for body in self.bodies[:2]:
            self.assertNotIn("tools", body)
        body = copy.deepcopy(self.bodies[0])
        body["tools"] = []
        check.assert_candidate(body, self.original[0]["expected"])

    def test_exact_prompt_contents_and_roles_are_enforced(self):
        for index in (0, 1):
            with self.subTest(index=index):
                self.reject_body(lambda b: b["input"][index]["content"][0].update(text="changed synthetic prompt"))
        self.reject_body(lambda b: b["input"][0].update(role="system"))

    def test_extra_history_environment_skills_and_attachments_are_rejected(self):
        for extra in ("AGENTS.md context", "skills instructions", "environment context", "prior history"):
            self.reject_body(lambda b: b["input"].append({"type": "message", "role": "developer", "content": [{"type": "input_text", "text": extra}]}))
        self.reject_body(lambda b: b["input"][1]["content"].append({"type": "input_image", "image_url": "synthetic"}))
        self.reject_body(lambda b: b.update(instructions="hidden added instructions"))

    def test_schema_model_and_effort_mutations_are_rejected(self):
        self.reject_body(lambda b: b["text"]["format"]["schema"].update(additionalProperties=True))
        self.reject_body(lambda b: b["text"]["format"].update(strict=False))
        self.reject_body(lambda b: b.update(model="another-model"))
        self.reject_body(lambda b: b["reasoning"].update(effort="high"))

    def test_native_metadata_ids_are_preserved_and_required(self):
        body = copy.deepcopy(self.bodies[0])
        body["client_metadata"]["thread_id"] = "another-native-id"
        check.assert_candidate(body, self.original[0]["expected"])
        self.reject_body(lambda b: b.pop("client_metadata"))

    def test_native_thread_and_requirements_context_are_rejected(self):
        base = self.original[0]
        check.assert_thread(base["thread_start"], base["requirements"])
        for mutate in (lambda t: t.update(instructionSources=["AGENTS.md"]),
                       lambda t: t.update(reasoningEffort="high"),
                       lambda t: t["thread"].update(turns=[{"id": "old"}]),
                       lambda t: t.update(runtimeWorkspaceRoots=["C:/project"])):
            thread = copy.deepcopy(base["thread_start"])
            mutate(thread)
            with self.assertRaises(check.Rejected):
                check.assert_thread(thread, base["requirements"])
        requirements = copy.deepcopy(base["requirements"])
        requirements["requirements"]["additionalDeveloperInstructions"] = "added policy text"
        with self.assertRaises(check.Rejected):
            check.assert_thread(base["thread_start"], requirements)

    def test_control_reconstructs_original_semantics_without_catalog_copy(self):
        source = OPTIONS.proof_root / "sources/codex-rs__models-manager__models.json"
        check.verify_control_source(source)
        candidate = check.read_bytes(REPO / "desktop/codex/luna-models.json")
        control = check.load_json_bytes(check.control_catalog(candidate))
        self.assertEqual(control, check.load(source))
        corrupted = candidate.replace(b'"gpt-6-luna"', b'"gpt-6-wrong"', 1)
        with self.assertRaises(check.Rejected):
            check.control_catalog(corrupted)

    def test_changed_adapter_source_fails_before_loading_or_running_it(self):
        for name in (*check.SOURCE_PINS, *check.OBSERVED_SOURCES):
            target = self.directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / name).read_bytes())
        check.checked_sources(self.directory)
        target = self.directory / "desktop/src/main/codex/config.ts"
        target.write_bytes(target.read_bytes().replace(b'gpt-6-luna', b'gpt-6-other', 1))
        with self.assertRaises(check.Rejected):
            check.checked_sources(self.directory)

    def test_config_deltas_are_only_ephemeral_credentials_and_dead_endpoint(self):
        config = check.read_bytes(OPTIONS.proof_root / "harness/isolation.toml").decode()
        parsed = check.tomllib.loads(config)
        parsed.pop("openai_base_url")
        original = config.replace('cli_auth_credentials_store = "ephemeral"', 'cli_auth_credentials_store = "keyring"')
        original = "\n".join(line for line in original.splitlines() if not line.startswith("openai_base_url =")) + "\n"
        catalog = Path(parsed["model_catalog_json"])
        patched = check.probe_config(original, catalog)
        self.assertEqual(check.tomllib.loads(patched)["cli_auth_credentials_store"], "ephemeral")
        for old, new in (('model = "gpt-6-luna"', 'model = "gpt-6-other"'),
                         ('developer_instructions = ""', 'developer_instructions = "added"'),
                         ('shell_tool = false', 'shell_tool = true')):
            with self.subTest(new=new), self.assertRaises(check.Rejected):
                check.probe_config(original.replace(old, new), catalog)

    def test_wrapped_capture_is_read_from_actual_bytes(self):
        trace = self.directory / "trace"
        payloads = trace / "payloads"
        payloads.mkdir(parents=True)
        (trace / "trace.jsonl").write_text(json.dumps({"payload": {"type": "inference_started", "request_payload": {"path": "payloads/request.json"}}}) + "\n")
        check.save(payloads / "request.json", {"body": self.bodies[0]})
        capture = check.captured_requests(trace)[0]
        check.assert_candidate(capture["body"], self.original[0]["expected"])
        self.assertEqual(capture["sha256"], check.sha(payloads / "request.json"))
        check.save(payloads / "request.json", {"body": {**self.bodies[0], "model": "changed"}})
        changed = check.captured_requests(trace)[0]
        self.assertNotEqual(changed["sha256"], capture["sha256"])
        with self.assertRaises(check.Rejected):
            check.assert_candidate(changed["body"], self.original[0]["expected"])

    def test_trace_paths_cannot_escape_on_either_os(self):
        for relative in ("../outside.json", "/tmp/outside.json", "C:/outside.json", "C:\\outside.json", "\\\\server\\share\\outside.json"):
            with self.subTest(relative=relative), self.assertRaises(check.Rejected):
                check.contained(self.directory, relative)

    def test_trace_symlink_and_duplicate_json_are_rejected(self):
        if sys.platform != "win32":
            (self.directory / "link").symlink_to(self.directory / "target")
            with self.assertRaises(check.Rejected):
                check.contained(self.directory, "link")
        with self.assertRaises(check.Rejected):
            check.load_json_bytes(b'{"model":"first","model":"second"}')

    def test_subprocess_deadline_cleans_owned_process_tree(self):
        paths, env = check.private_environment(self.directory)
        started = time.monotonic()
        with self.assertRaises(check.Rejected):
            check.command([sys.executable, "-B", "-c", "import time; time.sleep(60)"], paths, env,
                          self.directory / "command", check.Deadline(0.3))
        report = check.load(self.directory / "command/command.json")
        self.assertTrue(report["cleanup"]["ownedTreeAbsent"])
        self.assertTrue(report["cleanup"]["stdioThreadsFinished"])
        self.assertLess(time.monotonic() - started, 20)

    def test_subprocess_output_cap_is_enforced(self):
        paths, env = check.private_environment(self.directory)
        with self.assertRaises(check.Rejected):
            check.command([sys.executable, "-B", "-c", "import sys,time; sys.stdout.buffer.write(b'x'*4000000); sys.stdout.flush(); time.sleep(30)"],
                          paths, env, self.directory / "command", check.Deadline(8))
        self.assertLessEqual((self.directory / "command/stdout.txt").stat().st_size, check.MAX_STREAM)
        report = check.load(self.directory / "command/command.json")
        self.assertTrue(report["cleanup"]["ownedTreeAbsent"])
        self.assertTrue(report["cleanup"]["stdioThreadsFinished"])

    def test_cleanup_removes_descendant_after_immediate_parent_exit(self):
        paths, env = check.private_environment(self.directory)
        code = "import subprocess,sys; p=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(60)']); print(p.pid,flush=True)"
        check.command([sys.executable, "-B", "-c", code], paths, env, self.directory / "command", check.Deadline(8))
        report = check.load(self.directory / "command/command.json")
        self.assertTrue(report["cleanup"]["ownedTreeAbsent"])
        self.assertTrue(report["cleanup"]["stdioThreadsFinished"])

    def test_unpinned_executable_is_rejected_before_any_codex_rpc(self):
        paths, env = check.private_environment(self.directory)
        wrong = self.directory / ("wrong-codex.exe" if sys.platform == "win32" else "wrong-codex")
        wrong.write_bytes(b"not a native Codex executable\n")
        args = SimpleNamespace(node=shutil.which("node"), resources_dir=REPO, executable=str(wrong))
        with self.assertRaises(check.Rejected):
            check.builder(args, paths, env, self.directory, self.original[0]["expected"], check.Deadline(12))
        self.assertFalse((self.directory / "rpc-sent.jsonl").exists())

    def test_replay_detects_saved_evidence_mutation(self):
        if not OPTIONS.saved_run:
            self.skipTest("Add --saved-run after native execution for manifest tamper verification")
        result = check.replay(OPTIONS.saved_run)
        self.assertEqual(result["status"], "VERIFIED")
        run = self.directory / "copied-run"
        shutil.copytree(OPTIONS.saved_run, run)
        raw = next((run / "candidate-a/trace").rglob("payloads/*.json"))
        raw.write_bytes(raw.read_bytes() + b" ")
        with self.assertRaises(check.Rejected):
            check.replay(run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-root", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--saved-run", type=Path)
    OPTIONS, remaining = parser.parse_known_args()
    OPTIONS.scratch.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
