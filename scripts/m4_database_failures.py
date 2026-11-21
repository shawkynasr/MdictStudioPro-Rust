"""Qualify MDX/SQLite failure publication and deterministic cancellation on the Mac."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

from m2_closeout import inventory
from m3_shell import ROOT, ADAPTER, TXT_RUNTIME, check_adapter_lock, sources


TESTS = [
    ('import-cancellation', TXT_RUNTIME,
     'mdx_database::tests::mdx_to_database_preserves_decoded_header_and_duplicate_bodies_and_cancels',
     ['UTF-8/UTF-16 import cancellation during decoding and before database commit',
      'existing DB unchanged; malformed MDX creates no output']),
    ('rebuild-cancellation', TXT_RUNTIME,
     'database_mdx::tests::rebuild_cancellation_overwrite_and_final_destination_race_publish_nothing',
     ['rebuild cancellation during spool, copy, verification and before commit',
      'destination created at final commit is preserved; staging files removed']),
    ('adapter-failures-recovery', ADAPTER,
     'tests::database_failure_publications_preserve_files_and_allow_recovery',
     ['shared publication jobs reject existing destinations in both directions',
      'bad MDX checksum and invalid SQLite publish no output',
      'sources and existing destinations unchanged; no staging artifacts',
      'failed jobs return no receipt and can be forgotten',
      'successful conversion after failures reuses destination and releases admission'])
]


def require_one_test(stdout):
    if not re.search(r'test result: ok\. 1 passed; 0 failed;', stdout):
        raise RuntimeError('Expected exactly one passing native test; zero-test runs are refused')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m4-database-out-failures'))
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m4-database-out'):
        parser.error('Use a new m4-database-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-database-failures-v1', 'status': 'failed',
              'native_tests_executed': False, 'GUI_checks_executed': False,
              'cancellation_method': 'deterministic worker progress callbacks, not GUI timing',
              'steps': [], 'checks': []}
    protected = current = None

    def run(name, command, one_test=False):
        report['stage'] = name
        print(name, flush=True)
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                              timeout=1200, env={**os.environ, 'STUDIO_TEST_PYTHON': sys.executable})
        (out / (name + '.log')).write_text(done.stdout + '\nSTDERR:\n' + done.stderr, encoding='utf-8')
        report['steps'].append({'name': name, 'command': command, 'returncode': done.returncode})
        if done.returncode:
            raise RuntimeError(f'{name} failed; see {out / (name + ".log")}')
        if one_test:
            require_one_test(done.stdout)

    try:
        protected = inventory()
        current = sources()
        report.update(protected_source_sha256=protected, source_sha256=current)
        cargo = shutil.which('cargo')
        if not cargo:
            raise RuntimeError('Rust toolchain missing; run on the Rust-enabled Mac')
        # Only isolated M3 seed locks may normalize; never alter M2 locks.
        for name, manifest in [('runtime', TXT_RUNTIME), ('adapter', ADAPTER)]:
            lock = ROOT / Path(manifest).with_name('Cargo.lock')
            check_adapter_lock(lock)
            run(name + '-resolve', [cargo, 'metadata', '--offline', '--format-version', '1', '--manifest-path', manifest])
            report[name + '_lock'] = check_adapter_lock(lock)
        for name, manifest, test, checks in TESTS:
            run(name, [cargo, 'test', '--offline', '--locked', '--manifest-path', manifest,
                       '--lib', test, '--', '--exact', '--nocapture'], one_test=True)
            report['checks'].append({'name': name, 'test': test, 'status': 'passed', 'assertions': checks})
        report.update(native_tests_executed=True, status='database_failure_checks_passed', stage='complete')
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['traceback'] = traceback.format_exc()
    finally:
        try:
            if protected is not None:
                assert inventory() == protected, 'Protected M2 source changed'
            if current is not None:
                assert sources() == current, 'M3/M4 source changed'
        except Exception as error:
            report.update(status='failed', source_error=str(error))
        (out / 'm4-database-failures-report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(report['status'] + ': ' + str(out / 'm4-database-failures-report.json'))
    return 0 if report['status'] == 'database_failure_checks_passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
