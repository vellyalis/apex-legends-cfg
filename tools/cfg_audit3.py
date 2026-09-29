#!/usr/bin/env python
"""Second stage: refine verdicts (videoconfig keys), find equivalents for dead
names, and curate the "not in the cfg" candidate list.

Usage: python cfg_audit3.py <autoexec> <fields.tsv> <readers2.tsv> <stubs.tsv> <modules.tsv> <exe> <outdir>
"""
import sys, os, re, collections

FLAGS = {0x2: 'DEVELOPMENTONLY', 0x10: 'HIDDEN', 0x20: 'PROTECTED', 0x80: 'ARCHIVE',
         0x100: 'NOTIFY', 0x200: 'USERINFO', 0x1000: 'NEVER_AS_STRING', 0x2000: 'REPLICATED',
         0x4000: 'CHEAT', 0x80000: 'ARCHIVE_XBOX', 0x1000000: 'SCRIPTS_ONLY',
         0x40000000: 'NO_MIN_MAX_CHECK'}
BIND_RE = re.compile(r'^\s*(bind_?\w*|unbind)\s')
NAME_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*"?([^"\s]*)"?')
CATS = [
    ('audio', re.compile(r'^(snd_|sound_|miles_|audio_|music)')),
    ('input', re.compile(r'^(mouse_|m_|gamepad_|joystick|raw_input|input_|cl_use_raw_input|cl_mouse)')),
    ('net', re.compile(r'^(net_|cl_updaterate|cl_cmdrate|cl_resend|cl_timeout|cl_cmdbackup|rate|pin_|telemetry|match_)')),
    ('hud', re.compile(r'^(hud_setting_|cl_hud)')),
    ('player', re.compile(r'^(player_setting_|weapon_setting_|clubs_|colorblind|damage_indicator)')),
    ('video', re.compile(r'^(mat_|r_|setting\.|stream_|shadow_|ssao|dvs_|tsaa|csm_|viewmodel|fov_|cl_fov|particle|cl_detail|dof)')),
    ('perf', re.compile(r'^(fps_|cl_forcepreload|host_|threaded|vphysics|nx_)')),
    ('ragdoll/phys', re.compile(r'^(cl_ragdoll|cl_phys|rope_|cl_gib|violence_)')),
]


def flagnames(v):
    f = int(v, 16) if v.startswith('0x') else int(v)
    return '|'.join(n for b, n in sorted(FLAGS.items()) if f & b)


def load(path):
    out = {}
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        out[c[0]] = c
    return out


def main():
    cfg, fp, rp, sp, mp, exe, outdir = sys.argv[1:8]
    fields, readers, stubs, modules = load(fp), load(rp), load(sp), load(mp)
    blob = open(exe, 'rb').read()
    os.makedirs(outdir, exist_ok=True)

    entries = []
    for i, raw in enumerate(open(cfg, encoding='utf-8', errors='replace'), 1):
        line = raw.strip()
        if not line:
            continue
        body, _, comment = line.partition('//')
        body, comment = body.strip(), comment.strip()
        if not body:
            continue
        if BIND_RE.match(body):
            entries.append(dict(line=i, kind='bind', raw=body, comment=comment))
            continue
        m = NAME_RE.match(body)
        if not m:
            entries.append(dict(line=i, kind='other', raw=body, comment=comment))
            continue
        entries.append(dict(line=i, kind='cvar', name=m.group(1), value=m.group(2), raw=body, comment=comment))

    rows = []
    for e in entries:
        if e['kind'] != 'cvar':
            continue
        n = e['name']
        f = fields.get(n)
        r = readers.get(n)
        read = bool(r and (int(r[6]) > 0 or int(r[7]) > 0))
        vcf = (b'setting.' + n.encode() + b'\0') in blob
        if f:
            fv = int(f[3], 16) if f[3] else 0
            if fv & 0x4000:
                v = 'cheat'
            elif read:
                v = 'registered'
            elif fv & 0x1000000:
                v = 'registered-scriptread'
            else:
                v = 'registered-noread'
        elif n in stubs:
            v = 'registered-unverified'
        elif vcf:
            v = 'videoconfig-key'
        elif modules.get(n) and modules[n][1]:
            v = 'string-only'
        else:
            v = 'absent'
        rows.append((e, f, r, v, read, vcf))

    # name equivalence for dead entries
    live = set(fields) | set(stubs)
    equiv = {}
    words = re.compile(r'[A-Za-z0-9]+')
    for e, f, r, v, read, vcf in rows:
        if v not in ('absent', 'string-only'):
            continue
        n = e['name']
        toks = set(t for t in words.findall(n) if len(t) > 2)
        cands = []
        for ln in live:
            lt = set(words.findall(ln))
            if ln.startswith(n + '_') or n.startswith(ln + '_'):
                score = 100
            elif toks and toks == lt:
                score = 90
            elif toks and len(toks & lt) == len(toks):
                score = 80 + len(lt - toks)
            elif len(toks & lt) >= 2:
                score = 50 + len(toks & lt)
            else:
                continue
            cands.append((score, ln))
        cands.sort(key=lambda x: (-x[0], len(x[1])))
        equiv[n] = [c for _, c in cands[:6]]

    with open(os.path.join(outdir, 'autoexec-audit.tsv'), 'w', encoding='utf-8') as fh:
        fh.write("# line\tname\tvalue\tverdict\tdefault\tflags\tflags_decoded\tread\thandle_xrefs\tvalue_xrefs\tvideoconfig_key\tequiv\tcomment\n")
        for e, f, r, v, read, vcf in rows:
            fh.write('\t'.join([str(e['line']), e['name'], e['value'], v,
                                f[5] if f else '', f[3] if f else '',
                                flagnames(f[3]) if f and f[3] else '', str(int(read)),
                                r[6] if r else '0', r[7] if r else '0',
                                str(int(vcf)), ','.join(equiv.get(e['name'], [])),
                                e['comment'][:60]]) + '\n')

    # curated candidates
    have = {e['name'] for e in entries if e['kind'] == 'cvar'}
    cand = collections.defaultdict(list)
    for n, f in fields.items():
        if n in have:
            continue
        r = readers.get(n)
        read = bool(r and (int(r[6]) > 0 or int(r[7]) > 0))
        flags = int(f[3], 16) if f[3] else 0
        if flags & 0x4000:
            continue
        if re.match(r'^(test|debug|rpt|nav_|ai_|bot_|sv_|net_debug|host_|ConVar|VCvar|util_|ent_|rdr_)', n):
            continue
        if not (read or (flags & 0x1000000) or (flags & 0x200)):
            continue
        cat = 'other'
        for cname, cre in CATS:
            if cre.match(n):
                cat = cname
                break
        cand[cat].append((n, f[5], f[4] or flagnames(f[3]), read, r[6] if r else '0', r[7] if r else '0'))
    with open(os.path.join(outdir, 'candidates-by-category.tsv'), 'w', encoding='utf-8') as fh:
        fh.write("# category\tcvar\tdefault\tflags\tread\thandle_xrefs\tvalue_xrefs\n")
        for c in sorted(cand):
            for row in sorted(cand[c]):
                fh.write('\t'.join([c] + [str(x) for x in row]) + '\n')
    with open(os.path.join(outdir, 'equivalents.tsv'), 'w', encoding='utf-8') as fh:
        fh.write("# dead_name\tcandidates_in_this_build\n")
        for n, cs in sorted(equiv.items()):
            fh.write(f"{n}\t{','.join(cs)}\n")

    cnt = collections.Counter(v for _, _, _, v, _, _ in rows)
    print('verdicts:', dict(cnt))
    print('categories:', {c: len(v) for c, v in sorted(cand.items())})
    print('->', outdir)


if __name__ == '__main__':
    main()
