#!/usr/bin/env python
"""Readers v3: for each cvar pick the *unique* object (data value stored by the
stub via a per-cvar global) and the handle global, then list xref functions and
dump their disassembly.

Usage: python readers3.py <exe> <outdir> <cvar> [cvar2 ...]
"""
import sys, os, struct, bisect, re, json
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

class PE:
    def __init__(self, path):
        self.d, self.ib, self.secs, self.order = parse_pe(path)
        text_va, text_vsize, text_ptr, text_size = self.secs['.text']
        self.text = self.d[text_ptr:text_ptr+text_size]
        self.text_abs = self.ib + text_va
        arr = np.frombuffer(self.text, dtype=np.uint8)
        self.vals = np.lib.stride_tricks.sliding_window_view(arr, 4).view(np.uint32).ravel()
        self.idxs = np.arange(len(self.vals), dtype=np.uint64)
        self.base32 = ((self.text_abs + 4 + self.idxs) & 0xffffffff).astype(np.uint32)
        np.seterr(over='ignore')
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); self.md.detail = True
        self.funcs = self._pdata(); self.starts = [f[0] for f in self.funcs]

    def _pdata(self):
        vaddr, vsize, rawptr, rawsize = self.secs['.pdata']
        out = []
        for i in range(0, rawsize // 12 * 12, 12):
            begin, end, unwind = struct.unpack_from('<III', self.d, rawptr + i)
            if end <= begin: continue
            out.append((self.ib + begin, self.ib + end))
        out.sort(); return out

    def find_str(self, s):
        i = self.d.find(s.encode('ascii') + b'\0')
        if i == -1: return None
        return self.ib + self.off2rva(i)

    def off2rva(self, i):
        for name, (vaddr, vsize, rawptr, rawsize) in self.secs.items():
            if rawptr <= i < rawptr + rawsize:
                return vaddr + (i - rawptr)
        return None

    def va2off(self, va):
        rva = va - self.ib
        for name, (vaddr, vsize, rawptr, rawsize) in self.secs.items():
            if vaddr <= rva < vaddr + rawsize:
                return rawptr + (rva - vaddr)
        return None

    def sect_of(self, va):
        rva = va - self.ib
        for name, (vaddr, vsize, rawptr, rawsize) in self.secs.items():
            if vaddr <= rva < vaddr + max(vsize, rawsize):
                return name
        return '?'

    def cstr(self, va, maxlen=120, minlen=1):
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

    def xrefs(self, target_va):
        diff = np.uint32(target_va & 0xffffffff) - self.base32
        idx = np.nonzero(self.vals == diff)[0]
        return [self.text_abs + int(i) + 4 for i in idx]

    def disasm(self, start, end):
        off = start - self.text_abs
        return list(self.md.disasm(self.text[off:end - self.text_abs], start))

    def ripref(self, insn):
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                return insn.address + insn.size + op.mem.disp
        return None

def main():
    path, outdir = sys.argv[1], sys.argv[2]
    names = sys.argv[3:]
    os.makedirs(outdir, exist_ok=True)
    pe = PE(path)
    inv = {}
    for nm in names:
        nva = pe.find_str(nm)
        if nva is None:
            print(f"{nm}: name not found"); continue
        hits = pe.xrefs(nva)
        cands = []
        for h in hits:
            f = pe.func_of(h)
            if f and (f[1] - f[0]) < 0x600:
                cands.append((f, h))
        if not cands:
            print(f"{nm}: no small stub found ({len(hits)} hits)"); continue
        stub, _ = sorted(cands, key=lambda x: (x[0][1]-x[0][0]))[0]
        regs, globs = {}, []
        for insn in pe.disasm(*stub):
            t = pe.ripref(insn)
            if t is None:
                m = re.fullmatch(r'(r[a-z0-9]+), (0x[0-9a-f]+)', insn.op_str)
                if insn.mnemonic == 'mov' and m:
                    regs[m.group(1)] = int(m.group(2), 16)
                continue
            if insn.mnemonic == 'lea':
                dst = insn.op_str.split(',')[0].strip()
                regs[dst] = t
            elif insn.mnemonic == 'mov' and ',' in insn.op_str:
                src = insn.op_str.split(',')[1].strip()
                if re.fullmatch(r'(r[a-z0-9]+|e[a-z]+)', src) and src in regs:
                    globs.append((t, regs[src]))
        obj = None; handle = None; default = None
        for g, v in globs:
            if pe.cstr(v) is None and pe.sect_of(v) == '.data' and v != 0x1417dcac0 and v != 0:
                obj = v
        if obj is not None:
            for g, v in globs:
                if v == obj and abs(g - obj) <= 0x100:
                    handle = g
                    break
        defaults = [pe.cstr(v) for g, v in globs if pe.cstr(v) is not None]
        inv[nm] = {'stub': stub, 'obj': obj, 'handle': handle, 'defaults': defaults}
        print(f"{nm}: stub=0x{stub[0]:x} obj={hex(obj) if obj else None} handle={hex(handle) if handle else None} strings={defaults[:4]}")
    # readers
    report = []
    for nm, i in inv.items():
        if not i['obj']: continue
        for va in (i['obj'], i['handle']):
            fs = set()
            for h in pe.xrefs(va):
                f = pe.func_of(h)
                if f and f[0] != i['stub'][0]:
                    fs.add(f)
            report.append(f"\n##### {nm} readers of 0x{va:x}: {len(fs)} funcs")
            shown = 0
            for f in sorted(fs):
                if (f[1] - f[0]) > 0x1800:
                    report.append(f"--- func 0x{f[0]:x}-0x{f[1]:x} (size {f[1]-f[0]}, skipped big)")
                    continue
                if shown >= 30:
                    report.append("--- (more funcs elided)")
                    break
                shown += 1
                report.append(f"--- func 0x{f[0]:x}-0x{f[1]:x} (size {f[1]-f[0]})")
                n = 0
                for insn in pe.disasm(*f):
                    t = pe.ripref(insn)
                    ann = ''
                    if t is not None:
                        s = pe.cstr(t)
                        news = s is not None
                        if news and len(s) > 60:
                            s = s[:60] + '...'
                        ann = f'   ; {("str=" + repr(s)) if news else f"0x{t:x} [{pe.sect_of(t)}]"}'
                    report.append(f"  0x{insn.address:x}: {insn.mnemonic} {insn.op_str}{ann}")
                    n += 1
                    if n > 200:
                        report.append("   ...(truncated)")
                        break
    out = os.path.join(outdir, 'readers3.txt')
    open(out, 'w', encoding='utf-8').write('\n'.join(report))
    print(f"[written {out}] ({len(report)} lines)")

if __name__ == '__main__':
    main()
