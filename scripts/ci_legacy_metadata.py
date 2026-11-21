"""Verify the archived revision-3 diagnostic without relabelling its failures.

This is a historical-behavior regression check, not metadata qualification.
Any changed check, outcome, failure reason, dependency or setup result fails CI.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'docs/evidence/metadata-v3-completed-user-run/metadata-codec-report.json'
BASELINE_SHA256 = 'b84757a766692b396da65e38891ff75eaa45b35bbe929211868ee0563ef72a67'


def load_baseline():
    data = BASELINE.read_bytes()
    if hashlib.sha256(data).hexdigest() != BASELINE_SHA256:
        raise ValueError('Archived metadata diagnostic identity changed')
    return json.loads(data)


def verify_observation(actual, baseline, returncode):
    if returncode != 1:
        raise ValueError(f'Unexpected diagnostic exit status: {returncode}; expected the archived failed diagnostic')
    for field in ('status', 'suite', 'harness_revision', 'writer_patch_revision', 'counts'):
        if actual.get(field) != baseline.get(field):
            raise ValueError(f'Diagnostic {field} differs from archived revision 3')
    if actual.get('setup_error') or actual.get('setup_traceback'):
        raise ValueError('Diagnostic setup failed')
    observed = actual.get('checks', {})
    expected = baseline['checks']
    if not isinstance(observed, dict) or set(observed) != set(expected):
        raise ValueError('Diagnostic check inventory changed')
    for name, result in expected.items():
        current = observed[name]
        for field in ('status', 'error', 'dependencies'):
            if current.get(field) != result.get(field):
                raise ValueError(f'Diagnostic changed: {name}: {field}')
    return {'status': 'archived_diagnostic_reproduced', 'diagnostic_status': actual['status'],
            'counts': actual['counts'], 'metadata_qualified': False,
            'scope': 'Exact historical revision-3 outcomes only; failed/unsupported/blocked checks remain so.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = load_baseline()
    if args.output.exists() or args.output.is_symlink():
        parser.error('Output must not exist; never reuse a previous diagnostic report')
    output = args.output.resolve()
    completed = subprocess.run([sys.executable, str(ROOT / 'scripts/metadata_codecs.py'),
                                '--writer-revision', '3', '--output', str(output)], cwd=ROOT)
    try:
        actual = json.loads((output / 'metadata-codec-report.json').read_text(encoding='utf-8'))
        observation = verify_observation(actual, baseline, completed.returncode)
    except Exception as error:
        print(f'Historical diagnostic regression: {error}', file=sys.stderr)
        return 1
    (output / 'ci-observation.json').write_text(json.dumps(observation, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(observation, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
