#!/usr/bin/env python
"""Extract UI/cvar token families from binaries (exe / rpak).

Usage: python scan_tokens.py <out_dir> <file1> [file2 ...]
Writes <out_dir>/<basename>.tokens.txt with one section per family.
"""
import re, sys, os

PATS = {
    'gameui':   rb'#GameUI_[A-Za-z0-9_]+',
    'setting_ui': rb'#setting_[a-z0-9_]+',
    'panel':    rb'\b(?:Swch|Sld|TextEntrySld|Btn)[A-Za-z0-9_]+',
    'sens':     rb'[A-Za-z0-9_]*[Ss]ensitiv[A-Za-z0-9_]*',
    'mouse':    rb'[A-Za-z0-9_]*[Mm]ouse[A-Za-z0-9_]*',
    'look':     rb'[A-Za-z0-9_]*[Ll]ook[A-Za-z0-9_]*',
    'aim':      rb'[A-Za-z0-9_]*[Aa]im[A-Za-z0-9_]*',
    'stream':   rb'[A-Za-z0-9_]*strea[A-Za-z0-9_]*',
    'aniso':    rb'[A-Za-z0-9_]*[Aa]niso[A-Za-z0-9_]*',
    'turn':     rb'[A-Za-z0-9_]*[Tt]urn[A-Za-z0-9_]*',
    'deadzone': rb'[A-Za-z0-9_]*[Dd]eadzone[A-Za-z0-9_]*',
    'curve':    rb'[A-Za-z0-9_]*[Cc]urve[A-Za-z0-9_]*',
    'latency':  rb'[A-Za-z0-9_]*[Ll]atency[A-Za-z0-9_]*',
    'rawinput': rb'[A-Za-z0-9_]*[Rr]aw[A-Za-z0-9_]*',
}

def main():
    outdir = sys.argv[1]
    files = sys.argv[2:]
    os.makedirs(outdir, exist_ok=True)
    for path in files:
        data = open(path, 'rb').read()
        base = os.path.basename(path).replace('(', '_').replace(')', '_')
        outp = os.path.join(outdir, base + '.tokens.txt')
        with open(outp, 'w', encoding='utf-8') as f:
            f.write(f"# {path} size={len(data)}\n\n")
            for name, pat in PATS.items():
                hits = sorted(set(m.decode('ascii') for m in re.findall(pat, data)))
                f.write(f"### {name}: {len(hits)}\n")
                for h in hits[:500]:
                    f.write(h + "\n")
                f.write("\n")
        print(f"{base}: done ({len(data)} bytes)")

if __name__ == '__main__':
    main()
