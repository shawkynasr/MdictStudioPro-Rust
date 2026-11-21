# Bounded larger-file, RSS and staged-failure qualification

Real dictionary rebuilding has passed offline comparisons and user-reported
native tests in both readers. This next gate is entirely offline. No generated
stress or damaged file should be imported into MDict or GoldenDict.

Update project files in place, retaining .venv, vendor, real-corpus-inputs and
rebuild-out. Run from the project root:

```sh
.venv/bin/python scripts/stress_qualification.py --output stress-out
```

Return **stress-out/stress-report.json** and the referenced log for any failure.
No native app tests are needed. Use a new output directory for a repeated run.

## Default standard preset

- 49,152 MDX definitions, 1,024 ASCII bytes each: 48 MiB of body text.
- 128 MDD resources, 128 KiB each: 16 MiB of pseudorandom binary payloads.
- Deliberately small key/record targets exercise many block boundaries.
- The standard MDX must exceed 32 MiB on disk, beyond the conservative prior
  real-rebuild input budget. The engine stress builder/reader are tested at that
  size while the real-rebuild command must still refuse it under its preset.

Generation is deterministic and bounded: no existing dictionaries, source
fonts or app scan folders are used. At least 512 MiB free disk is required for
this preset, excluding unrelated future Cargo cache growth. The v6 engine and
dependency graph are unchanged. A new stress module in the real-rebuild probe
generates and verifies every expected key/payload, with sampled exact lookups.
The independent auditor checks block checksums, geometry and record termination.
Separate full Rust/Python scans compare exact payload multisets, duplicate
multiplicities, metadata and physical-order digests using SQLite.

## Memory observations and watchdog

The driver compiles first, obtains the actual executable path from Cargo's JSON
artifact output, and measures each direct Rust test process with POSIX wait4.
macOS returns maximum RSS in bytes; Linux's value is converted from KiB. The
report retains peak RSS bytes and elapsed time per process. Compiler/Cargo and
Python reader memory and separate dump-rows scans are explicitly excluded from
this Rust RSS measurement. The build is debug/unoptimized: elapsed times are
qualification observations, not release-performance benchmark results.

The default measured RSS budget is 768 MiB and the per-process timeout is 600
seconds. Periodic ps sampling kills a process if it observes RSS above budget;
the exact post-exit peak is also checked. Sampling may miss a brief spike until
process exit and can overshoot between samples. This is a watchdog and a measured
qualification threshold, not an allocator-level or guaranteed OS memory limit.
Do not call it proof of production memory bounds. A smaller budget can be set
with --rss-limit-mib; a budget failure remains a failed observation, not a pass.

The driver requires POSIX wait4 (macOS/Linux). Windows memory qualification stays
open. The script's measurements do not establish whole-application memory use,
browser/webview memory or native reader behavior with large files.

## Failure behavior

The batch tests:

- Truncated record data, invalid compression tags and oversized declarations:
  clean error exit required; a panic, timeout or signal is not a rejection pass.
- Checksum-only corruption: the independent auditor must reject it. The Rust
  default reader's accept/reject result is recorded without assuming its default
  policy enforces every checksum. Production checksum policy remains open.
- Injected write failure: no final destination may be published. This simulates
  an I/O error; it does not fill a real disk or prove every disk-full behavior.
- Existing destination: refusal must leave its sentinel and contents unchanged.
- Forced SIGKILL during staging: no final destination is published; the Python
  controller cleans the temporary workspace it owns after reaping the child.
  This does not prove automatic cleanup after power loss or controller failure.
- A fresh valid build/verify after failures. A Rust unit test separately tests
  a successful new operation in the same process after the injected write error.
- Exact 500,000-record and 256 MiB decoded-budget boundaries in Rust unit tests.

The report includes source hashes, process metrics, exact failure observations,
reader comparisons and generated-input hash integrity. It contains no native
test claim and never reads or modifies the original corpus.

## Scope of a successful result

The standard success status is **standard_stress_subset_passed_M1_open**. It
closes this bounded test batch only. It does not qualify arbitrary large files,
all corruption classes, fresh-source TXT/XLSX packing, the general metadata and
sorting policy, production allocator limits, native large-file rendering or M1.

A --profile quick option provides a small smoke run. Its success is explicitly
quick_smoke_passed_not_large_file_qualification; it cannot replace the standard
gate. Rust/Cargo are unavailable in the authoring environment, so the new Rust
stress module still needs compilation and execution on the user's Mac.
