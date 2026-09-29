#!/usr/bin/env python
"""List the 46 `setting.*` keys, who references them (.text lea), and diff against
the live videoconfig.txt. Usage: python videoconfig_report.py <exe> <ledger> <videoconfig> <out.md>
"""
import re, os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cvar_registry import PE  # noqa: E402

KEY_RE = re.compile(rb'setting\.[A-Za-z][A-Za-z0-9_]{2,40}\x00')
VAL_RE = re.compile(r'\s*"setting\.([A-Za-z0-9_]+)"\s*"([^"]*)"')


def lea_refs(pe, targets):
    """RIP-relative lea sites in .text pointing at any target VA -> {va: [(site, func)]}"""
    vaddr, vsize, rawptr, rawsize = pe.secs['.text']
    blob = pe.d[rawptr:rawptr + rawsize]
    base = pe.ib + vaddr
    out = {}
    tset = set(int(t) for t in targets)
    for m in re.finditer(rb'\x48\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]', blob):
        off = m.start()
        disp = struct.unpack_from('<i', blob, off + 3)[0]
        site = base + off
        tgt = site + 7 + disp
        if tgt in tset:
            out.setdefault(tgt, []).append(site)
    return out


def main():
    exe, ledger, vcfg, out = sys.argv[1:5]
    pe = PE(exe)

    keys = {}
    for lo, hi, rawptr, sec in pe.ranges:
        blob = pe.d[rawptr:rawptr + (hi - lo)]
        for m in KEY_RE.finditer(blob):
            keys[pe.ib + lo + m.start()] = m.group(0)[:-1].decode()

    refs = lea_refs(pe, keys.keys())

    led = {}
    for line in open(ledger, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        led[c[0]] = c

    live = {}
    for line in open(vcfg, encoding='utf-8'):
        m = VAL_RE.match(line)
        if m:
            live['setting.' + m.group(1)] = m.group(2)

    rows = []
    for va, k in sorted(keys.items(), key=lambda kv: kv[1]):
        name = k.split('.', 1)[1]
        c = led.get(name)
        rows.append(dict(key=k, va=va, refs=len(refs.get(va, [])),
                         cvar=name if c else '', default=c[1] if c else '',
                         flags=c[2] if c else '', read=c[4] if c else '',
                         cur=live.get(k, ''), notinlive=k not in live))

    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(f"# videoconfig.txt キー（exe内の `setting.*` 文字列 = {len(keys)}本）\n\n")
        fh.write("| key | exe文字列 | .text参照 | 同名cvar | cvar既定 | flags | native読取 | 現行値 |\n")
        fh.write("|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            fh.write(f"| `{r['key']}` | 0x{r['va']:x} | {r['refs']} | "
                     f"{('`'+r['cvar']+'`') if r['cvar'] else '—'} | {r['default'] or '—'} | "
                     f"{r['flags'] or '—'} | {r['read'] or '—'} | {r['cur'] or '(無し)'} |\n")
        miss = [r['key'] for r in rows if r['notinlive']]
        extra = [k for k in live if k not in keys]
        fh.write(f"\n- exe側にあって現行 videoconfig.txt に無いキー: {len(miss)}\n")
        for k in miss:
            fh.write(f"  - `{k}`\n")
        fh.write(f"- 現行ファイルにあって exe に文字列が無いキー: {len(extra)}\n")
        for k in extra:
            fh.write(f"  - `{k}`\n")
    print(open(out, encoding='utf-8').read())


if __name__ == '__main__':
    main()
