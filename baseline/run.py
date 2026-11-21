"""Stable subprocess entrypoint. Check mode never updates committed expected files."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["record", "check"])
    p.add_argument("--snapshot", type=Path)
    args = p.parse_args()
    expected = HERE / "expected"
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        output = expected if args.action == "record" else Path(tmp)
        cmd = [sys.executable, str(HERE / "capture.py"), "--output", str(output)]
        if args.snapshot:
            if args.action != "record":
                p.error("--snapshot is only allowed with record")
            cmd += ["--snapshot", str(args.snapshot.resolve())]
        subprocess.run(cmd, env=env, check=True)
        if args.action == "check":
            expected_names = {p.name for p in expected.iterdir() if p.is_file()}
            actual_names = {p.name for p in output.iterdir() if p.is_file()}
            if expected_names != actual_names:
                raise AssertionError(f"File inventory differs: {expected_names ^ actual_names}")
            for name in sorted(expected_names):
                if (expected / name).read_bytes() != (output / name).read_bytes():
                    raise AssertionError(f"Baseline changed: {name}")
                print(f"PASS {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
