#!/usr/bin/env python
"""Refined xref counts per cvar: handle(obj+0x38), value slots(obj+0x58/0x5c),
and the object base itself. One numpy pass over .text dwords.

Usage: python cvar_readers2.py <exe> <fields.tsv> <out.tsv>
"""
import sys
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
    base = ((text_abs + 4 + idx) & 0xffffffff).astype(np.uint64)
    nz = np.nonzero(vals)[0]
    tgt = (base[nz] + vals[nz].astype(np.uint64)) & 0xffffffff
    nnz = vals[nz]

    rows = []
    for line in open(fields, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        rows.append((c[0], int(c[1], 16), int(c[2], 16)))   # name, stub, obj

    targets = np.array(sorted({(o + off) & 0xffffffff for _, _, o in rows
                               for off in (0x00, 0x38, 0x58)}), dtype=np.uint64)
    hit = np.isin(tgt, targets)
    hitsites = {}
    for i, t in zip(nz[hit], tgt[hit]):
        hitsites.setdefault(int(t), []).append(text_abs + int(i))

    def sites_for(target):
        return hitsites.get(target & 0xffffffff, [])

    with open(out, 'w', encoding='utf-8') as fh:
        fh.write("# cvar\tobj\thandle_xrefs\tvalue_xrefs\tobj_xrefs\tstub\tw_handle\tw_value\tw_obj\n")
        for name, stub, obj in rows:
            hs = sites_for(obj + 0x38)
            vs = sites_for(obj + 0x58)
            os_ = sites_for(obj)
            fh.write(f"{name}\t0x{obj:x}\t{len(hs)}\t{len(vs)}\t{len(os_)}\t0x{stub:x}\t"
                     f"{len([s for s in hs if not (stub <= s < stub + 0x600)])}\t"
                     f"{len([s for s in vs if not (stub <= s < stub + 0x600)])}\t"
                     f"{len([s for s in os_ if not (stub <= s < stub + 0x600)])}\t")
            fh.write('\n')
    print('->', out)


if __name__ == '__main__':
    main()
