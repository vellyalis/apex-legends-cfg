#!/usr/bin/env python
"""Enumerate cvar registration stubs globally.

A cvar is registered by a small function that lea's its NAME string (+ usually a
DEFAULT-value string) and passes a static .data object to the register routine.
We find every RIP-relative `lea r64, [rip+disp]` in .text, keep the ones that
land on a name-like string, map each site to its function via .pdata, and keep
functions small enough to be registrations.

Modes:
  scan  <exe> <out.tsv>   -> cvar, stub_rva, size, strings, data_refs, imms
  stat  <exe>             -> counts only
"""
import sys, struct, re, bisect
import numpy as np
import capstone
from cvar_registry import PE, NAME_RE

LEA_RE = re.compile(rb'[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]')
# 48 8d /r  or 4c 8d /r  with mod=00 rm=101 (RIP-relative)


class Text:
    def __init__(self, pe):
        self.pe = pe
        vaddr, vsize, rawptr, rawsize = pe.secs['.text']
        self.raw = pe.d[rawptr:rawptr + rawsize]
        self.va = pe.ib + vaddr
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True
        self.funcs, self.starts = self._pdata()

    def _pdata(self):
        d = self.pe.d
        vaddr, vsize, rawptr, rawsize = self.pe.secs['.pdata']
        out = []
        for i in range(0, rawsize // 12 * 12, 12):
            begin, end, unwind = struct.unpack_from('<III', d, rawptr + i)
            if end <= begin:
                continue
            out.append((self.pe.ib + begin, self.pe.ib + end))
        out.sort()
        return out, [f[0] for f in out]

    def func_of(self, va):
        i = bisect.bisect_right(self.starts, va) - 1
        if i >= 0 and self.funcs[i][0] <= va < self.funcs[i][1]:
            return self.funcs[i]
        return None

    def lea_sites(self):
        """(site_va, target_va) for RIP-relative lea in .text."""
        for m in LEA_RE.finditer(self.raw):
            i = m.start()
            disp = struct.unpack_from('<i', self.raw, i + 3)[0]
            site = self.va + i
            yield site, site + 7 + disp

    def disasm(self, f):
        off = f[0] - self.va
        return list(self.md.disasm(self.raw[off:f[1] - self.va], f[0]))

    def ripref(self, insn):
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                return insn.address + insn.size + op.mem.disp
        return None


def scan(pe, out=None, max_size=0x600, verbose=True):
    t = Text(pe)
    name_starts = pe.name_starts
    stub_strs = {}   # func_va -> [ (site, target) ]
    for site, tgt in t.lea_sites():
        if tgt not in name_starts:
            continue
        f = t.func_of(site)
        if f is None or (f[1] - f[0]) > max_size:
            continue
        stub_strs.setdefault(f, []).append((site, tgt))
    stubs = {}
    for f, hits in stub_strs.items():
        names = sorted({tgt for _, tgt in hits})
        stubs[f] = names
    if verbose:
        print(f".text funcs={len(t.funcs)}  small-func name-string lea sites -> {len(stub_strs)} funcs, "
              f"{sum(len(v) for v in stubs.values())} name refs")
    if out is None:
        return stubs
    rows = []
    for f, namevas in stubs.items():
        for nva in namevas:
            nm = pe.cstr(nva)
            strings, datas, imms = [], [], []
            for insn in t.disasm(f):
                r = t.ripref(insn)
                if r is None:
                    m = re.fullmatch(r'(r[a-z0-9]+), (0x[0-9a-f]+)', insn.op_str)
                    if m and insn.mnemonic == 'mov':
                        imms.append((m.group(1), m.group(2)))
                    continue
                if insn.mnemonic == 'lea':
                    s = pe.cstr(r)
                    if s is not None:
                        if r != nva:
                            strings.append(s)
                    else:
                        sec = pe.sect_of(r)
                        datas.append((hex(r), sec))
                elif insn.mnemonic == 'mov':
                    sec = pe.sect_of(r)
                    if sec:
                        datas.append((hex(r), sec))
                # movss/movsd immediates carry float defaults
                elif insn.mnemonic in ('movss', 'movsd', 'mov'):
                    imms.append((insn.mnemonic, insn.op_str))
            rows.append((f[0], f[1] - f[0], nm, strings, datas, imms))
    if out:
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write("# cvar\tstub_rva\tstub_size\tother_strings\tdata_refs\timms\n")
            for va, size, nm, strings, datas, imms in sorted(rows, key=lambda r: r[2]):
                fh.write(f"{nm}\t0x{va:x}\t0x{size:x}\t{'|'.join(strings)}\t"
                         f"{'|'.join(f'{a}[{b}]' for a, b in datas)}\t{'|'.join(str(i) for i in imms)}\n")
        print(f"{len(rows)} rows -> {out}")
    return stubs


def main():
    mode, exe = sys.argv[1], sys.argv[2]
    pe = PE(exe)
    if mode == 'stat':
        scan(pe, None)
    else:
        scan(pe, sys.argv[3])


if __name__ == '__main__':
    main()
