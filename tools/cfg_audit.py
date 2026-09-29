#!/usr/bin/env python
"""Audit a community autoexec.cfg against the current build.

Evidence per entry:
  registered  - validated descriptor found in the exe (cvar_fields.tsv)
  default     - build default value string
  flags       - descriptor flags (FCVAR_*)
  readers     - handle xrefs outside the registration stub (0 => nothing reads it)
  stub        - registration stub RVA
  instring    - name string exists in the binary at all
  in_user_cfg - name is written by the game itself into the user's cfg files

Usage:
  python cfg_audit.py <autoexec.cfg> <fields.tsv> <readers.tsv> <stubs.tsv> <exe> <outdir>
"""
import sys, os, re, struct, bisect
from cvar_registry import PE, flag_str
from cvar_stubs import Text

CFG_FILES = [
    r'C:\Users\kazuy\Saved Games\Respawn\Apex\local\settings.cfg',
    r'C:\Users\kazuy\Saved Games\Respawn\Apex\profile\profile.cfg',
    r'C:\Users\kazuy\Saved Games\Respawn\Apex\local\videoconfig.txt',
]
LINE_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_.]*)\s+"?([^"\s]*)"?')
BIND_RE = re.compile(r'^\s*(bind_?\w*|unbind)\s')


def parse_autoexec(path):
    """-> list of dicts: name, value, comment, line, kind"""
    out = []
    for i, raw in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
        line = raw.strip()
        if not line:
            continue
        comment = ''
        body = line
        if '//' in line:
            # keep leading text, comment after //
            body, comment = line.split('//', 1)
            body = body.strip()
        if not body:
            out.append(dict(name='', value='', comment=comment.strip(), line=i, kind='comment'))
            continue
        if BIND_RE.match(body):
            out.append(dict(name='BIND', value=body, comment=comment.strip(), line=i, kind='bind'))
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_.]*)\s*(.*)$', body)
        if not m:
            out.append(dict(name=body, value='', comment=comment.strip(), line=i, kind='command'))
            continue
        name, val = m.group(1), m.group(2).strip().strip('"')
        kind = 'cvar'
        if name in ('snd_setmixer',):
            kind = 'command'
        out.append(dict(name=name, value=val, comment=comment.strip(), line=i, kind=kind))
    return out


def load_tsv(path):
    rows = {}
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        rows[c[0]] = c
    return rows


def main():
    cfg, fields_p, readers_p, stubs_p, exe, outdir = sys.argv[1:7]
    fields = load_tsv(fields_p)
    readers = load_tsv(readers_p)
    stubs = load_tsv(stubs_p)
    pe = PE(exe)
    t = Text(pe)
    # raw string presence
    raw_names = set()
    for m in re.finditer(rb'[A-Za-z_][A-Za-z0-9_.]{1,63}\x00', pe.d):
        raw_names.add(m.group(0)[:-1].decode())
    user = {}
    for f in CFG_FILES:
        if not os.path.exists(f):
            continue
        for line in open(f, encoding='utf-8', errors='replace'):
            m = LINE_RE.match(line)
            if m:
                user.setdefault(m.group(1), os.path.basename(f))

    entries = parse_autoexec(cfg)
    os.makedirs(outdir, exist_ok=True)
    audit = os.path.join(outdir, 'autoexec-audit.tsv')
    with open(audit, 'w', encoding='utf-8') as fh:
        fh.write("# line\tname\tvalue\tverdict\texists\tregistered\tdefault\tflags\treaders\tstub\tin_user_cfg\tcomment\n")
        summary = {}
        for e in entries:
            if e['kind'] in ('comment', 'bind') or not e['name']:
                continue
            n = e['name']
            f = fields.get(n)
            r = readers.get(n)
            s = stubs.get(n)
            registered = bool(f)
            exists = (n.encode() + b'\0') in pe.d
            rd = int(r[2]) - 1 if r and r[2].isdigit() else (int(r[2]) - 1 if r else 0)
            if registered:
                fl = f[3]
                verdict = 'registered'
                if fl == '0x4000' or 'CHEAT' in f[4]:
                    verdict = 'cheat-flagged'
                elif rd <= 0:
                    verdict = 'registered-unread'
            elif exists:
                verdict = 'string-only'
            else:
                verdict = 'absent'
            summary[verdict] = summary.get(verdict, 0) + 1
            fh.write(f"{e['line']}\t{n}\t{e['value']}\t{verdict}\t{int(exists)}\t{int(registered)}\t"
                     f"{f[5] if f else ''}\t{f[3] if f else ''}\t{rd}\t{f[1] if f else ''}\t"
                     f"{user.get(n, '')}\t{e['comment'][:60]}\n")
    print('verdicts:', summary)
    print('audit ->', audit)

    # missing candidates: registered + read + not in the cfg + not cheat-only
    have = {e['name'] for e in entries if e['kind'] in ('cvar', 'command')}
    miss = os.path.join(outdir, 'cvar-not-in-cfg.tsv')
    with open(miss, 'w', encoding='utf-8') as fh:
        fh.write("# cvar\tdefault\tflags\tflags_decoded\treaders\tin_user_cfg\n")
        for n in sorted(fields):
            if n in have:
                continue
            fr = fields[n]
            r = readers.get(n)
            rd = int(r[2]) - 1 if r and r[2].isdigit() else 0
            fh.write(f"{n}\t{fr[5]}\t{fr[3]}\t{fr[4]}\t{rd}\t{user.get(n, '')}\n")
    print('not-in-cfg ->', miss)


if __name__ == '__main__':
    main()
