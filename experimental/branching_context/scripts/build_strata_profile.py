"""Pin measured Strata files/settings; incomplete calibration never gets tolerances."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from calibration_inputs import execution_settings


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native_root', type=Path)
    parser.add_argument('calibration', type=Path)
    parser.add_argument('source_receipt', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--admission', type=Path)
    args = parser.parse_args()
    root = args.native_root.resolve()
    calibration = json.loads(args.calibration.read_text())
    admission_path = args.admission or root/'build/q8-dual-engine-admission.json'
    admission = json.loads(admission_path.read_text())
    settings = execution_settings(admission)
    assert settings['kv_format'] == calibration['kv_format']
    assert settings['capacity'] == calibration['capacity']
    assert admission['expert_cache_slots'] == calibration['expert_cache_slots']
    assert admission['oracle_command'] == calibration['command']
    assert sha(admission['oracle_command'][0]) == calibration['oracle_sha256']
    assert sha(admission['sut_command'][0]) == admission['sut_binary_sha256']
    previous_path = Path(calibration['prior_executed_hash_run'])
    previous = json.loads(previous_path.read_text())
    for name, item in calibration['model_files'].items():
        stat = Path(name).stat()
        assert (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (item['bytes'], item['mtime_ns'], item['ctime_ns']), name
        assert previous['model_files'][name]['sha256'] == item['sha256'], name
    helper = root/'tools/gguf_reader.py'
    spec = importlib.util.spec_from_file_location('strata_profile_gguf', helper)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    command = admission['sut_command']
    model_path = command[command.index('--native') + 1]
    md = module.GGUFFile(Path(model_path)).metadata
    assert md['general.architecture'] == 'qwen4exp'
    assert md['tokenizer.ggml.model'] == 'gpt2'
    eos = [md['tokenizer.ggml.tokens'].index(token) for token in ('<|endoftext|>', '<|im_end|>')]
    weights = {name: dict(bytes=item['bytes'], sha256=item['sha256']) for name, item in calibration['model_files'].items()}
    model_sha = digest(weights)
    contract = dict(weights_sha256=model_sha, architecture=md['general.architecture'],
        rope_base=str(md['qwen4exp.rope.freq_base']), yarn='model-default',
        tokenizer_identity=model_sha, template_identity='exact-token-ids/no-template',
        attention='causal-qsa-indexed', positions='absolute-zero-based', input_kind='token_ids',
        adapters=[], state_kind='qwen4exp-gdn-qsa-ple-v1')
    source = json.loads(args.source_receipt.read_text())
    for name, expected in source['source_sha256'].items():
        assert sha(root / name) == expected, name
    build = dict(revision=source['source_commit'], source_sha256=source['source_sha256'],
        sha256={name: sha(name) for name in (command[0], admission['oracle_command'][0], str(helper))})
    execution = dict(sut_command=command, oracle_command=admission['oracle_command'],
        capacity=calibration['capacity'], kv_dtype=calibration['kv_format'],
        operator=calibration['operator'], environment=calibration['environment'], eos_tokens=eos)
    # Disjoint from the synthetic calibration histories, fixed before API tests.
    fixtures = dict(prefix=[1 + (i * 13 % 71) for i in range(33)], suffix_a=[71, 72, 73], suffix_b=[81, 82, 83])
    profile = dict(backend='strata', model_path=model_path, model_weights_sha256=model_sha,
        model_files=calibration['model_files'], model_hash_receipt=str(previous_path),
        model_hash_receipt_sha256=sha(previous_path), model_contract=contract,
        model_contract_id=digest(contract), backend_revision=build['revision'], native_build=build,
        gguf_reader=str(helper), execution=execution, hardware=calibration['hardware'],
        execution_profile_id=digest(dict(build=build, execution=execution, hardware=calibration['hardware'])),
        fixtures=fixtures, token_fixtures_sha256=digest(fixtures),
        oracle_binary=admission['oracle_command'][0], oracle_revision=calibration['oracle_source_revision'],
        calibration_path=str(args.calibration.resolve()), calibration_status=calibration['status'],
        admission_path=str(admission_path.resolve()), admission_sha256=sha(admission_path),
        numerical_gate_qualified=False)
    if calibration['status'] == 'FROZEN':
        profile.update(atol=calibration['atol'], rtol=calibration['rtol'],
            baseline_max_absolute_error=calibration['baseline_max_absolute_error'],
            tolerance_rule=calibration['tolerance_rule'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as out:
        json.dump(profile, out, indent=2)
        out.write('\n')
    print(json.dumps(dict(path=str(args.output), sha256=sha(args.output),
        model_contract_id=profile['model_contract_id'], execution_profile_id=profile['execution_profile_id'],
        calibration_status=profile['calibration_status'], numerical_gate_qualified=False)))


if __name__ == '__main__':
    main()
