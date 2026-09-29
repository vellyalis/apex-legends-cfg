#!/usr/bin/env python
"""Extract per-cvar descriptor fields from the registration stubs (static).

Stub pattern (observed, v3.0.1.28):
    lea rax, [rip+name]                  ; 'name'
    mov [rip+obj+0x10], rax              ; name ptr
    lea rbx, [rip+obj]
    mov [rip+obj+0x38], rbx              ; handle = self
    mov [rip+obj+0x28], imm32            ; FCVAR flags
    mov [rip+obj+0x40], rax2             ; default-value string
    mov [rip+obj+0x50], imm32            ; type/id
    mov [rip+obj+0x64], imm32(float)     ; min
    mov [rip+obj+0x68], imm32(float)     ; max

Output TSV: cvar, stub_rva, obj_rva, flags, default, type, min, max, name_vas

Usage: python cvar_fields.py <exe> <out.tsv>
"""
import sys, struct, re
import capstone
from cvar_registry import PE, flag_str
from cvar_stubs import Text

STORE_RE = re.compile(r'^(byte|word|dword|qword) ptr \[rip \+ (0x[0-9a-f]+)\], (.*)$')
LOAD_RE = re.compile(r'^([a-z0-9]+), (byte|word|dword|qword) ptr \[rip \+ (0x[0-9a-f]+)\]$')
MOVE_RE = re.compile(r'^([a-z0-9]+), (0x[0-9a-f]+)$')
IMM_RE = re.compile(r'^-?(?:0x[0-9a-f]+|\d+)$')


def f32(v):
    return struct.unpack('<f', struct.pack('<I', v & 0xffffffff))[0]


def analyze(pe, t, f):
    """Return dict of descriptor fields or None."""
    regs = {}          # reg -> ('str', va) | ('va', va) | ('imm', val)
    stores = {}        # obj-relative offset keyed by absolute VA -> value desc
    name_vas = []
    for insn in t.disasm(f):
        m = insn.mnemonic
        if m == 'lea':
            r = t.ripref(insn)
            if r is None:
                continue
            dst = insn.op_str.split(',')[0].strip()
            s = pe.cstr(r)
            regs[dst] = ('str', r) if s is not None else ('va', r)
            continue
        mm = MOVE_RE.match(insn.op_str)
        if m == 'mov' and mm and not insn.op_str.startswith(('byte', 'word', 'dword', 'qword')):
            regs[mm.group(1)] = ('imm', int(mm.group(2), 16))
            continue
        ml = LOAD_RE.match(insn.op_str)
        if m == 'mov' and ml:
            # load from [rip+X] into reg -> unknown; drop
            regs.pop(ml.group(1), None)
            continue
        ms = STORE_RE.match(insn.op_str)
        if m in ('mov', 'movss', 'movsd') and ms:
            r = t.ripref(insn)
            if r is None:
                continue
            src = ms.group(3).strip()
            if src in regs:
                kind, val = regs[src]
                if kind == 'str':
                    stores.setdefault(r, []).append(('str', pe.cstr(val), val))
                elif kind == 'va':
                    stores.setdefault(r, []).append(('va', val))
                elif kind == 'imm':
                    stores.setdefault(r, []).append(('imm', val))
            else:
                if IMM_RE.match(src):
                    stores.setdefault(r, []).append(('imm', int(src, 0)))
                elif src.endswith('xmm1') or src in ('xmm0', 'xmm2'):
                    stores.setdefault(r, []).append(('xmm', src))
            continue
        # any reg write invalidates tracking
        dst = insn.op_str.split(',')[0].strip() if insn.op_str else ''
        if dst and not dst.startswith(('[', 'byte', 'word', 'dword', 'qword')):
            regs.pop(dst, None)
    # find name store: store at VA X of ('str', name-cvar-like)
    obj = None
    name = None
    name_va = None
    for va, lst in stores.items():
        for kind, val, *rest in lst:
            if kind == 'str' and val and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,63}', val):
                obj = va - 0x10
                name = val
                name_va = rest[0] if rest else None
    if obj is None:
        return None
    # validate handle = self at obj+0x38
    h = stores.get(obj + 0x38)
    if not h or h[0][0] != 'va' or h[0][1] != obj:
        return None
    flags = next((v for k, v in stores.get(obj + 0x28, []) if k == 'imm'), None)
    typ = next((v for k, v in stores.get(obj + 0x50, []) if k == 'imm'), None)
    default = None
    for kind, val, *_ in stores.get(obj + 0x40, []):
        if kind == 'str':
            default = val
    mn = next((v for k, v in stores.get(obj + 0x64, []) if k == 'imm'), None)
    mx = next((v for k, v in stores.get(obj + 0x68, []) if k == 'imm'), None)
    return dict(name=name, name_va=name_va, obj=obj, stub=f[0], flags=flags, default=default, typ=typ, min=mn, max=mx)


def main():
    exe, out = sys.argv[1], sys.argv[2]
    max_size = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x600
    pe = PE(exe)
    t = Text(pe)
    name_starts = pe.name_starts
    cand = {}
    for site, tgt in t.lea_sites():
        if tgt not in name_starts:
            continue
        f = t.func_of(site)
        if f is None or (f[1] - f[0]) > max_size:
            continue
        cand.setdefault(f, set()).add(tgt)
    rows, seen = [], {}
    for f, names in cand.items():
        info = analyze(pe, t, f)
        if not info:
            continue
        if info['name_va'] not in names:
            continue          # name store must be one of the lea'd names in this func
        key = info['name']
        if key in seen:
            seen[key][1] += 1
            continue
        row = (info, len(names))
        seen[key] = [row, 0]
        rows.append(row)
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write("# cvar\tstub_rva\tobj_rva\tflags\tflags_decoded\tdefault\ttype+0x50\tmin\tmax\n")
        for info, n in sorted(rows, key=lambda r: r[0]['name']):
            fh.write(f"{info['name']}\t0x{info['stub']:x}\t"
                     f"0x{info['obj']:x}\t"
                     f"{'0x%x' % info['flags'] if info['flags'] is not None else ''}\t"
                     f"{flag_str(info['flags']) if info['flags'] is not None else ''}\t"
                     f"{info['default'] if info['default'] is not None else ''}\t"
                     f"{'0x%x' % info['typ'] if info['typ'] is not None else ''}\t"
                     f"{f32(info['min']) if info['min'] is not None else ''}\t"
                     f"{f32(info['max']) if info['max'] is not None else ''}\n")
    print(f"stubs with lea'd names: {len(cand)}  validated descriptors: {len(rows)} -> {out}")


if __name__ == '__main__':
    main()
