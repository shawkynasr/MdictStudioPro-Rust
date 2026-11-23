"""Recognize only the new direct compressor edge over an exact reviewed lock.

This proves equivalence to an anchored older lock except for one local package's
direct edge to an already-present compressor. It does not qualify new native code.
"""
import hashlib

LOCKS = {
    'm3/export-io/Cargo.lock', 'm3/txt-runtime/Cargo.lock',
    'm3/indexed-sessions/Cargo.lock', 'm3/native-adapter/Cargo.lock',
    'm3/desktop/src-tauri/Cargo.lock',
}


def matches_reviewed_lock(name, data, accepted):
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    if digest(data) in accepted:
        return True
    if name not in LOCKS:
        return False
    sections = data.split(b'\n[[package]]\n')
    candidates = [i for i, part in enumerate(sections)
                  if part.startswith(b'name = "studio-export-io"\n')]
    if len(candidates) != 1:
        return False
    index = candidates[0]
    lines = sections[index].splitlines(keepends=True)
    edges = [i for i, line in enumerate(lines)
             if line in (b' "miniz_oxide",\n', b' "miniz_oxide 0.9.1",\n')]
    if len(edges) != 1:
        return False
    del lines[edges[0]]
    sections[index] = b''.join(lines)
    return digest(b'\n[[package]]\n'.join(sections)) in accepted
