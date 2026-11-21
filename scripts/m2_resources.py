"""Verify the MDD core slice and transactional extraction, without native apps."""
import argparse
from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from patched_interop import ROOT, read_python, require, verify_candidate_source
from m2_foundation import check_layout, fingerprints, sha
from v2_audit import audit


def relative_resource_path(key):
    """Independent portable path validation; never normalize away traversal."""
    require(isinstance(key, str) and 0 < len(key.encode('utf-8')) <= 4096, 'Empty/oversized resource key')
    normalized = key.replace('\\', '/')
    require(not normalized.startswith('//'), 'UNC/repeated leading separators')
    relative = normalized[1:] if normalized.startswith('/') else normalized
    parts = relative.split('/')
    require(len(parts) <= 32, 'Too many path components')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    reserved.update(p + n for p in ['COM', 'LPT'] for n in list('123456789') + ['¹', '²', '³'])
    for part in parts:
        require(part not in {'', '.', '..'} and len(part.encode('utf-8')) <= 255, 'Unsafe resource component')
        require(not part.endswith((' ', '.')), 'Ambiguous trailing path characters')
        require(not any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in '<>:"|?*' for c in part), 'Nonportable resource component')
        require(part.split('.')[0].rstrip(' .').upper() not in reserved, 'Reserved device name')
    return '/'.join(parts)


def compare_resources(expected, actual):
    pairs = [(r['key'], bytes(r['bytes'])) for r in expected]
    require(len(pairs) == len({k for k, _ in pairs}), 'Duplicate expected resource key')
    require(Counter(pairs) == Counter(actual), 'Independent reader resource keys/bytes differ')


def verify_extracted(directory, expected):
    require(directory.is_dir() and not directory.is_symlink(), 'Extraction root must be a real directory')
    files = {}; dirs = set()
    for row in expected:
        relative = relative_resource_path(row['key'])
        require(relative not in files, 'Expected extraction aliases')
        files[relative] = bytes(row['bytes'])
        pieces = relative.split('/')
        dirs.update('/'.join(pieces[:i]) for i in range(1, len(pieces)))
    seen_files = set(); seen_dirs = set()
    for path in directory.rglob('*'):
        require(not path.is_symlink(), 'Symlink appeared in extracted tree')
        relative = path.relative_to(directory).as_posix()
        if path.is_dir():
            seen_dirs.add(relative)
        else:
            require(path.is_file() and relative in files, 'Unexpected extracted node')
            require(path.stat().st_size == len(files[relative]), 'Extracted byte length differs')
            require(path.read_bytes() == files[relative], 'Extracted bytes differ')
            seen_files.add(relative)
    require(seen_files == set(files) and seen_dirs == dirs, 'Extraction inventory differs')
    return [{'path':name, 'bytes':len(data), 'sha256':__import__('hashlib').sha256(data).hexdigest()} for name,data in sorted(files.items())]


def source_fingerprints():
    result = fingerprints()
    for name in ['scripts/m2_resources.py', 'baseline/resource-probe/studio-probe.ttf']:
        result[name] = sha(ROOT / name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=False, exist_ok=False)
    report = {'status':'m2_resources_failed', 'M1':'complete_unchanged', 'M2_complete':False,
              'python':sys.version, 'platform':platform.platform(), 'steps':[], 'checks':{},
              'native_readers':'NOT_REQUESTED', 'scope':'bounded versioned MDD, exact resource lookup and staged extraction'}
    def run(label, command, parse=False, refusal=None):
        log = out / (label + '.log')
        print(f'Running {label}; log: {log}', flush=True)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='strict')
        log.write_text(result.stdout + '\nSTDERR:\n' + result.stderr, encoding='utf-8')
        step = {'name':label, 'returncode':result.returncode, 'log':log.name}
        report['steps'].append(step)
        if refusal:
            require(result.returncode == 1 and not result.stdout.strip(), f'{label} must be a controlled refusal; return {log.name}')
            final = json.loads(result.stderr.strip().splitlines()[-1])
            require(final.get('status') == 'failed' and final['error']['code'] == refusal, f'{label} refused for wrong reason; return {log.name}')
            step['expected_refusal'] = refusal
            return None
        require(result.returncode == 0, f'{label} failed; return {log.name}')
        return json.loads(result.stdout) if parse else None
    try:
        check_layout(); report['source_sha256'] = source_fingerprints()
        require(importlib.metadata.version('mdict-utils') == '1.3.14', 'Use existing .venv with mdict-utils==1.3.14')
        verify_candidate_source(ROOT / 'vendor/mdictlib-0.2.8-studio-sort-v6', 6)
        cargo = shutil.which('cargo'); require(cargo is not None, 'Run on the Rust-enabled Mac')
        command = [cargo, 'run', '--locked', '--manifest-path', 'm2/Cargo.toml', '-p', 'studio-cli', '--']
        run('resource-tests', [cargo, 'test', '--locked', '--manifest-path', 'm2/Cargo.toml', '--workspace'])
        smoke = run('resource-smoke', command + ['mdd-smoke', str(out / 'smoke')], parse=True)
        require(smoke['status'] == 'mdd_core_smoke_passed' and len(smoke['expected_resources']) == 6, 'Incomplete resource smoke')
        (out / 'resource-smoke.json').write_text(json.dumps(smoke, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        path = Path(smoke['file']); expected = smoke['expected_resources']
        require(path == out / 'smoke/studio-core-resources.mdd', 'Unexpected MDD path')
        require(Path(smoke['extracted_directory']) == out / 'smoke/extracted', 'Unexpected extraction path')
        before = sha(path)
        compare_resources(expected, read_python(path, 'mdd'))
        wire = audit(path); require(wire['status'] == 'structural_audit_passed', 'Independent MDD wire audit failed')
        inventory = verify_extracted(out / 'smoke/extracted', expected)
        for index, row in enumerate(expected):
            reopened = run(f'resource-reopen-{index}', command + ['resource', str(path), row['key']], parse=True)
            require(reopened['resource'] == row, 'Resource bytes differ after separate-process reopen')
        missing = run('resource-missing', command + ['resource', str(path), 'missing.bin'], parse=True)
        require(missing['resource'] is None, 'Missing resource returned a value')
        extracted = out / 'extracted-reopened'
        run('extract-reopen', command + ['extract', str(path), str(extracted)], parse=True)
        verify_extracted(extracted, expected)
        run('extract-existing-refused', command + ['extract', str(path), str(extracted)], refusal='destination_exists')
        verify_extracted(extracted, expected)
        for label, keys, reason in [('unsafe', ['../escape.bin'], 'unsafe_path'),
                                    ('aliases', ['A/file.bin','a/other.bin'], 'path_collision')]:
            request = out / (label + '-request.json'); rejected = out / (label + '.mdd')
            request.write_text(json.dumps({'title':'negative', 'description':'negative',
                'resources':[{'key':k,'bytes':[0,255,128]} for k in keys]}), encoding='utf-8')
            run(label + '-refused', command + ['mdd-pack', str(request), str(rejected)], refusal=reason)
            require(not rejected.exists(), 'Rejected pack published an output')
        require(sha(path) == before, 'MDD changed during independent reads/extraction')
        require(source_fingerprints() == report['source_sha256'], 'Source/lock changed during run')
        report['checks'] = {'resources':6, 'mdd_sha256':before, 'independent_python_bytes':'passed',
            'wire_audit':'passed', 'separate_process_reopen':'passed', 'extraction_inventory':inventory,
            'existing_destination_preserved':'passed', 'unsafe_and_alias_pack_refusals':'passed'}
        report['status'] = 'm2_resources_passed_remaining_M2_work_pending'
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = f'{type(error).__name__}: {error}'
    destination = out / 'm2-resources-report.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{report['status']}: {destination}", flush=True)
    return 0 if report['status'] == 'm2_resources_passed_remaining_M2_work_pending' else 1


if __name__ == '__main__':
    raise SystemExit(main())
