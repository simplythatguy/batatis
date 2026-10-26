"""Compare the actual adapter templates with saved synthetic native captures, offline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib


MANIFEST_SHA256 = '552f9b2ccbf9a9edd61122b75c7876e0ae18a388c14032eae265fbe21066fcdb'
ASSEMBLY_SHA256 = '2e35120991aa50a2ede1b65ac70182aa2f46f2e511f2bff1c484561f2020f0a6'
RUNTIME_SHA256 = 'd8990e3ee7acfbc26f91265b12a1a83f0fee40d0e0f8f1f40a37d4ec21f499cf'
CATALOG_SHA256 = 'dca46de82fef92c2d3f7212467181b2d17cf8e5a3d468ade38d555280bf37fb8'
RUN = 'runs/20261025T190515Z-c824cb3e'


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def assembly(config):
    value = dict(config)
    value.pop('cli_auth_credentials_store', None)
    value.pop('openai_base_url', None)
    value['model_catalog_json'] = '<APP_PRIVATE_CATALOG>'
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def assert_body(body, expected):
    assert not body.get('tools'), 'Top-level tool definitions exposed'
    assert not any(item.get('type') == 'additional_tools' for item in body['input']), 'Response Lite additional_tools exposed'
    assert len(body['input']) == 2, 'Extra context, history or attachment input'
    for message, role, text in zip(body['input'], ['developer', 'user'], [expected['system'], expected['user']], strict=True):
        assert message['type'] == 'message' and message['role'] == role, 'Changed message role'
        assert message['content'] == [{'type': 'input_text', 'text': text}], 'Changed workflow text'
    assert body['model'] == 'gpt-6-luna'
    assert body['reasoning'] == {'effort': 'medium', 'context': 'all_turns'}
    assert body['text']['format'] == {'type': 'json_schema', 'strict': True, 'schema': expected['schema'], 'name': 'codex_output_schema'}
    assert body['tool_choice'] == 'auto' and body['parallel_tool_calls'] is False
    assert body['stream'] is True and body['store'] is False


NODE = """
import fs from 'node:fs';
import * as config from './desktop/src/main/codex/config.ts';
import * as protocol from './desktop/src/main/codex/protocol.ts';
import { bundledRuntime } from './desktop/src/main/codex/binary.ts';
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const rows = cases.map((c) => {
  protocol.assertRequirements(c.requirements);
  protocol.parseModels(c.modelsResponse);
  const threadId = protocol.parseThread(c.thread_start, c.cwd);
  protocol.parseTurn(c.turn_start.turn);
  return {
    thread: config.threadParams(c.cwd, c.expected.system),
    turn: config.turnParams(threadId, {user:c.expected.user, schema:c.expected.schema}),
    args: config.RUNTIME_ARGS,
    initialize: config.initializeParams('1.0.0'),
  };
});
const runtime = await bundledRuntime()({resourcesDir:process.cwd()}, 'darwin', 'arm64');
console.log(JSON.stringify({fingerprint:config.CODEX_CONTEXT_FINGERPRINT,
  config:config.processConfig('/APP_PRIVATE/luna-models.json'),
  runtime:{executable:runtime.executable, sha256:runtime.sha256}, rows}));
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native_probe', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    native = args.native_probe.resolve()
    manifest_path = native / 'artifact-manifest.json'
    assert sha(manifest_path) == MANIFEST_SHA256, 'Native artifact manifest changed'
    manifest = {entry['path']: entry for entry in json.loads(manifest_path.read_text())['added_files']}

    def checked(path):
        path = path.resolve()
        relative = str(path.relative_to(native))
        assert sha(path) == manifest[relative]['sha256'], f'Changed evidence artifact {relative}'
        return path

    cases = []
    for name in ['candidate-a', 'candidate-b', 'stock-control']:
        case_path = checked(native / RUN / name / 'result.json')
        case = json.loads(case_path.read_text())
        case['cwd'] = case['thread_start']['cwd']
        case['sent'] = [json.loads(line) for line in checked(case_path.parent / 'rpc-sent.jsonl').read_text().splitlines()]
        received = [json.loads(line) for line in checked(case_path.parent / 'rpc-received.jsonl').read_text().splitlines()]
        model_request = next(message for message in case['sent'] if message['method'] == 'model/list')
        case['modelsResponse'] = next(message['result'] for message in received if message.get('id') == model_request['id'])
        for capture in case['trace_events']:
            request_path = checked(Path(capture['request_path']))
            assert sha(request_path) == capture['request_sha256']
            raw = json.loads(request_path.read_text())
            # Trace payloads wrap their captured request body under `body`.
            body = raw.get('body', raw)
            assert body == capture['body'], 'Saved trace summary differs from captured bytes'
        cases.append(case)

    candidates = cases[:2]
    result = subprocess.run(['node', '--experimental-strip-types', '--disable-warning=MODULE_TYPELESS_PACKAGE_JSON',
        '--import', './desktop/scripts/register-ts.mjs', '--input-type=module', '--eval', NODE],
        cwd=repo, input=json.dumps(candidates), capture_output=True, text=True, check=True)
    adapter = json.loads(result.stdout)
    actual_config = tomllib.loads(adapter['config'])
    actual_assembly = assembly(actual_config)
    assert digest(actual_assembly) == ASSEMBLY_SHA256, 'Adapter process configuration differs from native assembly'
    assert actual_config['cli_auth_credentials_store'] == 'keyring'
    assert 'openai_base_url' not in actual_config
    assert sha(repo / 'desktop/codex/luna-models.json') == CATALOG_SHA256
    assert sha(repo / 'desktop/codex/runtime/darwin-arm64/codex') == RUNTIME_SHA256
    assert adapter['runtime']['sha256'] == RUNTIME_SHA256
    rows = []
    for case, actual in zip(candidates, adapter['rows'], strict=True):
        assert case['assembly_config'] == actual_assembly
        assert case['assembly_config_fingerprint_sha256'] == ASSEMBLY_SHA256
        assert case['argv'][-len(actual['args']):] == actual['args']
        sent = {message['method']: message.get('params') for message in case['sent']}
        assert sent['thread/start'] == actual['thread'], 'Adapter thread parameters differ'
        assert sent['turn/start'] == actual['turn'], 'Adapter turn parameters differ'
        assert sent['initialize']['capabilities'] == actual['initialize']['capabilities']
        assert case['cleanup']['owned_process_group_absent'] and case['cleanup']['exit_code'] == 0
        for capture in case['trace_events']:
            assert_body(capture['body'], case['expected'])
        rows.append({'case': case['case'], 'requestSha256': [c['request_sha256'] for c in case['trace_events']], 'toolDefinitions': 0})
    for capture in cases[2]['trace_events']:
        try:
            assert_body(capture['body'], cases[2]['expected'])
        except AssertionError:
            pass
        else:
            raise AssertionError('Stock positive control incorrectly passed')
    owned = [repo / 'desktop/src/main/codex.ts', *sorted((repo / 'desktop/src/main/codex').glob('*.ts'))]
    proof = {
        'status': 'PARAMETER_AND_ASSEMBLY_EQUIVALENCE_VERIFIED',
        'scope': 'Saved no-auth macOS request boundary only. Production gate remains explicit and unchanged.',
        'nativeManifestSha256': MANIFEST_SHA256,
        'assemblyConfigFingerprint': ASSEMBLY_SHA256,
        'adapterContextFingerprint': adapter['fingerprint'],
        'runtimeSha256': RUNTIME_SHA256, 'catalogSha256': CATALOG_SHA256,
        'adapterRuntime': adapter['runtime'],
        'adapterSourceHashes': {str(path.relative_to(repo)): sha(path) for path in owned},
        'candidateCases': rows, 'stockControlRejected': True,
        'reviewBeforeEnabling': [
            'Production keyring and official endpoint replace probe ephemeral credentials and denied loopback endpoint.',
            'Production client identity differs from the synthetic probe; capabilities and assembly parameters match.',
            'Probe used private HOME, XDG and diagnostic tracing; production uses the documented OS environment allow-list.',
            'System instructions occupy the native developer role. Codex attribution IDs remain.',
            'This does not prove authentication, entitlement, successful inference, Windows execution, provider hidden policy or a universal internal tool deny-list.',
        ],
        'proposedVerifiedContext': {'evidence': str(args.output.resolve()), 'runtimeSha256': RUNTIME_SHA256, 'contextFingerprint': adapter['fingerprint']},
        'enabledByThisScript': False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'status': proof['status'], 'output': str(args.output.resolve()), 'adapterContextFingerprint': adapter['fingerprint'], 'enabledByThisScript': False}))


if __name__ == '__main__':
    main()
