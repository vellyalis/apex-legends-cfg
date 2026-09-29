#!/usr/bin/env python
"""cvar descriptor + reader graph v2 (PE x64). Correct VA/RVA handling.

Usage: python cvar_graph2.py <exe> <out.txt> <name1> [name2 ...]
Prints per cvar:
  - stub function
  - descriptor base (lowest unique-global data target) and a qword dump of the
    descriptor range [base, base+0x80) with string/float annotations
  - reader functions of the descriptor range and of the handle global
Then a MATRIX of functions touching >=2 of our cvars.
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
        self.text_va = text_va; self.text_ptr = text_ptr; self.text_size = text_size
        self.text = self.d[text_ptr:text_ptr+text_size]
        self.text_abs = self.ib + text_va
        arr = np.frombuffer(self.text, dtype=np.uint8)
        self.vals = np.lib.stride_tricks.sliding_window_view(arr, 4).view(np.uint32).ravel()
        self.idxs = np.arange(len(self.vals), dtype=np.uint64)
        self.base32 = ((self.text_abs + 4 + self.idxs) & 0xffffffff).astype(np.uint32)
        np.seterr(over='ignore')
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); self.md.detail = True
        self.funcs = self._pdata()
        self.starts = [f[0] for f in self.funcs]

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
        for name, (vaddr, vsize, rawptr, rawsize) in self.secs.items():
            if rawptr <= i < rawptr + rawsize:
                return self.ib + vaddr + (i - rawptr)
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

    def xrefs(self, target_va, cap=6000):
        diff = np.uint32(target_va & 0xffffffff) - self.base32
        mask = self.vals == diff
        idx = np.nonzero(mask)[0]
        return [self.text_abs + int(i) + 4 for i in idx[:cap]], int(len(idx))

    def disasm(self, start, end):
        off = start - self.text_abs
        return list(self.md.disasm(self.text[off:end - self.text_abs], start))

    def ripref(self, insn):
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                return insn.address + insn.size + op.mem.disp
        return None

def main():
    path, out = sys.argv[1], sys.argv[2]
    names = sys.argv[3:]
    pe = PE(path)
    lines = []
    info = {}
    glob_users = {}
    # stage 1: stubs and their glob stores
    for nm in names:
        nva = pe.find_str(nm)
        if nva is None:
            info[nm] = {'err': 'name string not found'}; continue
        hits, n = pe.xrefs(nva)
        stub = next((pe.func_of(h) for h in hits if pe.func_of(h)), None)
        if not stub:
            info[nm] = {'err': 'no stub', 'name_va': nva}; continue
        regs, globs = {}, []
        for insn in pe.disasm(*stub):
            t = pe.ripref(insn)
            if t is None:
                m = re.fullmatch(r'(r[a-z0-9]+), (0x[0-9a-f]+)', insn.op_str)
                if insn.mnemonic == 'mov' and m:
                    try: regs[m.group(1)] = int(m.group(2), 16)
                    except Exception: pass
                continue
            if insn.mnemonic == 'lea':
                dst = insn.op_str.split(',')[0].strip()
                regs[dst] = t
            elif insn.mnemonic == 'mov' and ',' in insn.op_str:
                src = insn.op_str.split(',')[1].strip()
                if re.fullmatch(r'(r[a-z0-9]+|e[a-z]+)', src) and src in regs:
                    globs.append((t, regs[src]))
        info[nm] = {'name_va': nva, 'stub': stub, 'globs': globs}
        for g, v in globs:
            glob_users.setdefault(g, set()).add(nm)

    # stage 2: descriptor ranges per cvar
    for nm, i in info.items():
        if 'err' in i: continue
        uniq = [(g, v) for g, v in i['globs'] if len(glob_users.get(g, [])) == 1]
        data = [(g, v) for g, v in uniq if pe.sect_of(v) == '.data' or pe.sect_of(g) == '.data']
        i['uniq_globs'] = uniq
        # descriptor = cluster of data addresses around the most-referenced unique data address
        cands = sorted(set(v for g, v in data if pe.sect_of(v) == '.data') | set(g for g, v in data))
        i['data_targets'] = cands
        lines.append(f"\n===== {nm}")
        lines.append(f"  stub 0x{i['stub'][0]:x}-0x{i['stub'][1]:x}  name_va 0x{i['name_va']:x}")
        for g, v in i['globs']:
            share = len(glob_users.get(g, []))
            s = pe.cstr(v); 
            lines.append(f"  glob 0x{g:x} <- 0x{v:x} [{pe.sect_of(v)}] shared_by={share} {('str='+repr(s)) if s else ''}")
        if cands:
            base = min(cands)
            lines.append(f"  descriptor dump @0x{base:x}:")
            for off in range(0, 0x80, 8):
                o = pe.va2off(base + off)
                if o is None: break
                q = struct.unpack_from('<Q', pe.d, o)[0]
                i32, = struct.unpack_from('<i', pe.d, o)
                f32, = struct.unpack_from('<f', pe.d, o)
                s = pe.cstr(q)
                note = f'-> "{s}"' if s else (f'float {f32:.6g}' if 0.0 < abs(f32) < 1e7 else (f'int {i32}' if i32 else '0'))
                lines.append(f"    +0x{off:02x}: 0x{q:016x}  {note}")

    # stage 3: readers
    va2cvars = {}
    for nm, i in info.items():
        if 'err' in i: continue
        for va in i.get('data_targets', []):
            va2cvars.setdefault(va, set()).add(nm)
    func_cvars = {}
    lines.append("\n## READERS")
    for va, nms in sorted(va2cvars.items()):
        hits, n = pe.xrefs(va)
        funcs = set()
        for h in hits:
            f = pe.func_of(h)
            if f: funcs.add(f)
        lines.append(f"-- 0x{va:x} [{','.join(sorted(nms))}]: hits={n} funcs={len(funcs)}")
        for f in sorted(funcs):
            for nm in nms:
                if f[0] == info[nm]['stub'][0]:
                    continue
                func_cvars.setdefault(f, set()).add(nm)
    lines.append("\n## MATRIX (funcs touching >=2 cvars)")
    multi = {f: cs for f, cs in func_cvars.items() if len(cs) >= 2}
    for f, cs in sorted(multi.items()):
        lines.append(f"func 0x{f[0]:x}-0x{f[1]:x}: {sorted(cs)}")
    lines.append(f"(reader funcs total {len(func_cvars)}, multi {len(multi)})")
    open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines[:500]))
    print(f"[written {out}]")

if __name__ == '__main__':
    main()
