#!/usr/bin/env python
"""Resolve cvar descriptor objects to names by scanning for pointers to name
strings in .rdata/.data  (object = pointer_location - 0x10).

Usage:
  python resolve_objects.py <exe> map <out.tsv>          # build object->name map
  python resolve_objects.py <exe> query <out.txt> 0xADDR [0xADDR ...]
  python resolve_objects.py <exe> desc  <out.txt> 0xADDR [0xADDR ...]   # dump descriptor
  python resolve_objects.py <exe> callers <out.txt> 0xADDR              # call rel32 callers
"""
import sys, os, re, struct, bisect
import numpy as np

def parse_pe(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3c)[0]
    coff = e + 4
    nsec, = struct.unpack_from('<H', d, coff + 2)
    opt_size, = struct.unpack_from('<H', d, coff + 16)
    opt = coff + 20
    magic, = struct.unpack_from('<H', d, opt)
    ib, = struct.unpack_from('<Q', d, opt + 24) if magic == 0x20b else struct.unpack_from('<I', d, opt + 28)
    secs, order = {}, []
    so = opt + opt_size
    for i in range(nsec):
        off = so + i * 40
        name = d[off:off+8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, vaddr = struct.unpack_from('<II', d, off + 8)
        rawsize, rawptr = struct.unpack_from('<II', d, off + 16)
        secs[name] = (vaddr, vsize, rawptr, rawsize)
        order.append(name)
    return d, ib, secs, order

def build_map(d, ib, secs):
    # 1) all ascii strings in .rdata with their VAs
    vaddr, vsize, rawptr, rawsize = secs['.rdata']
    rdata = d[rawptr:rawptr+rawsize]
    strs = {}
    for m in re.finditer(rb'[\x20-\x7e]{3,200}', rdata):
        s = m.group().decode('ascii')
        va = ib + vaddr + m.start()
        strs[va] = s
    # 2) all 8-byte pointers in .data/.rdata pointing at those strings
    ptrs = {}
    for secname in ('.data', '.rdata'):
        vaddr, vsize, rawptr, rawsize = secs[secname]
        blob = d[rawptr:rawptr+rawsize]
        arr = np.frombuffer(blob, dtype=np.uint8)
        if len(arr) < 8: continue
        vals = arr[:len(arr)//8*8].view(np.uint64)
        for target_va in strs:
            # search occurrences of this VA
            pass
        # group: build value->offsets for those in .rdata range
        rrange_lo, rrange_hi = ib + secs['.rdata'][0], ib + secs['.rdata'][0] + secs['.rdata'][3]
        mask = (vals >= rrange_lo) & (vals < rrange_hi)
        sel = np.nonzero(mask)[0]
        for i in sel:
            tva = int(vals[i])
            s = strs.get(tva)
            if s is None: continue
            loc = ib + vaddr + int(i)*8
            ptrs.setdefault((loc, tva), s)
    return strs, ptrs

def main():
    path, mode = sys.argv[1], sys.argv[2]
    out = sys.argv[3]
    args = sys.argv[4:]
    d, ib, secs, order = parse_pe(path)
    strs, ptrs = build_map(d, ib, secs)
    def va2off(va):
        rva = va - ib
        for name, (vaddr, vsize, rawptr, rawsize) in secs.items():
            if vaddr <= rva < vaddr + rawsize:
                return rawptr + (rva - vaddr)
        return None
    lines = []
    if mode == 'map':
        seen = {}
        for (loc, tva), s in ptrs.items():
            obj = loc - 0x10
            if obj in seen: continue
            seen[obj] = s
        lines.append("object_va\tname")
        for obj in sorted(seen):
            lines.append(f"0x{obj:x}\t{seen[obj]}")
        open(out, 'w', encoding='utf-8').write('\n'.join(lines))
        print(f"map entries: {len(seen)} -> {out}")
    elif mode == 'query':
        rev = {}
        for (loc, tva), s in ptrs.items():
            rev.setdefault(loc - 0x10, s)
        for a in args:
            va = int(a, 16)
            lines.append(f"0x{va:x}: {rev.get(va, '(no name string at +0x10)')}")
        print('\n'.join(lines))
        open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    elif mode == 'desc':
        for a in args:
            va = int(a, 16)
            lines.append(f"\n=== descriptor 0x{va:x} ===")
            for off in range(0, 0x80, 8):
                o = va2off(va + off)
                if o is None: break
                q, = struct.unpack_from('<Q', d, o)
                i32, = struct.unpack_from('<i', d, o)
                f32, = struct.unpack_from('<f', d, o)
                s = strs.get(q)
                note = f'str "{s}"' if s else (f'float {f32:.6g}' if 0.0 < abs(f32) < 1e7 else (f'int {i32}' if i32 else ''))
                lines.append(f" +0x{off:02x}: 0x{q:016x} {note}")
        print('\n'.join(lines)); open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    elif mode == 'callers':
        text_va, text_vsize, text_ptr, text_size = secs['.text']
        text = d[text_ptr:text_ptr+text_size]
        targets = {int(a, 16) for a in args}
        hits = []
        for i in range(len(text)-5):
            if text[i] == 0xE8:
                rel, = struct.unpack_from('<i', text, i+1)
                tgt = ib + text_va + i + 5 + rel
                if tgt in targets:
                    hits.append((ib + text_va + i, tgt))
        lines.append(f"callers: {len(hits)}")
        for src, tgt in hits:
            lines.append(f"0x{src:x} -> 0x{tgt:x}")
        print('\n'.join(lines)); open(out, 'w', encoding='utf-8').write('\n'.join(lines))

if __name__ == '__main__':
    main()
