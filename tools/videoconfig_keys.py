#!/usr/bin/env python
"""Extract the videoconfig.txt key whitelist from the exe.

Videoconfig keys are the literal strings `setting.<name>` that the video settings
manager accepts. We (1) find every such string in read/write data sections,
(2) locate the qword arrays that reference them (the accept-list the parser walks),
(3) cross-reference each key with the cvar ledger.

Usage: python videoconfig_keys.py <exe> <cvar-ledger.tsv> <out.tsv>
"""
import re, os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cvar_registry import PE  # noqa: E402

KEY_RE = re.compile(rb'setting\.[A-Za-z][A-Za-z0-9_]{2,40}\x00')


def main():
    exe, ledger, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pe = PE(exe)

    # (1) every `setting.*` string VA
    keys = {}
    for lo, hi, rawptr, sec in pe.ranges:
        blob = pe.d[rawptr:rawptr + (hi - lo)]
        for m in KEY_RE.finditer(blob):
            keys[pe.ib + lo + m.start()] = m.group(0)[:-1].decode()

    # (2) qword runs referencing those string VAs
    offs, vals = pe._all_qwords()
    arr = {}
    run_start, run_keys = None, []
    ordered = sorted(zip(offs.tolist(), vals.tolist()))
    for off, v in ordered:
        if v in keys:
            if run_start is None:
                run_start, run_keys = off, []
            run_keys.append(keys[v])
        else:
            if run_start is not None and len(run_keys) >= 5:
                arr[run_start] = list(run_keys)
            run_start, run_keys = None, []
    if run_start is not None and len(run_keys) >= 5:
        arr[run_start] = list(run_keys)

    # (3) ledger cross-reference
    led = {}
    for line in open(ledger, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        led[c[0]] = c

    used = sorted({k for v in arr.values() for k in v})
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write("# key\tstring_va\tarrays\tcvar\tdefault\tflags\tread_by_native\tcheat\n")
        for k in sorted(used):
            name = k.split('.', 1)[1]
            cvar = led.get(name)
            arrs = ','.join(f'0x{a:x}' for a, v in arr.items() if k in v)
            sv = ','.join(f'0x{va:x}' for va, n in keys.items() if n == k)
            fh.write('\t'.join([k, sv, arrs, name if cvar else '',
                                cvar[1] if cvar else '',
                                cvar[2] if cvar else '',
                                cvar[4] if cvar else '',
                                cvar[5] if cvar else '']) + '\n')

    print(f'setting.* strings: {len(keys)}')
    print(f'arrays (>=5 refs): {len(arr)}')
    for a in sorted(arr):
        print(f'  array @0x{a:x}: {len(arr[a])} keys')
        print('    ' + ', '.join(arr[a]))
    print(f'whitelist keys: {len(used)} (unique across arrays) -> {out}')


if __name__ == '__main__':
    main()
