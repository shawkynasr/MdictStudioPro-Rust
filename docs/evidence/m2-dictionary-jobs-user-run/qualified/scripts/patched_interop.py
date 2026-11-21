"""Bidirectional fixture tests for patched Rust writer and original Python writer.

Requires mdict-utils==1.3.14 and prepared sort-experiment vendor source. Writes
a report even when preflight or individual checks fail. No installed package,
source fixture, or existing output directory is overwritten.
"""
import argparse
import ast
from collections import Counter
import contextlib
import functools
import hashlib
import importlib.metadata
import io
import json
import locale
from pathlib import Path
import platform
import re
import shutil
import string
import struct
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]


def experiment_command(revision, *args):
    vendor = ROOT / f"vendor/mdictlib-0.2.8-studio-sort-v{revision}"
    # Pass TOML as an argv value, never shell text. Lockfile identity is unchanged.
    return ["cargo", "--config", "patch.crates-io.mdictlib.path=" + json.dumps(str(vendor)),
            "run", "--locked", "--manifest-path", "experiments/legacy-sort/Cargo.toml", "--", *args]


def verify_candidate_source(vendor, revision):
    marker = json.loads((vendor / "STUDIO_LEGACY_SORT_EXPERIMENT.json").read_text(encoding="utf-8"))
    require(marker.get("patch_revision") == revision, "Wrong prepared source revision")
    source = (vendor / "src/write/mod.rs").read_bytes()
    if revision>=4:
        from prepare_sort_experiment import native_wire_patch
        source=native_wire_patch(source.decode("utf-8"),reverse=True).encode("utf-8")
    if revision >= 3:
        anchor = b'Self::Utf16Le => "UTF-16",'
        require(source.count(anchor) == 1, "Missing/ambiguous UTF-16 compatibility label")
        source = source.replace(anchor, b'Self::Utf16Le => "UTF-16LE",', 1)
    passing = json.loads((ROOT / "docs/evidence/interop-v2-user-run/interop-report.json").read_text(encoding="utf-8"))
    require(hashlib.sha256(source).hexdigest() == passing["source_sha256"]["vendor/mdictlib-0.2.8-studio-sort-v2/src/write/mod.rs"], "Candidate differs from the passing v2 writer beyond the selected revision's explicit edits")
    sort_source = (vendor / "src/write/studio_legacy_sort.rs").read_bytes()
    if revision==6:
        from prepare_sort_experiment import preserve_order_patch
        sort_source=preserve_order_patch(sort_source.decode('utf-8'),reverse=True).encode('utf-8')
    if revision>=5:
        from prepare_sort_experiment import literal_sort_patch
        sort_source=literal_sort_patch(sort_source.decode("utf-8"),reverse=True).encode("utf-8")
    require(hashlib.sha256(sort_source).hexdigest() == passing["source_sha256"]["patches/studio_legacy_sort.rs"], "Sort module changed beyond selected diagnostic profile")
    for name, checksum in marker["modified_files"].items():
        require(hash_file(vendor / name) == checksum, f"Prepared source changed: {name}")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(expected, actual, *, order=False):
    """Exact strings and bytes only: no strip(), newline or Unicode normalization."""
    if order:
        require(expected == actual, f"Physical rows differ: expected={expected!r}, actual={actual!r}")
    else:
        require(Counter(expected) == Counter(actual), f"Key/payload multisets differ: expected={expected!r}, actual={actual!r}")


def decode(value):
    return value.decode("utf-8", errors="strict") if isinstance(value, bytes) else value


def inspect_header(path):
    """Independent framing check, using stdlib XML/ADLER32, bounded to 1 MiB."""
    with path.open("rb") as stream:
        prefix=stream.read(4)
        require(len(prefix)==4,"Header length missing")
        length=struct.unpack(">I",prefix)[0]
        require(2<=length<=1024*1024 and length%2==0,"Invalid fixture header length")
        payload=stream.read(length)
        crc=stream.read(4)
    require(len(payload)==length and len(crc)==4,"Truncated header framing")
    terminated=payload.endswith(b"\x00\x00")
    require(terminated,"UTF-16LE header has no terminating zero pair")
    require(zlib.adler32(payload)&0xffffffff==struct.unpack("<I",crc)[0],"Header checksum mismatch")
    attrs=ET.fromstring(payload[:-2].decode("utf-16le",errors="strict")).attrib
    require(attrs.get("GeneratedByEngineVersion")=="2.0","Wrong/missing generated version")
    return {"payload_bytes":length,"terminated":True,"checksum_valid":True,"attributes":attrs}


def legacy_fixture_records(text):
    """Model this UTF-8 fixture's raw body span, retaining its final line ending.

    This is the legacy TXT-input contract, NOT a normalization of binary output.
    """
    result, key, body = [], None, []
    for raw in text.splitlines(keepends=True):
        line=raw.removesuffix("\n").removesuffix("\r")
        if key is None:
            require(bool(line) and line!="</>","Invalid fixture key")
            key=line
        elif line=="</>":
            require(bool(body),"Empty fixture body")
            result.append((key,"".join(body)))
            key,body=None,[]
        else:
            body.append(raw)
    require(key is None,"Unterminated fixture")
    return result


def read_python(path, kind):
    # Public low-level classes used by mdict-utils; readers yield UTF-8 keys.
    from mdict_utils.base.readmdict import MDX, MDD
    reader = MDX(str(path)) if kind == "mdx" else MDD(str(path))
    return [(decode(k), decode(v) if kind == "mdx" else bytes(v)) for k, v in reader.items()]


def custom_writer_class():
    """Use the exact app class AST with REAL writer dependencies, no GUI import."""
    from mdict_utils.writer import MDictWriter, _OffsetTableEntry
    original = ROOT / "baseline/legacy/MdictStudio.py"
    tree = ast.parse(original.read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "MDictWriterCustomSort")
    namespace = {"MDictUtilsWriter":MDictWriter, "_OffsetTableEntry":_OffsetTableEntry,
                 "functools":functools, "locale":locale, "re":re, "string":string}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(original),"exec"),namespace)
    return namespace["MDictWriterCustomSort"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--writer-revision", type=int, choices=[2, 3, 4], default=2)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {"status":"running","harness_revision":3,"writer_patch_revision":args.writer_revision,"checks":{},"environment":{"python":sys.version,"os":platform.system(),"release":platform.release(),"machine":platform.machine()},
              "not_proven":["reader_apps","legacy_encodings","metadata_stylesheets","large_files","non_C_locale"]}
    log = out / "interop.log"

    def run(*cmd):
        completed = subprocess.run(list(map(str,cmd)), cwd=ROOT, capture_output=True, text=True)
        with log.open("a",encoding="utf-8") as stream:
            stream.write(json.dumps(list(map(str,cmd)))+"\n"+completed.stdout+"\nSTDERR:\n"+completed.stderr+"\n")
        if completed.returncode:
            raise RuntimeError(f"Command failed ({completed.returncode}); see interop.log: {cmd[0]}")
        return completed.stdout

    def step(name, action):
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                detail = action()
            report["checks"][name] = {"status":"passed","detail":detail}
        except Exception as error:
            report["checks"][name] = {"status":"failed","error":str(error),"traceback":traceback.format_exc()}
        finally:
            with log.open("a",encoding="utf-8") as stream:
                stream.write(f"CHECK {name}\n"+captured.getvalue()+"\n")

    def dump_rust(path, kind):
        value = json.loads(run("cargo","run","--locked","-p","studio-engine-probe","--","dump-json",path))
        return [(v["key"],v["text"]) for v in value["entries"]] if kind=="mdx" else [(v["key"],bytes(v["bytes"])) for v in value["resources"]]

    try:
        version = importlib.metadata.version("mdict-utils")
        require(version=="1.3.14",f"Expected mdict-utils==1.3.14, found {version}")
        require(shutil.which("cargo") is not None,"Cargo is unavailable")
        vendor=ROOT / f"vendor/mdictlib-0.2.8-studio-sort-v{args.writer_revision}"
        require(vendor.is_dir(),f"Run python3 scripts/prepare_sort_experiment.py --revision {args.writer_revision}")
        verify_candidate_source(vendor, args.writer_revision)
        require((ROOT / "experiments/legacy-sort/Cargo.lock").is_file(),"Experiment Cargo.lock missing")
        locale.setlocale(locale.LC_COLLATE,"C")
        report["environment"].update({"mdict-utils":version,"rustc":run("rustc","--version").strip(),"cargo":run("cargo","--version").strip(),"collation":"C"})
        # Fingerprint actual patched source, not just the path dependency lock.
        report["source_sha256"] = {str(p.relative_to(ROOT)):hash_file(p) for p in [
            ROOT/"Cargo.lock",ROOT/"experiments/legacy-sort/Cargo.lock",ROOT/"patches/studio_legacy_sort.rs",
            vendor/"src/write/mod.rs",vendor/"src/write/studio_legacy_sort.rs"]}
        cases = json.loads((ROOT/"baseline/cases.json").read_text(encoding="utf-8"))
        oracle = json.loads((ROOT/"baseline/expected/sort-C-locale.json").read_text(encoding="utf-8"))
        core = out/"rust-default"
        patched = out/"rust-patched"
        # Use the same patched engine for default-sort and explicit-sort output.
        # The upstream root workspace remains an unchanged historical baseline.
        run(*experiment_command(args.writer_revision,"baseline",ROOT/"baseline/cases.json",core))
        run(*experiment_command(args.writer_revision,patched))
        expected_mdx = [(v["key"],v["text"]) for v in cases["engine_entries"]]
        expected_mdd = [(v["key"],bytes(v["bytes"])) for v in cases["engine_resources"]]

        def check_python(path, kind, expected, order=False):
            framing=inspect_header(path)
            actual = read_python(path,kind)
            compare(expected,actual,order=order)
            return {"records":len(actual),"comparison":"ordered_exact" if order else "exact_multiset","header":framing}

        step("rust_default_mdx_to_python",lambda:check_python(core/"qualification.mdx","mdx",expected_mdx))
        step("rust_default_mdd_to_python",lambda:check_python(core/"qualification.mdd","mdd",expected_mdd))
        for style in ["mdict-utils","mdxbuilder"]:
            for kind in ["mdx","mdd"]:
                values = {key:(f"<p>record-{i}: {key}</p>" if kind=="mdx" else bytes([0,255,128,i])+bytes([42])*40) for i,key in enumerate(cases["sort_keys"])}
                expected = [(key,values[key]) for key in oracle[f"{style}:{kind}"]]
                step(f"rust_{style}_{kind}_to_python",lambda style=style,kind=kind,expected=expected:check_python(patched/f"{style}.{kind}",kind,expected,True))
            duplicates = ["Apple","apple","APPLE","apple","a-b","ab","a b"]
            for kind in ["mdx","mdd"]:
                expected = [(key,f"<p>record-{i}: {key}</p>" if kind=="mdx" else bytes([0,255,128,i])+bytes([42])*40) for i,key in enumerate(duplicates)]
                step(f"rust_{style}_{kind}_duplicates_to_python",lambda style=style,kind=kind,expected=expected:check_python(patched/f"{style}-duplicates.{kind}",kind,expected))

        writer = custom_writer_class()
        from mdict_utils.writer import pack_mdx_txt
        source = core/"qualification.txt"
        expected_legacy_mdx=legacy_fixture_records(source.read_bytes().decode("utf-8",errors="strict"))
        # source_text explicitly writes one separator LF before each delimiter.
        # The legacy parser includes it in the encoded body. Verify that exact
        # policy; never strip or rewrite either reader's returned payload.
        compare([(k,v+"\n") for k,v in expected_mdx],expected_legacy_mdx)
        resource_dir = core/"resources"
        for style in ["mdict-utils","mdxbuilder"]:
            for kind in ["mdx","mdd"]:
                def reverse(style=style,kind=kind):
                    if kind=="mdx":
                        data = pack_mdx_txt(str(source),encoding="utf-8")
                        expected = expected_legacy_mdx
                    else:
                        data = [{"key":"\\"+p.relative_to(resource_dir).as_posix().replace("/","\\"),"path":str(p),"size":p.stat().st_size,"pos":0} for p in sorted(resource_dir.rglob("*")) if p.is_file()]
                        expected = expected_mdd
                    output = out/f"python-{style}.{kind}"
                    engine = writer(data,title="Legacy interoperability",description="Synthetic fixture",encoding="utf-8",is_mdd=kind=="mdd",sort_style=style,key_size=48,record_size=32)
                    with output.open("wb") as stream:
                        engine.write(stream)
                    # Check independently against the input fixture, NOT against
                    # another writer's potentially identical data-loss behavior.
                    compare(expected,dump_rust(output,kind))
                    compare(expected,read_python(output,kind))
                    return {"records":len(expected),"writer":"original_MDictWriterCustomSort","sha256":hash_file(output),"both_readers_agree":True,"source_policy":"legacy TXT body includes delimiter-preceding LF" if kind=="mdx" else "binary bytes unchanged"}
                step(f"python_{style}_{kind}_to_rust",reverse)
        report["status"] = "passed" if all(v["status"]=="passed" for v in report["checks"].values()) else "failed"
        report["artifact_sha256"] = {str(p.relative_to(out)):hash_file(p) for p in out.rglob("*") if p.suffix in {".mdx",".mdd"}}
    except Exception as error:
        report["status"] = "blocked"
        report["setup_error"] = str(error)
        report["setup_traceback"] = traceback.format_exc()
    finally:
        (out/"interop-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"{report['status']}: {out/'interop-report.json'}")
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":
    raise SystemExit(main())
