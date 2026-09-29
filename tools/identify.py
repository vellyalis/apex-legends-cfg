#!/usr/bin/env python
"""Identify data addresses: who references them, in which function, and what
strings that function touches (cvar names, defaults). Also dumps float constants.

Usage: python identify.py <exe> <out.txt> <0xADDR> [0xADDR ...]
Env: CONSTS=0xADDR,0xADDR  -> also print float value at those VAs
"""
import sys, os, struct, bisect, re
import numpy as np
import capstone

def parse_pe(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3c)[0]
    coff = e + 4
    nsec, = struct.unpack_from('<H', d, coff + 2)
    opt_size, = struct.unpack_from('<H', d, coff + 16)
    opt = coff + 20
    magic, = struct.unpack_from('<H', d, opt)
    ib, = struct.unpack_from('<Q', d, opt + 24) if magic == 0x20b else struct.unpack_from('<I', d, opt + 28)
    secs = {}
    so = opt + opt_size
    for i in range(nsec):
        off = so + i * 40
        name = d[off:off+8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, vaddr = struct.unpack_from('<II', d, off + 8)
        rawsize, rawptr = struct.unpack_from('<II', d, off + 16)
        secs[name] = (vaddr, vsize, rawptr, rawsize)
    return d, ib, secs

class PE:
    def __init__(self, path):
        self.d, self.ib, self.secs = parse_pe(path)
        text_va, vsize, text_ptr, text_size = self.secs['.text']
        self.text = self.d[text_ptr:text_ptr+text_size]
        self.text_abs = self.ib + text_va
        arr = np.frombuffer(self.text, dtype=np.uint8)
        self.vals = np.lib.stride_tricks.sliding_window_view(arr, 4).view(np.uint32).ravel()
        base = (self.text_abs + 4 + np.arange(len(self.vals), dtype=np.uint64)) & 0xffffffff
        self.base32 = base.astype(np.uint32)
        np.seterr(over='ignore')
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); self.md.detail = True
        self.funcs = []
        vaddr, vsize, rawptr, rawsize = self.secs['.pdata']
        for i in range(0, rawsize//12*12, 12):
            b, e, u = struct.unpack_from('<III', self.d, rawptr+i)
            if e > b: self.funcs.append((self.ib+b, self.ib+e))
        self.funcs.sort(); self.starts = [f[0] for f in self.funcs]

    def va2off(self, va):
        rva = va - self.ib
        for name, (vaddr, vsize, rawptr, rawsize) in self.secs.items():
            if vaddr <= rva < vaddr + rawsize:
                return rawptr + (rva - vaddr)
        return None

    def float_at(self, va):
        o = self.va2off(va)
        return struct.unpack_from('<f', self.d, o)[0] if o else None

    def cstr(self, va, maxlen=90, minlen=1):
        off = self.va2off(va)
        if off is None: return None
        out = []
        for b in self.d[off:off+maxlen]:
            if b == 0: break
            if 32 <= b < 127: out.append(chr(b))
            else: return None
        return ''.join(out) if len(out) >= minlen else None

    def func_of(self, va):
        i = bisect.bisect_right(self.starts, va) - 1
        if i >= 0 and self.funcs[i][0] <= va < self.funcs[i][1]:
            return self.funcs[i]
        return None

    def xrefs(self, va):
        diff = np.uint32(va & 0xffffffff) - self.base32
        idx = np.nonzero(self.vals == diff)[0]
        return [self.text_abs + int(i) + 4 for i in idx]

    def disasm(self, s, e):
        return list(self.md.disasm(self.text[s-self.text_abs:e-self.text_abs], s))

    def ripref(self, insn):
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                return insn.address + insn.size + op.mem.disp
        return None

def main():
    path, out = sys.argv[1], sys.argv[2]
    addrs = [int(a, 16) for a in sys.argv[3:]]
    pe = PE(path)
    lines = []
    for va in addrs:
        hits = pe.xrefs(va)
        fs = {}
        for h in hits:
            f = pe.func_of(h)
            if f: fs.setdefault(f, []).append(h)
        lines.append(f"\n### 0x{va:x}: {len(hits)} xrefs in {len(fs)} funcs")
        for f, hs in sorted(fs.items()):
            strings = []
            for insn in pe.disasm(*f):
                t = pe.ripref(insn)
                if t is None: continue
                s = pe.cstr(t)
                if s: strings.append(s)
            uniq = []
            for s in strings:
                if s not in uniq: uniq.append(s)
            lines.append(f"  func 0x{f[0]:x}-0x{f[1]:x} size={f[1]-f[0]} refs={len(hs)}")
            lines.append(f"     strings: {uniq[:12]}")
    consts = os.environ.get('CONSTS')
    if consts:
        lines.append("\n### constants")
        for a in consts.split(','):
            a = a.strip()
            if not a: continue
            va = int(a, 16)
            lines.append(f" 0x{va:x} = {pe.float_at(va)}")
    open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
