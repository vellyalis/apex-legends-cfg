#!/usr/bin/env python
"""cvar_fields v2: recover descriptors from FAMILY/loop registrations too.

Difference from cvar_fields.py: the store tracker follows base registers
(`lea rbx,[rip+obj]` / `lea rbx,[rip+table]` / `add rbx,0x48`) and stores via
`[reg+disp]`, which is how indexed families (mouse_zoomed_sensitivity_scalar_N,
gamepad_*, dialogue_cat_*, aimassist_*) are registered.

Usage: python cvar_fields2.py <exe> <out.tsv> [max_func_size]
"""
import sys, re, struct
from cvar_registry import PE, flag_str
from cvar_stubs import Text

STORE_RIP = re.compile(r'^(byte|word|dword|qword) ptr \[rip \+ (0x[0-9a-f]+)\], (.*)$')
STORE_REG = re.compile(r'^(byte|word|dword|qword) ptr \[([a-z0-9]+)(?: \+ (0x[0-9a-f]+))?\], (.*)$')
LEA_RIP = re.compile(r'^([a-z0-9]+), \[rip \+ (0x[0-9a-f]+)\]$')
LEA_REG = re.compile(r'^([a-z0-9]+), \[([a-z0-9]+)(?: \+ (0x[0-9a-f]+))?\]$')
MOV_IMM = re.compile(r'^([a-z0-9]+), (-?(?:0x[0-9a-f]+|\d+))$')
ADD_IMM = re.compile(r'^([a-z0-9]+), (-?(?:0x[0-9a-f]+|\d+))$')
CVARNAME = re.compile(r'[A-Za-z][A-Za-z0-9_.]{2,63}$')


def f32(v):
    return struct.unpack('<f', struct.pack('<I', v & 0xffffffff))[0]


def analyze(pe, t, f, min_stores=1):
    regs = {}
    stores = {}
    markers = set()
    MARKERS = (0x1417dcac0, 0x1419c7920)

    def put(va, desc):
        stores.setdefault(va, []).append(desc)

    PLAIN_IMM = re.compile(r'^-?(?:0x[0-9a-f]+|\d+)$')

    def valof(src):
        if src in regs:
            return regs[src]
        if PLAIN_IMM.match(src):
            return ('imm', int(src, 0))
        return None

    for insn in t.disasm(f):
        m, ops = insn.mnemonic, insn.op_str
        rr = t.ripref(insn)
        if rr in MARKERS:
            markers.add(rr)
        if m == 'lea':
            ml = LEA_RIP.match(ops)
            if ml:
                dst, disp = ml.group(1), int(ml.group(2), 16)
                r = t.ripref(insn)
                if r is None:
                    continue
                s2 = pe.cstr(r)
                regs[dst] = ('str', s2, r) if s2 is not None else ('base', r, 0)
                continue
            mr = LEA_REG.match(ops)
            if mr:
                dst, base, disp = mr.group(1), mr.group(2), (int(mr.group(3), 16) if mr.group(3) else 0)
                if base in regs and regs[base][0] == 'base':
                    _, bva, boff = regs[base]
                    regs[dst] = ('base', bva + (disp & 0xffffffff) if disp > 0x7fffffff else bva + disp, boff) \
                        if False else ('base', bva + disp, boff)
                else:
                    regs.pop(dst, None)
                continue
            regs.pop(ops.split(',')[0].strip(), None)
            continue
        if m in ('mov', 'movss', 'movsd', 'movzx'):
            ms = STORE_RIP.match(ops)
            if ms:
                r = t.ripref(insn)
                src = ms.group(3).strip()
                v = valof(src)
                if r is not None and v is not None:
                    put(r, v)
                continue
            mr = STORE_REG.match(ops)
            if mr:
                base, disp, src = mr.group(2), (int(mr.group(3), 16) if mr.group(3) else 0), mr.group(4).strip()
                if base in regs and regs[base][0] == 'base':
                    _, bva, boff = regs[base]
                    v = valof(src)
                    if v is not None:
                        put(bva + disp + boff, v)
                continue
            ml = re.match(r'^([a-z0-9]+), (byte|word|dword|qword) ptr \[.*\]$', ops)
            if ml and ml.group(1) in regs:
                regs.pop(ml.group(1), None)
                continue
            mi = MOV_IMM.match(ops)
            if mi:
                dst = mi.group(1)
                if dst in ('rsp', 'rbp') or dst.startswith(('e', 'r')) and dst not in regs:
                    pass
                regs[dst] = ('imm', int(mi.group(2), 0))
                continue
            dst = ops.split(',')[0].strip() if ops else ''
            if dst and not dst.startswith(('[', 'byte', 'word', 'dword', 'qword')):
                regs.pop(dst, None)
            continue
        if m in ('add', 'sub') and ops:
            ma = ADD_IMM.match(ops)
            if ma and ma.group(1) in regs and regs[ma.group(1)][0] == 'base':
                dst = ma.group(1)
                _, bva, boff = regs[dst]
                d = int(ma.group(2), 0)
                regs[dst] = ('base', bva + (d if m == 'add' else -d), boff)
                continue
            dst = ops.split(',')[0].strip()
            regs.pop(dst, None)
            continue
        dst = ops.split(',')[0].strip() if ops else ''
        if dst and not dst.startswith(('[', 'byte', 'word', 'dword', 'qword', 'xmm')):
            regs.pop(dst, None)

    # every cvar-looking name store => one descriptor candidate
    cands = []
    for va, lst in stores.items():
        for v in lst:
            if v[0] != 'str' or not v[1] or not CVARNAME.match(v[1]):
                continue
            obj = va - 0x10
            h = stores.get(obj + 0x38)
            strict = bool(h and any(x[0] == 'base' and x[1] == obj and x[2] == 0 for x in h))

            def imm_at(off):
                for x in stores.get(obj + off, []):
                    if x[0] == 'imm':
                        return x[1]
                return None

            default = None
            for x in stores.get(obj + 0x40, []):
                if x[0] == 'str':
                    default = x[1]
            flags, typ = imm_at(0x28), imm_at(0x50)
            if not markers:
                continue
            if not strict and flags is None and default is None and typ is None:
                continue
            cands.append(dict(name=v[1], name_va=v[2], obj=obj, stub=f[0], strict=strict,
                              flags=flags, default=default, typ=typ,
                              min=imm_at(0x64), max=imm_at(0x68)))
    return cands


def main():
    exe, out = sys.argv[1], sys.argv[2]
    max_size = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x200000
    pe = PE(exe)
    t = Text(pe)
    cand = {}
    for site, tgt in t.lea_sites():
        if tgt not in pe.name_starts:
            continue
        f = t.func_of(site)
        if f is None or (f[1] - f[0]) > max_size:
            continue
        cand.setdefault(f, set()).add(tgt)
    print(f'candidate functions: {len(cand)}', flush=True)
    rows, seen = [], {}
    for i, (f, names) in enumerate(cand.items()):
        if i % 2000 == 0:
            print(f'  ...{i}/{len(cand)} validated={len(rows)}', flush=True)
        infos = analyze(pe, t, f) or []
        for info in infos:
            if info['name_va'] not in names or info['name'] in seen:
                continue
            seen[info['name']] = 1
            rows.append(info)
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write("# cvar\tstub_rva\tobj_rva\tflags\tflags_decoded\tdefault\ttype+0x50\tmin\tmax\n")
        for i in sorted(rows, key=lambda r: r['name']):
            fh.write(f"{i['name']}\t0x{i['stub']:x}\t0x{i['obj']:x}\t"
                     f"{'0x%x' % i['flags'] if i['flags'] is not None else ''}\t"
                     f"{flag_str(i['flags']) if i['flags'] is not None else ''}\t"
                     f"{i['default'] if i['default'] is not None else ''}\t"
                     f"{'0x%x' % i['typ'] if i['typ'] is not None else ''}\t"
                     f"{f32(i['min']) if i['min'] is not None else ''}\t"
                     f"{f32(i['max']) if i['max'] is not None else ''}\n")
    print(f'validated descriptors: {len(rows)} -> {out}')


if __name__ == '__main__':
    main()
