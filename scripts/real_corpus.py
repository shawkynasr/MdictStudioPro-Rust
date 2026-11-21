"""Read-only corpus comparison using Rust and Python, with disk-backed hashes.

No source dictionaries are packed, extracted, repaired, or overwritten.
"""
import argparse
import collections
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from patched_interop import ROOT, require, experiment_command, verify_candidate_source, decode


def file_hash(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def create_manifest(directory,destination):
    directory=directory.resolve()
    require(directory.is_dir(),"Select a dictionary directory")
    files=sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in {".mdx",".mdd"})
    require(bool(files),"No MDX/MDD dictionaries found in selected directory")
    manifest={"cases":[{"id":f"dictionary-{i:03d}","path":str(p.resolve()),"tags":[],"lookup_keys":[]} for i,p in enumerate(files,1)]}
    with destination.open("x",encoding="utf-8") as stream:
        json.dump(manifest,stream,ensure_ascii=False,indent=2)
    return len(files)


def connect(path):
    db=sqlite3.connect(path)
    db.execute("PRAGMA cache_size=-4096")
    db.execute("PRAGMA temp_store=FILE")
    db.execute("CREATE TABLE records(k BLOB NOT NULL,h BLOB NOT NULL,r INTEGER NOT NULL DEFAULT 0,p INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(k,h)) WITHOUT ROWID")
    return db


def record(db,engine,key,payload):
    require(engine in {"r","p"},"Invalid comparison engine")
    require(isinstance(key,str),"Record key is not Unicode")
    require(isinstance(payload,bytes),"Record body is not bytes")
    # Hash exact decoded UTF-8 bodies for MDX, exact binary bytes for MDD.
    digest=hashlib.sha256(payload).digest()
    db.execute(f"INSERT INTO records(k,h,{engine}) VALUES(?,?,1) ON CONFLICT(k,h) DO UPDATE SET {engine}={engine}+1",(key.encode("utf-8"),digest))


def payload(row,kind):
    return row["text"].encode("utf-8") if kind=="mdx" else bytes(row["bytes"])


def ingest(lines,db,engine,kind):
    header=None;count=0;ended=False
    for raw in lines:
        row=json.loads(raw)
        require(not ended,"Output after end marker")
        if row["type"]=="header":
            require(header is None and count==0,"Duplicate/out-of-order header")
            require(row["kind"]==kind,"Wrong dictionary kind")
            header=row["attributes"]
        elif row["type"]=="row":
            require(header is not None,"Record before header")
            record(db,engine,row["key"],payload(row,kind));count+=1
        elif row["type"]=="end":
            require(header is not None and row["records"]==count,"Incomplete/wrong record count")
            ended=True
        else:
            raise ValueError("Unknown record protocol message")
    require(ended,"Truncated reader stream: no end marker")
    db.commit()
    return {"records":count,"attributes":header}


def differences(db):
    return db.execute("SELECT count(*) FROM records WHERE r<>p").fetchone()[0]


def stream_command(cmd,db,engine,kind,log,timeout):
    start=time.monotonic()
    with log.open("wb") as stderr:
        process=subprocess.Popen(list(map(str,cmd)),cwd=ROOT,stdout=subprocess.PIPE,stderr=stderr,start_new_session=os.name=="posix")
        def stop():
            try:
                if os.name=="posix":os.killpg(process.pid,signal.SIGKILL)
                elif process.poll() is None:process.kill()
            except ProcessLookupError:pass
        timer=threading.Timer(timeout,stop);timer.daemon=True;timer.start()
        try:
            result=ingest(process.stdout,db,engine,kind)
            require(process.wait()==0,f"Reader exited unsuccessfully; see {log.name}")
            result["elapsed_seconds"]=round(time.monotonic()-start,3)
            return result
        finally:
            timer.cancel()
            if process.poll() is None: stop()
            process.wait()
            process.stdout.close()


def python_rows(path):
    # Reserve the original stdout pipe, redirect ordinary/native stdout to stderr
    # before importing the reader. Diagnostics cannot corrupt the row protocol.
    protocol=os.fdopen(os.dup(1),"w",encoding="utf-8")
    os.dup2(2,1);sys.stdout=sys.stderr
    from mdict_utils.base.readmdict import MDX,MDD
    kind="mdd" if path.suffix.lower()==".mdd" else "mdx"
    reader=MDD(str(path)) if kind=="mdd" else MDX(str(path),substyle=False)
    def emit(row):
        protocol.write(json.dumps(row,ensure_ascii=False)+"\n")
    emit({"type":"header","kind":kind,"attributes":{decode(k):decode(v) for k,v in reader.header.items()}})
    count=0
    for key,value in reader.items():
        row={"type":"row","key":decode(key)}
        row.update({"text":decode(value)} if kind=="mdx" else {"bytes":list(value)})
        emit(row);count+=1
    emit({"type":"end","records":count});protocol.flush();protocol.close()


def check(manifest_path,out,timeout):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    report={"status":"blocked","cases":[],"environment":{"python":sys.version,"os":platform.platform()},
            "comparison":"exact UTF-8 keys and SHA-256 payload multisets with duplicate counts; no whitespace/Unicode normalization",
            "not_proven":["native_reader_rendering","pack_or_unpack_parity","large_file_resource_limits","all_lookup_keys","metadata_contract_resolution"]}
    try:
        require(importlib.metadata.version("mdict-utils")=="1.3.14","Expected mdict-utils 1.3.14")
        vendor=ROOT/"vendor/mdictlib-0.2.8-studio-sort-v3"
        verify_candidate_source(vendor,3)
        report["writer_source_sha256"]=file_hash(vendor/"src/write/mod.rs")
        report["environment"]["mdict-utils"]=importlib.metadata.version("mdict-utils")
        for tool in ["rustc","cargo"]:
            version=subprocess.run([tool,"--version"],capture_output=True,text=True,encoding="utf-8",timeout=30)
            require(version.returncode==0,f"Cannot identify {tool}")
            report["environment"][tool]=version.stdout.strip()
        report["source_sha256"]={str(p.relative_to(ROOT)):file_hash(p) for p in [ROOT/"Cargo.lock",ROOT/"experiments/legacy-sort/Cargo.lock",ROOT/"experiments/legacy-sort/src/readers.rs",ROOT/"scripts/real_corpus.py"]}
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        require(isinstance(manifest.get("cases"),list) and manifest["cases"],"Manifest must contain real dictionary cases")
        seen=set()
        for index,case in enumerate(manifest["cases"],1):
            identity=case["id"];require(identity not in seen,"Duplicate corpus ID");seen.add(identity)
            path=Path(case["path"]).expanduser()
            if not path.is_absolute(): path=manifest_path.resolve().parent/path
            path=path.resolve();require(path.suffix.lower() in {".mdx",".mdd"},"Only MDX/MDD files are supported")
            item={"id":identity,"path":str(path),"tags":case.get("tags",[]),"status":"failed","engines":{}}
            item["companions"]=[]
            for companion in case.get("companions",[]):
                candidate=Path(companion).expanduser()
                if not candidate.is_absolute(): candidate=manifest_path.resolve().parent/candidate
                item["companions"].append({"path":str(candidate),"present":candidate.is_file()})
            report["cases"].append(item)
            db=None
            try:
                before=file_hash(path);item.update(sha256=before,size_bytes=path.stat().st_size)
                kind=path.suffix[1:].lower();db=connect(out/f"case-{index:03d}.sqlite")
                for engine,cmd in [("r",experiment_command(3,"dump-rows",path)),("p",[sys.executable,Path(__file__).resolve(),"python-rows",path])]:
                    try:
                        detail=stream_command(cmd,db,engine,kind,out/f"case-{index:03d}-{engine}.log",timeout)
                        item["engines"][engine]={"status":"passed",**detail}
                    except Exception as error:
                        item["engines"][engine]={"status":"failed","error":str(error)}
                require(all(v["status"]=="passed" for v in item["engines"].values()),"One or both reader scans failed; comparison not established")
                item["different_key_payload_counts"]=differences(db)
                require(item["different_key_payload_counts"]==0,"Decoded record multisets differ")
                rust_meta=item["engines"]["r"]["attributes"];python_meta=item["engines"]["p"]["attributes"]
                item["metadata_differences"]={k:{"rust":rust_meta.get(k),"python":python_meta.get(k)} for k in sorted(set(rust_meta)|set(python_meta)) if rust_meta.get(k)!=python_meta.get(k)}
                # Existing source headwords guarantee these are exact-key probes,
                # compared to Python's complete physical-record inventory.
                samples=[r[0].decode("utf-8") for r in db.execute("SELECT DISTINCT k FROM records ORDER BY k LIMIT 8")]
                keys=list(dict.fromkeys(case.get("lookup_keys",[])+samples))
                item["lookups"]={}
                for key in keys:
                    try:
                        result=subprocess.run(list(map(str,experiment_command(3,"lookup-json",path,key))),cwd=ROOT,capture_output=True,text=True,encoding="utf-8",timeout=timeout)
                        require(result.returncode==0,"Rust lookup command failed: "+result.stderr[-500:])
                        rows=json.loads(result.stdout)["rows"]
                        actual=collections.Counter(hashlib.sha256(payload(row,kind)).digest() for row in rows)
                        expected=collections.Counter(dict(db.execute("SELECT h,p FROM records WHERE k=? AND p>0",(key.encode("utf-8"),))))
                        require(bool(expected),"Requested key absent in independent Python inventory")
                        require(actual==expected,"Lookup payload multiplicity differs from Python physical inventory")
                        item["lookups"][key]={"status":"passed","records":sum(expected.values())}
                    except Exception as error:
                        item["lookups"][key]={"status":"failed","error":str(error)}
                require(all(v["status"]=="passed" for v in item["lookups"].values()),"One or more sampled lookups failed")
                item["status"]="records_passed_metadata_differs" if item["metadata_differences"] else "passed"
            except Exception as error:
                item["error"]=str(error)
            finally:
                if db is not None: db.close()
                if path.is_file():
                    after=file_hash(path);item["sha256_after"]=after
                    if item.get("sha256")!=after: item.update(status="failed",error="Input changed during verification")
        report["declared_tags"]=dict(collections.Counter(tag for case in report["cases"] for tag in case["tags"]))
        report["status"]="passed_reader_comparison_only" if all(c["status"]=="passed" for c in report["cases"]) else "partial_or_failed"
    except Exception as error:
        report["setup_error"]=str(error)
    finally:
        (out/"corpus-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"{report['status']}: {out/'corpus-report.json'}")
    return 0 if report["status"]=="passed_reader_comparison_only" else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    init=commands.add_parser("init");init.add_argument("directory",type=Path);init.add_argument("--manifest",type=Path,default=Path("corpus-local.json"))
    run=commands.add_parser("check");run.add_argument("--manifest",type=Path,required=True);run.add_argument("--output",type=Path,required=True);run.add_argument("--timeout",type=float,default=1800)
    worker=commands.add_parser("python-rows");worker.add_argument("path",type=Path)
    args=parser.parse_args()
    if args.command=="python-rows": python_rows(args.path);return 0
    if args.command=="init": print(f"Listed {create_manifest(args.directory,args.manifest)} files in {args.manifest}; review tags and lookup_keys before checking");return 0
    require(args.timeout>0,"Timeout must be positive")
    return check(args.manifest,args.output,args.timeout)


if __name__=="__main__":
    raise SystemExit(main())
