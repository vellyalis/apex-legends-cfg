#!/usr/bin/env python
"""Generate the documented videoconfig.txt + VIDEOCONFIG-GUIDE.md.

- 現行値をライブファイルから読み、exe 内の `setting.*` 文字列（=正規キー46本）と突合
- 各キーに「既定/現行/推奨/意味/副作用」コメントを付けて出力
- 全キーがexe上に実在することを機械検証してから書き出す

Usage: python mk_documented_videoconfig.py <exe> <ledger> <live-videoconfig> <out-dir>
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cvar_registry import PE  # noqa: E402

KEY_RE = re.compile(rb'setting\.[A-Za-z][A-Za-z0-9_]{2,40}\x00')
VAL_RE = re.compile(r'\s*"setting\.([A-Za-z0-9_]+)"\s*"([^"]*)"')

# key -> (推奨値 or None=現行維持, グループ, コメント)
T = {
 'last_display_width':   (None, 'display', '内部値: 直近の画面幅。ゲームが書く。触らない'),
 'last_display_height':  (None, 'display', '内部値: 直近の画面高。触らない'),
 'defaultres':           (None, 'display', '解像度の幅（メニュー「解像度」）。触らない'),
 'defaultresheight':     (None, 'display', '解像度の高さ。触らない'),
 'fullscreen':           (None, 'display', '1=全画面 / 0=ウィンドウ。メニューの表示モード。触らない'),
 'nowindowborder':       (None, 'display', 'ボーダーレス指定。メニュー側。触らない'),
 'configversion':        (None, 'display', 'videoconfigの形式バージョン。絶対に触らない'),
 'sound_volume':         (None, 'audio',   '音量。既定1.0。足音は視認性と同じ「情報」なので下げない'),

 'stream_memory':        ('6000000', 'visibility', '★推奨変更（現行300000/既定298000）: テクスチャストリーミング予算(KB)。16GB VRAMなら6GB級でよい。上げる=遠く/近くのテクスチャが鮮明（負荷: VRAM消費増、読み込みスパイクに注意）'),
 'r_lod_switch_scale':   ('1.000000', 'visibility', '★推奨変更（現行0.600000/既定1）: 遠距離モデルのLOD切替距離。1.0=既定で遠くまで高精度モデル。0.6=早く低ポリに落ちる（敵の見分けが悪化）。1超でさらに遠くまで高精度（負荷増）'),
 'mat_forceaniso':       ('8', 'visibility', '★推奨変更（現行2/既定2）: 異方性フィルタ。斜め視点の床/壁テクスチャのボケが減る（2/4/8/16）。16で最大、負荷は軽微'),
 'ssao_enabled':         ('0', 'visibility', '★推奨追加（既定1・現行ファイルに無し=既定1）: 環境遮蔽。切ると暗部の「黒潰れ/エッジの暗がり」が減り、暗所の敵が見やすい。メニュー「アンビエントオクルージョン」相当'),
 'ssao_quality':         (None, 'visibility', 'AOの品質。既定3 / 現行0（最も軽い側）。ssao_enabled=0なら無関係'),
 'gamma':                (None, 'visibility', '画面の明るさ（メニュー「明るさ」スライダー相当。現行0.700000）。暗所を明るくしたい場合はメニューで上げるのが安全（ここを直接いじると読み取り専用化と衝突しやすい）'),

 'mat_picmip':           (None, 'visual', 'テクスチャ解像度。既定0(=最高)。0のまま推奨（上げると全テクスチャが荒くなる）'),
 'mat_mip_linear':       (None, 'visual', 'ミップマップ補間。既定1。触らない'),
 'mat_antialias_mode':   (None, 'visual', '0=アンチエイリアス無し / 1=TSAA。現行0。オフ=輪郭がシャープ（敵の輪郭が締まる）が、ギザつき(ジャギ)は増える。負荷は軽くなる'),
 'mat_vsync_mode':       (None, 'visual', '0=VSyncオフ。360Hz+VRRならオフ推奨（現行0のまま）'),
 'mat_backbuffer_count': (None, 'visual', '背面バッファ枚数。現行1（最小遅延側）。メニュー外。1のままでよい'),
 'fadeDistScale':        (None, 'visual', 'オブジェクトのフェード距離スケール。既定1.0。「1未満=遠くの物が早く消える(軽い/見えにくい)」。現行1.0のまま'),
 'map_detail_level':     (None, 'visual', 'マップ詳細レベル（意味未特定・既定不明）。現行1のまま触らない'),
 'new_shadow_settings':  (None, 'visual', '新シャドウ経路の切替フラグ（内部）。現行1のまま'),
 'dynamic_streaming_budget': (None, 'visual', '動的ストリーミング予算（内部フラグ・既定不明）。現行1のまま'),

 'csm_enabled':          (None, 'shadow', 'キャラクター影(CSM)。既定1 / 現行0。0=キャラ影なし=敵の輪郭が黒フチで浮かず地形に溶ける…のを避けたい人は1、軽さ優先なら0。※ALGSで明示的に許可されていた値'),
 'csm_coverage':         (None, 'shadow', '影のカバレッジ。既定2 / 現行1（狭い=高解像度側）。csm_enabled=0なら無関係'),
 'csm_cascade_res':      (None, 'shadow', '影の解像度。既定1024 / 現行512（軽い側）。csm_enabled=0なら無関係'),
 'shadow_enable':        (None, 'shadow', '動的スポット影。既定1 / 現行0（オフ=負荷減・暗部のムラ減。視認性は微プラス）'),
 'shadow_depth_dimen_min': (None, 'shadow', '影マップの最小解像度。既定192 / 現行0。shadow_enable=0なら無関係'),
 'shadow_depth_upres_factor_max': (None, 'shadow', '影マップの最大アップレゾ係数。既定2 / 現行0'),
 'shadow_maxdynamic':    (None, 'shadow', '動的影の最大数。既定4 / 現行0（0=動的影なし）'),

 'volumetric_lighting':  (None, 'glare', '体積光。既定はOFF以外/現行0。0=光の筋(グレア)が消えて見やすい（cvar r_volumetric_lighting_enabled と同系統）'),
 'volumetric_fog':       (None, 'glare', '体積フォグ。現行0。0=霧状の光の滲みが消える（視認性プラス・負荷減）'),

 'particle_cpu_level':   (None, 'effects', 'エフェクト(粒子)のCPU負荷レベル。既定0 / 現行0。プリセット依存。0のまま'),
 'cl_particle_fallback_base': (None, 'effects', '粒子の自動間引き(base)。既定0 / 現行3（プリセット由来）。方向性が非公開のため触らない'),
 'cl_particle_fallback_multiplier': (None, 'effects', '粒子の自動間引き(multiplier)。既定1 / 現行2。触らない'),

 'r_decals':             (None, 'decals', '弾痕/デカールの上限。既定256 / 現行0（0=残らない）。0は負荷減だが「弾がどこに当たったか」の視覚情報も消える。1以上にすると命中確認が視覚でも取れる'),
 'r_createmodeldecals':  (None, 'decals', 'モデルへのデカール(血/弾痕)生成。既定1 / 現行0。同上のトレードオフ'),

 'cl_gib_allow':         (None, 'gore', 'ギブ(肉片)表示。既定1 / 現行0。0=撃破時の肉片が飛ばない（視界のノイズ減・負荷減）'),
 'cl_ragdoll_maxcount':  (None, 'gore', '死体(ラグドール)数。既定8 / 現行0（0=死体なし。視界がクリア・負荷減）'),
 'cl_ragdoll_self_collision': (None, 'gore', '死体の自己衝突。既定1 / 現行1。ラグドール0なら無関係'),

 'dvs_enable':           (None, 'perf', '動的解像度(アダプティブリゾリューション)。既定1 / 現行0。0=常に固定解像度（解像度が勝手に下がってボケるのを防ぐ）。視認性目的なら0推奨のまま'),
 'dvs_gpuframetime_min': (None, 'perf', '動的解像度の下限フレームタイム(µs)。既定15000 / 現行15000。dvs_enable=0なら無関係'),
 'dvs_gpuframetime_max': (None, 'perf', '上限側。既定16500 / 現行16500。同上'),
}

NOT_WRITTEN = {
 'cl_fovScale': 'FOV。profile.cfg の cl_fovScale が正なので、ここには書かない（二重管理になると読み取り専用化した時にFOVを固定してしまう）',
 'set_dress_level': 'exe内に文字列はあるが意味未特定・ゲームは書かない。触らない',
 'ssao_downsample': 'AOのダウンサンプル段数。既定/範囲が静的に未確定で現行ファイルにも無いため収録しない（ssao_enabled=0なら無関係）',
}


def main():
    exe, ledger, live, outdir = sys.argv[1:5]
    pe = PE(exe)

    found = set()
    for lo, hi, rawptr, sec in pe.ranges:
        blob = pe.d[rawptr:rawptr + (hi - lo)]
        for m in KEY_RE.finditer(blob):
            found.add(m.group(0)[:-1].decode())

    led = {}
    for line in open(ledger, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        led[c[0].lower()] = c

    cur = {}
    for line in open(live, encoding='utf-8'):
        m = VAL_RE.match(line)
        if m:
            cur['setting.' + m.group(1)] = m.group(2)

    # 出力キー = テーブル + 現行ファイルにあるがテーブル外のもの（未記載はエラーにする）
    unknown = [k for k in cur if k.split('.', 1)[1] not in T]
    assert not unknown, f'テーブル未定義のキー: {unknown}'
    keys = ['setting.' + n for n in T]

    missing = [k for k in keys if k not in found]
    assert not missing, f'exeに存在しないキー: {missing}'

    order = ['display', 'visibility', 'visual', 'glare', 'shadow', 'effects', 'decals', 'gore', 'perf', 'audio']
    title = {'display': '表示設定（ゲームの管理値・触らない）',
             'visibility': '視認性（推奨変更 ★）',
             'visual': '画質・描画',
             'glare': 'グレア・フォグ（視認性）',
             'shadow': '影',
             'effects': 'エフェクト',
             'decals': 'デカール（弾痕/血）',
             'gore': '死体・ギブ',
             'perf': 'パフォーマンス',
             'audio': '音'}

    lines = ['"VideoConfig"', '{']
    for g in order:
        gk = [k for k in keys if T[k.split('.', 1)[1]][1] == g]
        if not gk:
            continue
        lines.append('')
        lines.append(f'\t// ===== {title[g]} =====')
        for k in gk:
            n = k.split('.', 1)[1]
            rec, _, cmt = T[n]
            val = rec if rec else cur.get(k, '')
            if not val:
                continue
            seen = cur.get(k)
            tag = f'現行 {seen}' if seen else '現行ファイルに無し'
            if led.get(n):
                tag = f'既定 {led[n][1]} / {tag}'
            lines.append(f'\t// {cmt}｜{tag}')
            lines.append(f'\t"{k}"\t\t"{val}"')
    lines.append('}')
    lines.append('')
    body = '\n'.join(lines)
    open(os.path.join(outdir, 'videoconfig.txt'), 'w', encoding='utf-8', newline='\r\n').write(body)

    # ガイド
    doc = ['# videoconfig.txt（実測ベース）— 各項目の意味と推奨値', '',
           f'- 正規キー: exe 内の `setting.*` 文字列 **{len(found)}本**（このファイルに載せたのは {len(keys)}本）',
           '- 既定値は cvar 台帳（同名cvar・大文字小文字を無視して突合）から取得。`—` は cvar が無い（設定マネージャ側のキー）',
           '- ★ = 推奨変更。それ以外は現行値のまま（無闇に変えない）', '',
           '| key | 推奨 | 既定(cvar) | 現行 | グループ |', '|---|---|---|---|---|']
    for k in keys:
        n = k.split('.', 1)[1]
        rec, g, _ = T[n]
        doc.append(f"| `{k}` | {rec or '(現行維持)'} | {led[n][1] if led.get(n) else '—'} | {cur.get(k, '(無し)')} | {g} |")
    doc += ['', '## 書かなかったキー', '']
    for k, why in NOT_WRITTEN.items():
        doc.append(f'- `setting.{k}`: {why}')
    doc += ['', '## 使い方（読み取り専用が前提）', '',
            '1. `videoconfig.txt` を `%USERPROFILE%\\Saved Games\\Respawn\\Apex\\local\\` にコピー（**ゲーム終了中に**）',
            '2. 右クリック → プロパティ → 「読み取り専用」にチェック（または `attrib +R videoconfig.txt`）',
            '3. ゲーム起動 → メニューの映像設定がこちらの値で固定される（メニューで変更しても保存されない）',
            '',
            '**理由**: `videoconfig.txt` はゲーム自身が上書きするファイル。読み取り専用にしないと、次回終了時にメニューの値で書き戻され、コメントも消える。',
            '',
            '**解除/戻し方**: `attrib -R videoconfig.txt` → ゲームを起動して映像設定を1回変更する（またはファイルを削除して起動＝既定で作り直される）。',
            '',
            '**注意**: 読み取り専用中はメニューからの解像度/明るさ等の変更も保存されない。変えたい時は一度属性を外す。',
            '']
    open(os.path.join(outdir, 'VIDEOCONFIG-GUIDE.md'), 'w', encoding='utf-8').write('\n'.join(doc) + '\n')

    print(f'exe keys={len(found)} emitted={len(keys)} '
          f'changed={sum(1 for k in keys if T[k.split(".",1)[1]][0])} -> {outdir}/videoconfig.txt')


if __name__ == '__main__':
    main()
