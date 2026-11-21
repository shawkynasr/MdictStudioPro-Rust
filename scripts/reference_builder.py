"""Prepare official-builder sources and compare a supplied v2 output offline."""
import argparse
from collections import Counter
import html
import importlib.metadata
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib
from patched_interop import ROOT, require, hash_file, read_python, verify_candidate_source, experiment_command
from check_native_wire import wire_contract
from stylesheet_controls import specification
from v2_audit import audit


def source_files():
    """Exact common inputs: UTF-16LE BOM, CRLF, no final style newline.

    A source body ends in CRLF before the delimiter. Rust receives that same
    text explicitly; any different official parsing remains an observed delta.
    """
    spec = specification()
    case = spec["cases"][0]
    case["stylesheet"] = case["stylesheet"].replace("\n", "\r\n")
    for row in case["entries"]:
        row["text"] += "\r\n"
    source = ''.join(e["key"] + "\r\n" + e["text"] + "</>\r\n" for e in case["entries"])
    files = {"source.txt": b'\xff\xfe' + source.encode('utf-16le'),
             "style.txt": b'\xff\xfe' + case["stylesheet"].encode('utf-16le'),
             "rust-spec.json": (json.dumps(spec, ensure_ascii=False, indent=2) + '\n').encode('utf-8')}
    return files


def prepare(out):
    out = out.resolve(); out.mkdir(parents=True, exist_ok=False)
    files = source_files()
    for name, content in files.items(): (out/name).write_bytes(content)
    manifest = {"status": "sources_prepared_no_compiler_run", "writer_revision": 5,
                "encoding": "UTF-16LE with BOM", "source_line_endings": "CRLF",
                "style_final_newline": False,
                "files": {name: hash_file(out/name) for name in files}}
    (out/'reference-kit.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (out/'BUILD-IN-WINDOWS.txt').write_text(
        'Use your supplied MdxBuilder Version 3.0 RC1.\n'
        'Source: source.txt\nStyle: style.txt\nOriginal format: MDict(Compact HTML)\n'
        'Encoding: UTF-16(Unicode)\nTitle: 04-stylesheet\n'
        'Target: official-stylesheet.mdx\nData/resource path: leave empty\n'
        'Encrypt: unchecked; no password or encryption key\n'
        'Build, then return official-stylesheet.mdx. Do not import it into readers yet.\n'
        'Do not use MdxBuilder 4.x for this v2 reference.\n', encoding='utf-8')
    print(f"Sources prepared: {out}")
    return 0


def verify_kit(kit):
    manifest = json.loads((kit/'reference-kit.json').read_text(encoding='utf-8'))
    require(manifest['status'] == 'sources_prepared_no_compiler_run', 'Unexpected kit status')
    # Bind to reproducible fixture bytes, not just a user-editable manifest.
    for name, expected in source_files().items():
        require((kit/name).read_bytes() == expected, f'Kit source differs: {name}')
        require(hash_file(kit/name) == manifest['files'][name], f'Kit hash differs: {name}')


def header_details(path):
    with path.open('rb') as stream:
        prefix = stream.read(4); require(len(prefix) == 4, 'Missing header length')
        size = struct.unpack('>I', prefix)[0]
        require(2 <= size <= 1024*1024 and size % 2 == 0, 'Header exceeds fixture limit')
        raw = stream.read(size); checksum = stream.read(4)
    require(len(raw) == size and len(checksum) == 4, 'Truncated header')
    require(zlib.adler32(raw) & 0xffffffff == struct.unpack('<I', checksum)[0], 'Header checksum differs')
    xml = raw.decode('utf-16le', errors='strict')
    attrs = {k: html.unescape(v) for k, v in re.findall(r'(\w+)="(.*?)"', xml, re.S)}
    require(attrs.get('GeneratedByEngineVersion') == '2.0', 'Expected v2 output; builder version is not MDX format version')
    return {'attributes': attrs, 'header_bytes': size, 'ends_CRLF_NUL': xml.endswith('\r\n\0'),
            'ends_NUL': xml.endswith('\0'), 'header_adler32_valid': True}


def inspect_fixture(path):
    require(path.suffix.lower() == '.mdx' and path.stat().st_size <= 8*1024*1024, 'Expected a small synthetic MDX fixture')
    before = hash_file(path); header = header_details(path)
    rows = read_python(path, 'mdx')
    expected_keys = Counter(e['key'] for e in specification()['cases'][0]['entries'])
    require(Counter(k for k, v in rows) == expected_keys, 'Reference keys differ from the five-entry fixture')
    from mdict_utils.base.readmdict import MDX
    styled = [(k.decode('utf-8'), v.decode('utf-8')) for k, v in MDX(str(path), substyle=True).items()]
    require(Counter(k for k, v in styled) == expected_keys, 'Expanded entry inventory differs')
    values = dict(styled)
    observation = {'file': path.name, 'sha256': before, 'header': header,
        'raw_rows': [{'key': k, 'text': v, 'ends_CRLF': v.endswith('\r\n'), 'ends_LF': v.endswith('\n')} for k, v in rows],
        'python_expanded_rows': [{'key': k, 'text': v} for k, v in styled],
        'python_expanded_pair_equal': {color: values['inline-'+color] == values['marker-'+color] for color in ['red', 'blue']},
        'structural_audit': audit(path)}
    require(hash_file(path) == before, 'Input changed during comparison')
    return observation


def differences(left, right):
    a = left['header']['attributes']; b = right['header']['attributes']
    return {'header_attributes': {k: {'official': a.get(k), 'rust': b.get(k)} for k in sorted(set(a)|set(b)) if a.get(k) != b.get(k)},
        'raw_rows_equal_in_physical_order': left['raw_rows'] == right['raw_rows'],
        'raw_key_payload_multisets_equal': Counter((e['key'], e['text']) for e in left['raw_rows']) == Counter((e['key'], e['text']) for e in right['raw_rows']),
        'python_expanded_rows_equal': left['python_expanded_rows'] == right['python_expanded_rows']}


def compare_reference(kit, reference, out):
    kit = kit.resolve(); reference = reference.resolve(); out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'blocked', 'native_readers': 'NOT_RUN_DO_NOT_IMPORT',
              'qualification': 'NOT_ESTABLISHED', 'steps': [],
              'not_proven': ['native_stylesheet_rendering', 'MDict_crash_cause', 'official_builder_invocation_settings']}
    def run(name, command):
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=1800)
        (out/(name+'.log')).write_text(result.stdout+'\nSTDERR:\n'+result.stderr, encoding='utf-8')
        report['steps'].append({'name': name, 'returncode': result.returncode, 'log': name+'.log'})
        require(result.returncode == 0, f'{name} failed; see log')
        return result.stdout
    try:
        verify_kit(kit)
        require(importlib.metadata.version('mdict-utils') == '1.3.14', 'Expected mdict-utils 1.3.14')
        # Inspect the supplied artifact before invoking Cargo.
        report['official'] = inspect_fixture(reference)
        run('prepare', [sys.executable, ROOT/'scripts/prepare_sort_experiment.py', '--revision', '5', '--reuse'])
        vendor = ROOT/'vendor/mdictlib-0.2.8-studio-sort-v5'
        verify_candidate_source(vendor, 5)
        report['source_sha256'] = {str(p.relative_to(ROOT)): hash_file(p) for p in
            [vendor/'src/write/mod.rs', vendor/'src/write/studio_legacy_sort.rs',
             ROOT/'experiments/native-controls/src/main.rs', Path(__file__).resolve()]}
        built = json.loads(run('rust-build', ['cargo', 'run', '--locked', '--manifest-path',
            'experiments/native-controls/Cargo.toml', '--', kit/'rust-spec.json', out/'rust-dictionaries']))
        require(built['profile'] == 'HeaderLiteralC' and len(built['cases']) == 2, 'Unexpected Rust output')
        require({c['file'] for c in built['cases']} == {'04-stylesheet-utf8.mdx', '04-stylesheet-utf16.mdx'}, 'Wrong Rust fixture identity')
        report['rust'] = inspect_fixture(out/'rust-dictionaries/04-stylesheet-utf16.mdx')
        require(report['rust']['structural_audit']['status'] == 'structural_audit_passed', 'Rust structural audit failed')
        report['rust']['wire'] = wire_contract(out/'rust-dictionaries/04-stylesheet-utf16.mdx', report['rust']['structural_audit'])
        require(report['rust']['wire']['status'] == 'passed', 'Rust wire contract failed')
        case = json.loads((kit/'rust-spec.json').read_text(encoding='utf-8'))['cases'][0]
        expected = sorted(case['entries'], key=lambda e: e['key'].lower())
        require([(e['key'],e['text']) for e in report['rust']['raw_rows']] == [(e['key'],e['text']) for e in expected], 'Rust source/body contract differs')
        require(report['rust']['header']['attributes'].get('StyleSheet') == case['stylesheet'], 'Rust raw stylesheet differs')
        reference_read = json.loads(run('rust-read-reference', experiment_command(5, 'inspect-json', reference)))
        report['official']['rust_reader_observation'] = reference_read
        require(reference_read.get('kind') == 'mdx' and Counter((e['key'],e['text']) for e in reference_read['entries']) ==
                Counter((e['key'],e['text']) for e in report['official']['raw_rows']), 'Rust/Python disagree on reference raw records')
        require(hash_file(reference) == report['official']['sha256'], 'Reference changed during Rust inspection')
        report['differences'] = differences(report['official'], report['rust'])
        # Differences are observations, not permission to waive a failed contract.
        report['status'] = 'comparison_complete_native_untested'
    except Exception as error:
        report['error'] = str(error)
    finally:
        (out/'reference-comparison-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(f"{report['status']}: {out/'reference-comparison-report.json'}")
    return 0 if report['status'] == 'comparison_complete_native_untested' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('compare'); p.add_argument('--kit', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    return prepare(args.output) if args.command == 'prepare' else compare_reference(args.kit, args.reference, args.output)


if __name__ == '__main__': raise SystemExit(main())
