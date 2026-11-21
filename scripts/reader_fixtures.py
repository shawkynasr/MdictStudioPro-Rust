"""Create native-reader fixtures and a manual results sheet; never claim GUI passes."""
import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zlib
import importlib.metadata
from patched_interop import ROOT, require, hash_file, experiment_command, verify_candidate_source, compare, read_python, inspect_header


def green_png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = (b"\0" + bytes([0, 180, 70]) * 24) * 24
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",24,24,8,2,0,0,0)) + chunk(b"IDAT",zlib.compress(pixels)) + chunk(b"IEND",b"")


def specification():
    red = '<span style="color:#9b1c31;font-weight:700;border:2px solid #9b1c31;">'
    blue = '<span style="color:#1d4ed8;text-decoration:underline;">'
    stylesheet = f"1\n{red}\n</span>\n2\n{blue}\n</span>"
    rows = [
        ("style-inline-red",red+"STYLE_ONE_OK</span>"), ("style-marker-red","`1`STYLE_ONE_OK"),
        ("style-inline-blue",blue+"STYLE_TWO_OK</span>"), ("style-marker-blue","`2`STYLE_TWO_OK"),
        ("resource-control",'<link rel="stylesheet" href="styles/check.css"><div class="mdd-check">MDD_CSS_OK</div><img src="images/green.png" width="24" height="24">'),
        ("字","<p>中文显示正常：字</p>"), ("مرحبا",'<p dir="rtl" style="text-align:right">أهلاً بالعالم</p>'),
        ("redirect","@@@LINK=style-marker-red"), ("duplicate","<p>DUPLICATE_ONE</p>"), ("duplicate","<p>DUPLICATE_TWO</p>"),
        ("a-b","<p>PUNCT_DASH</p>"), ("ab","<p>PUNCT_PLAIN</p>"), ("a b","<p>PUNCT_SPACE</p>")]
    return {"metadata":{"Format":"Html","Compact":"Yes","StyleSheet":stylesheet},
            "entries":[{"key":key,"text":text} for key,text in rows],
            "resources":[{"key":"\\styles\\check.css","bytes":list(b'.mdd-check {background:#00b446;color:#000;border:2px solid #000;}')},
                         {"key":"\\images\\green.png","bytes":list(green_png())}],
            "rendered":{"style-marker-red":red+"STYLE_ONE_OK</span>","style-marker-blue":blue+"STYLE_TWO_OK</span>"}}


def crlf_header(data):
    """Synthetic diagnostic fixture only: replace stylesheet line endings.

    Recompute framing/checksum; keep the entire key/record tail byte-identical.
    Never accept production dictionary paths for this operation.
    """
    length=struct.unpack(">I",data[:4])[0]
    payload=data[4:4+length]
    require(payload.endswith(b"\0\0"),"Fixture header lacks terminator")
    require(struct.unpack("<I",data[4+length:8+length])[0]==zlib.adler32(payload)&0xffffffff,"Fixture header checksum differs")
    xml=payload[:-2].decode("utf-16le")
    matches=list(re.finditer(r'StyleSheet="([^"]*)"',xml))
    require(len(matches)==1,"Ambiguous stylesheet attribute")
    match=matches[0]
    value=match.group(1)
    require("\r" not in value and "\n" in value,"Expected LF fixture stylesheet")
    xml=xml[:match.start(1)]+value.replace("\n","\r\n")+xml[match.end(1):]
    payload=xml.encode("utf-16le")+b"\0\0"
    return struct.pack(">I",len(payload))+payload+struct.pack("<I",zlib.adler32(payload)&0xffffffff)+data[8+length:]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--writer-revision",type=int,choices=[3,4],default=3)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={"status":"blocked","native_readers":"NOT_RUN","checks":{},"fixtures":[],"writer_revision":args.writer_revision}
    try:
        require(importlib.metadata.version("mdict-utils")=="1.3.14","Expected mdict-utils 1.3.14")
        verify_candidate_source(ROOT/f"vendor/mdictlib-0.2.8-studio-sort-v{args.writer_revision}",args.writer_revision)
        spec=specification()
        if args.writer_revision==4:
            spec["metadata"].update({"Compat":"Yes","CreationDate":"2026-10-28","DataSourceFormat":"106","RegisterBy":""})
        (out/"fixture-spec.json").write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding="utf-8")
        cmd=experiment_command(args.writer_revision,"reader-fixtures",out/"fixture-spec.json",out/"dictionaries")
        result=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
        (out/"build.log").write_text(result.stdout+"\nSTDERR:\n"+result.stderr,encoding="utf-8")
        require(result.returncode==0,"Rust fixture build failed; see build.log")
        built=json.loads(result.stdout)
        require(built["writer_patch_revision"]==args.writer_revision,"Wrong writer candidate")
        from mdict_utils.base.readmdict import MDX
        base_files=list((out/"dictionaries").glob("*.mdx"))
        require(len(base_files)==4,"Missing encoding/profile fixtures")
        for path in base_files:
            variant=path.with_stem(path.stem+"-crlf")
            variant.write_bytes(crlf_header(path.read_bytes()))
            shutil.copyfile(path.with_suffix(".mdd"),variant.with_suffix(".mdd"))
        expected=[(e["key"],e["text"]) for e in spec["entries"]]
        resources=[(r["key"],bytes(r["bytes"])) for r in spec["resources"]]
        for path in sorted((out/"dictionaries").glob("*.mdx")):
            name=path.stem
            try:
                inspect_header(path)
                compare(expected,read_python(path,"mdx"))
                result=subprocess.run(list(map(str,experiment_command(args.writer_revision,"inspect-json",path))),cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
                with (out/"build.log").open("a",encoding="utf-8") as stream:stream.write("\nINSPECT "+name+"\n"+result.stderr)
                require(result.returncode==0,"Rust raw-fixture inspection failed; see build.log")
                compare(expected,[(v["key"],v["text"]) for v in json.loads(result.stdout)["entries"]])
                compare(resources,read_python(path.with_suffix(".mdd"),"mdd"))
                styled={key.decode("utf-8"):value.decode("utf-8") for key,value in MDX(str(path),substyle=True).items()}
                for key,value in spec["rendered"].items():
                    require(styled.get(key)==value,f"Python stylesheet expansion differs for {key}")
                report["checks"][name]={"status":"passed","scope":"Rust/Python raw records, MDD bytes, Python stylesheet substitution; no GUI rendering"}
            except Exception as error:
                report["checks"][name]={"status":"failed","error":str(error)}
            report["fixtures"].append({"name":name,"mdx_sha256":hash_file(path),"mdd_sha256":hash_file(path.with_suffix(".mdd"))})
        with (out/"reader-results.csv").open("w",newline="",encoding="utf-8") as stream:
            fields=["reader","version","os","fixture","mdx_sha256","mdd_sha256","key","expected","result","notes","evidence_file"]
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            tests={"style-inline-red":"dark red bold text with red border", "style-marker-red":"same appearance as style-inline-red; no literal `1`", "style-inline-blue":"blue underlined text", "style-marker-blue":"same appearance as style-inline-blue; no literal `2`", "resource-control":"green CSS background and green square image", "字":"Chinese text readable", "مرحبا":"Arabic readable, joined and right aligned", "duplicate":"DUPLICATE_ONE and DUPLICATE_TWO both available", "redirect":"resolves to styled STYLE_ONE_OK", "a-b":"PUNCT_DASH", "ab":"PUNCT_PLAIN", "a b":"PUNCT_SPACE"}
            for fixture in report["fixtures"]:
                for reader in ["Reader A","Reader B"]:
                    for key,expected_view in tests.items():
                        writer.writerow({"reader":reader,"fixture":fixture["name"],"mdx_sha256":fixture["mdx_sha256"],"mdd_sha256":fixture["mdd_sha256"],"key":key,"expected":expected_view,"result":"NOT_RUN"})
        report["status"]="fixtures_checked_native_pending" if all(c["status"]=="passed" for c in report["checks"].values()) else "failed"
    except Exception as error:
        report["setup_error"]=str(error)
    finally:
        (out/"reader-fixture-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"{report['status']}: {out/'reader-fixture-report.json'}")
    return 0 if report["status"]=="fixtures_checked_native_pending" else 1


if __name__=="__main__":
    raise SystemExit(main())
