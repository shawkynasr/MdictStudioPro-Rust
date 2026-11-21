"""Capture uploaded legacy code as an oracle; never import the GUI or run plugins on launch.

Run through run.py to fix PYTHONHASHSEED before Python starts.
"""
import argparse
import ast
import functools
import hashlib
import importlib.util
import json
import locale
import os
from pathlib import Path
import re
import string
import sys
import tempfile
import zipfile

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "baseline"
PLUGINS = {
    "cc_cedict": ("cccedict_plugin", "CCCEDICTPlugin"),
    "moe_revised": ("edudict_plugin", "EduDictRevisedPlugin"),
    "moe_revised_wfg": ("WFG_desgin_Plugin", "WFGRevisedPlugin"),
    "moe_concise": ("concise_plugin", "MOEConcisePlugin"),
    "moe_idioms": ("idiom_plugin", "MOEIdiomPlugin"),
    "moe_mini": ("mini_plugin", "MOEMiniPlugin"),
}


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot(archive):
    """Only copy an explicit allowlist, with no archive path extraction."""
    files = ["MdictStudio.py", "base_plugin.py", "excel_utils.py", "build.py", "requirements.txt", "README.md", "LICENSE", ".github/workflows/build.yml"]
    files += [f"plugins/{module}.py" for module, _ in PLUGINS.values()]
    hashes = {}
    with zipfile.ZipFile(archive) as z:
        for name in files:
            data = z.read("MdictStudioPro-main/" + name)
            dest = HERE / "legacy" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        assets = {i.filename.removeprefix("MdictStudioPro-main/"): {"bytes": i.file_size, "sha256": hashlib.sha256(z.read(i)).hexdigest()} for i in z.infolist() if not i.is_dir() and "/assets/" in i.filename}
    dump(HERE / "source-manifest.json", {"archive_sha256": hashlib.sha256(Path(archive).read_bytes()).hexdigest(), "archive_commit": "6e181e22193472518d7966b66bac4dc2f2b32f83", "files": hashes, "assets": assets})


def load_plugins():
    sys.path.insert(0, str(HERE / "legacy"))
    result = {}
    for key, (module, cls) in PLUGINS.items():
        spec = importlib.util.spec_from_file_location(module, HERE / "legacy" / "plugins" / (module + ".py"))
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        result[key] = getattr(loaded, cls)()
    return result


def workbook(path, rows):
    wb = Workbook()
    ws = wb.active
    headers = list(dict.fromkeys(k for row in rows for k in row))
    ws.append(headers)
    for row in rows:
        ws.append([row.get(k) for k in headers])
    wb.save(path)
    wb.close()


def sort_oracle(keys, style, is_mdd):
    """Execute the original class AST, with transport-only writer dependencies stubbed.

    This validates comparator behavior, NOT mdict-utils binary writing.
    """
    tree = ast.parse((HERE / "legacy" / "MdictStudio.py").read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "MDictWriterCustomSort")
    env = {"MDictUtilsWriter": object, "re": re, "string": string, "locale": locale, "functools": functools, "_OffsetTableEntry": lambda **kw: kw}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "legacy-sort-ast", "exec"), env)
    writer = object.__new__(env["MDictWriterCustomSort"])
    writer._sort_style, writer._is_mdd = style, is_mdd
    writer._python_encoding, writer._encoding_length = "utf-8", 1
    items = [{"key": k, "path": "fixture", "size": 0, "pos": 0} for k in keys]
    writer._build_offset_table(items)
    return [v["key"] for v in items]


def capture(dest):
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("Use baseline/run.py: golden generation requires PYTHONHASHSEED=0")
    locale.setlocale(locale.LC_COLLATE, "C")
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    plugins = load_plugins()
    from excel_utils import _cell_to_str, read_excel_as_dicts
    dest.mkdir(parents=True, exist_ok=True)
    observed = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        xlsx = tmp / "moe.xlsx"
        workbook(xlsx, cases["moe_rows"])
        for key, plugin in plugins.items():
            source = xlsx
            if key == "cc_cedict":
                source = tmp / "cedict.u8"
                source.write_text(cases["cedict"], encoding="utf-8")
            out = tmp / (key + ".txt")
            progress, logs = [], []
            plugin.convert(str(source), str(out), "utf-8", progress.append, logs.append)
            data = out.read_bytes()
            (dest / (key + ".txt")).write_bytes(data)
            observed[key] = {"sha256": hashlib.sha256(data).hexdigest(), "records": data.count(b"\n</>\n"), "final_progress": progress[-1], "id": plugin.id, "registration_key": plugin.id or plugin.name, "encodings": plugin.default_encodings, "options_schema": plugin.options_schema}
            # Error paths are separately observed, not replaced by mock converters.
            bad = tmp / "empty.xlsx"
            workbook(bad, [{"irrelevant": "no headword"}])
            if key == "cc_cedict":
                bad = tmp / "empty.u8"
                bad.write_bytes(b"")
            try:
                plugin.convert(str(bad), str(out), "utf-8", lambda _: None, lambda _: None)
            except Exception as exc:
                observed[key]["empty_error"] = {"type": type(exc).__name__, "message": str(exc)}
            else:
                raise AssertionError(f"{key}: empty source unexpectedly accepted")
        normalized = [{"input": repr(v), "output": _cell_to_str(v)} for v in [None, True, False, 1, 1.0, 1.25, " padded ", " 001 ", "\n字\t"]]
        # Test actual workbook behavior as well as the cell helper.
        wb = Workbook()
        ws = wb.active
        ws.append([" label ", None, "number", "flag"])
        ws.append([" 字 ", " 001 ", 1.0, True])
        ws.append([None, None, None, None])
        normal_path = tmp / "normalization.xlsx"
        wb.save(normal_path)
        wb.close()
        dump(dest / "normalization.json", {"cells": normalized, "workbook_rows": read_excel_as_dicts(normal_path)})
    sorts = {f"{style}:{'mdd' if mdd else 'mdx'}": sort_oracle(cases["sort_keys"], style, mdd) for style in ["mdxbuilder", "mdict-utils"] for mdd in [False, True]}
    dump(dest / "sort-C-locale.json", sorts)
    dump(dest / "observations.json", observed)
    return observed


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.snapshot:
        snapshot(args.snapshot)
    capture(args.output)
