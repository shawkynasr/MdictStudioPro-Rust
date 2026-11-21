"""Run every Python contract with canonical platform temporary paths.

macOS /var aliases /private/var. Canonicalizing the temporary root keeps
historical lexical path assertions meaningful without editing protected tests.
"""
from pathlib import Path
import tempfile
import unittest


def main():
    tempfile.tempdir = str(Path(tempfile.gettempdir()).resolve())
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_*.py')
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
