#!/usr/bin/env python
"""Bound the "dynamic" cvar class: find every name passed to a by-name cvar
lookup helper, and every name a small function references, then diff vs ledger.

A: for each `lea rcx/r8/rdx, [rip+name]` followed within N instructions by a
   `call X`, record (X, name). Call targets that appear with many different
   names are cvar-lookup/registration APIs -> their names are cvars the native
   code knows by name at runtime.

Usage: python lookup_names.py <exe> <ledger.tsv> <out.txt>
"""
import sys, re, collections
from cvar_registry import PE
from cvar_stubs import Text

NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_.]{1,63}$')


def main():
    exe, ledger_p, out_p = sys.argv[1:4]
    pe = PE(exe)
    t = Text(pe)
    ledger = set()
    for l in open(ledger_p, encoding='utf-8'):
        if not l.startswith('#') and l.strip():
            ledger.add(l.split('\t')[0])

    pairs = collections.defaultdict(set)   # call target -> names
    raw = open(out_p + '.pairs.tsv', 'w', encoding='utf-8')
    for f in t.funcs:
        ins = list(t.disasm(f))
        for i, insn in enumerate(ins):
            if insn.mnemonic != 'lea':
                continue
            r = t.ripref(insn)
            if r is None:
                continue
            s = pe.cstr(r)
            if not s or not NAME.match(s):
                continue
            if not insn.op_str.startswith(('rcx', 'rdx', 'r8')):
                continue
            for j in range(i + 1, min(i + 6, len(ins))):
                m = re.match(r'^call (0x[0-9a-f]+)$', f'{ins[j].mnemonic} {ins[j].op_str}')
                if m:
                    tgt = int(m.group(1), 16)
                    pairs[tgt].add(s)
                    raw.write('0x%x	%s\n' % (tgt, s))
                    break
    # APIs = targets seen with >=8 distinct names
    api = {k: v for k, v in pairs.items() if len(v) >= 8}
    allnames = set()
    for v in api.values():
        allnames |= v
    missing = sorted(n for n in allnames if n not in ledger)
    lines = [f'call targets receiving name-string args: {len(pairs)}',
             f'  of which look like name APIs (>=8 distinct names): {len(api)}']
    for k, v in sorted(api.items(), key=lambda kv: -len(kv[1]))[:15]:
        lines.append(f'    0x{k:x}: {len(v)} names, e.g. {", ".join(sorted(v)[:6])}')
    lines.append(f'names passed to those APIs: {len(allnames)}')
    lines.append(f'  not in ledger: {len(missing)}')
    for n in missing:
        lines.append(f'    {n}')
    txt = '\n'.join(lines)
    open(out_p, 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    main()
