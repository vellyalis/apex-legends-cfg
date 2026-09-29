#!/usr/bin/env python
"""Count static xrefs to every cvar handle global (obj+0x38) in .text.

A handle is a global that holds a pointer to the descriptor; game code loads it
with `mov reg, [rip+handle]` (disp32 = handle - (site+4)). One numpy pass.

Usage: python cvar_readers.py <exe> <cvar_fields.tsv> <out.tsv>
"""
import sys, struct
import numpy as np
from cvar_registry import PE


def main():
    exe, fields, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pe = PE(exe)
    vaddr, vsize, rawptr, rawsize = pe.secs['.text']
    text = pe.d[rawptr:rawptr + rawsize]
    text_abs = pe.ib + vaddr
    arr = np.frombuffer(text, dtype=np.uint8)
    vals = np.lib.stride_tricks.sliding_window_view(arr, 4).view(np.uint32).ravel()
    idx = np.arange(len(vals), dtype=np.uint64)
    base = ((text_abs + 4 + idx) & 0xffffffff).astype(np.uint32)

    rows = []
    for line in open(fields, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        rows.append((c[0], int(c[2], 16)))

    handles = np.array([((obj + 0x38) & 0xffffffff) for _, obj in rows], dtype=np.uint64)
    nz = np.nonzero(vals)[0]
    tgt = (base[nz].astype(np.uint64) + vals[nz].astype(np.uint64)) & 0xffffffff
    hit = np.isin(tgt, handles)
    hits = nz[hit]
    tgts = tgt[hit]
    counts = {}
    sites = {}
    for i, t in zip(hits, tgts):
        t = int(t)
        counts[t] = counts.get(t, 0) + 1
        sites.setdefault(t, []).append(text_abs + int(i))
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write("# cvar\tobj_rva\txref_sites\tsite_examples\n")
        for name, obj in rows:
            h = (obj + 0x38) & 0xffffffff
            n = counts.get(h, 0)
            ex = ','.join(f'0x{a:x}' for a in sites.get(h, [])[:6])
            fh.write(f"{name}\t0x{obj:x}\t{n}\t{ex}\n")
    nz_cnt = sum(1 for name, o in rows if counts.get((o + 0x38) & 0xffffffff, 0))
    print(f"{len(rows)} cvars, {nz_cnt} with >=1 handle xref -> {out}")


if __name__ == '__main__':
    main()
