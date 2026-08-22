#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Gemini 對話匯出的 .docx 轉成 HonKit 雙欄對照頁面。

適用格式：每則對話含 `you asked:` / `message time:` / `gemini response:` 三個標記。

用法：
    python convert4.py 新對話.docx 對照閱讀/新資料夾

如果目標資料夾已經有 .md，預設會直接中止，不會覆蓋任何東西。
想接在既有編號後面繼續編（例如舊的到 38，新的從 39 開始）：

    python convert4.py 新對話.docx 對照閱讀/陸漂文 --append

同一個對話「重新匯出」（內容變多了）時，用這個只收新增的部分：

    python convert4.py 陸漂文翻譯.docx 對照閱讀/陸漂文 --append --skip-dup

只收某個時間點之後的對話：

    python convert4.py 匯出.docx 對照閱讀/陸漂文 --append --after auto

`--after auto` 會自己看資料夾裡最新一篇的對話時間，只收比它更新的。
也可以自己指定：--after 2026-08-01

其他選項：
    --after auto   只收比資料夾裡最新一篇更新的對話（也可寫成日期）
    --skip-dup     跳過資料夾裡已經有的篇章（比對英文原文）
    --start 39     指定從第幾號開始編
    --prefix b     檔名加前綴，產出 b01.md、b02.md…（不會跟數字檔名相撞）
    --force        真的要覆蓋既有檔案時才加（會先列出要蓋掉哪些）

只需要 Python 3，不需要安裝 pandoc 或任何套件。
"""

import math
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

ASK = re.compile(r'^you asked:', re.I)
RESP = re.compile(r'^gemini response:', re.I)
TIME = re.compile(r'^message time:\s*(.*)$', re.I)
MARK = re.compile(r'以下.{0,25}翻譯')
URL = re.compile(r'https?://\S+')


# ---------- 讀 .docx ----------

def read_docx(path):
    """直接解 .docx（本質是 zip）取出段落文字，不需要 pandoc。"""
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)

    out = []
    for p in root.iter(W + 'p'):
        buf = []
        for node in p.iter():
            if node.tag == W + 't':
                buf.append(node.text or '')
            elif node.tag in (W + 'br', W + 'cr'):
                buf.append('\n')
            elif node.tag == W + 'tab':
                buf.append('\t')
        text = ''.join(buf).strip()
        if text:
            out.append(text)
    return out


# ---------- 小工具 ----------

def cjk(s):
    return len(re.findall(r'[\u4e00-\u9fff]', s))


def lat(s):
    return len(re.findall(r'[A-Za-z]', s))


def is_zh(s):
    return cjk(s) > lat(s)


def is_junk(s):
    """只有標點、符號或純數字的段落（分隔線、日期戳記之類）。"""
    core = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', s)
    return core == '' or core.isdigit()


# ---------- 對齊 ----------

def align(en, zh):
    """用動態規劃把英文段落對到中文段落。

    允許 1:1、1:2、2:1、2:2 以及單邊刪除，成本依「中文字數 / 英文字數」的
    比例落差計算。非 1:1 的罰分刻意設得很高，所以段落數對得起來時幾乎都會
    維持 1:1，只有在 Gemini 自己把一段拆兩段、或兩段併一段時才會合併。
    """
    E = [max(1, len(a)) for a in en]
    Z = [max(1, len(b)) for b in zh]
    if not E or not Z:
        return [(en, zh)]
    r = sum(Z) / sum(E)

    MOVES = [(1, 1, 0.0), (1, 2, 7.0), (2, 1, 7.0),
             (2, 2, 15.0), (1, 0, 12.0), (0, 1, 12.0)]
    n, m = len(en), len(zh)
    INF = float('inf')
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0

    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == INF:
                continue
            for a, b, pen in MOVES:
                if i + a > n or j + b > m:
                    continue
                e = sum(E[i:i + a])
                z = sum(Z[j:j + b])
                if a == 0:
                    c = pen + z / 40.0
                elif b == 0:
                    c = pen + r * e / 40.0
                else:
                    c = abs(z - r * e) / math.sqrt(r * e + 1.0) + pen
                if dp[i][j] + c < dp[i + a][j + b]:
                    dp[i + a][j + b] = dp[i][j] + c
                    bk[i + a][j + b] = (i, j, a, b)

    pairs, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj, a, b = bk[i][j]
        pairs.append((en[pi:pi + a], zh[pj:pj + b]))
        i, j = pi, pj
    return list(reversed(pairs))


# ---------- 解析 ----------

def parse(paras):
    source = ''
    for p in paras[:5]:
        m = URL.search(p)
        if m:
            source = m.group(0)
            break

    starts = [i for i, p in enumerate(paras) if ASK.match(p)]
    entries = []

    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(paras)
        block = paras[s + 1:end]

        ri = next((i for i, p in enumerate(block) if RESP.match(p)), None)
        if ri is None:
            continue

        when = ''
        head = []
        for p in block[:ri]:
            tm = TIME.match(p)
            if tm:
                when = tm.group(1).strip()
            else:
                head.append(p)

        # 英文原文：濾掉給 Gemini 的中文指示、⚠️ 預警標籤、純符號分隔線
        en = [p for p in head
              if not is_zh(p)
              and not p.lstrip().startswith('\u26a0')
              and not is_junk(p)]

        tail = block[ri + 1:]
        mi = next((i for i, p in enumerate(tail) if MARK.search(p)), None)
        if mi is None:
            note, zh = '', tail
        else:
            note, zh = '\n\n'.join(tail[:mi]), tail[mi + 1:]
        zh = [p for p in zh if not is_junk(p)]

        if not en or not zh:
            continue
        entries.append({'time': when, 'en': en, 'zh': zh,
                        'note': note, 'source': source})
    return entries


# ---------- 輸出 ----------

def make_title(entry, idx):
    first = entry['zh'][0]
    first = re.sub(r'^[（(「『\[]+', '', first)
    first = re.split(r'[。！？\n]', first)[0]
    first = re.sub(r'[，、：；\s]+$', '', first).strip()
    if len(first) > 22:
        first = first[:22] + '\u2026'
    return f'{idx:02d} {first}' if first else f'{idx:02d}'


def make_page(entry, title, pairs):
    out = [f'# {title}', '']

    meta = []
    if entry['time']:
        meta.append(f"> 對話時間：{entry['time']}")
    if entry['source']:
        meta.append(f"> 來源：{entry['source']}")
    if meta:
        out += meta + ['']

    if entry['note']:
        out += ['\n'.join(('> ' + ln.strip()) if ln.strip() else '>'
                          for ln in entry['note'].split('\n')), '']

    out += ['<!--dual 🇬🇧 English|🇹🇼 中文翻譯-->', '']
    for en_group, zh_group in pairs:
        out += ['<!--src-->', '', '\n\n'.join(en_group) or '&nbsp;', '']
        out += ['<!--tgt-->', '', '\n\n'.join(zh_group) or '&nbsp;', '']
    out += ['<!--/dual-->', '']
    return '\n'.join(out)


def opt_value(name, default=None):
    """讀取 --name value 形式的參數。"""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


TIME_LINE = re.compile(r'對話時間：\s*([\d\-: ]+)')


def latest_time(outdir):
    """掃出資料夾裡最新的一則對話時間。"""
    newest = ''
    if not os.path.isdir(outdir):
        return newest
    for name in os.listdir(outdir):
        if not name.endswith('.md'):
            continue
        try:
            with open(os.path.join(outdir, name), encoding='utf-8') as f:
                m = TIME_LINE.search(f.read(2000))
        except OSError:
            continue
        if m:
            newest = max(newest, m.group(1).strip())
    return newest


SRC_BLOCK = re.compile(r'<!--src-->\s*\n(.*?)(?=\n<!--(?:tgt|src|/dual)-->)', re.S)


def signature(text):
    """把一段英文正規化成比對用的指紋。"""
    return re.sub(r'\s+', ' ', text).strip().lower()[:120]


def existing_signatures(outdir):
    """掃出資料夾裡每篇的英文指紋，用來判斷是不是已經收過了。

    指紋取「整篇英文接起來的開頭」，而不是第一段 ——
    因為段落有可能被合併，用單段當指紋會對不上。
    """
    sigs = {}
    if not os.path.isdir(outdir):
        return sigs
    for name in sorted(os.listdir(outdir)):
        if not name.endswith('.md'):
            continue
        try:
            with open(os.path.join(outdir, name), encoding='utf-8') as f:
                blocks = SRC_BLOCK.findall(f.read())
        except OSError:
            continue
        if blocks:
            sigs.setdefault(signature(' '.join(blocks)), name)
    return sigs


def existing_numbers(outdir, prefix):
    """掃出資料夾裡既有的編號，用來決定接續起點。"""
    pat = re.compile(r'^' + re.escape(prefix) + r'(\d+)\.md$')
    nums = []
    if os.path.isdir(outdir):
        for name in os.listdir(outdir):
            m = pat.match(name)
            if m:
                nums.append(int(m.group(1)))
    return nums


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    # --start / --prefix 的值不算位置參數
    for flag in ('--start', '--prefix'):
        v = opt_value(flag)
        if v in args:
            args.remove(v)

    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    src, outdir = args[0], args[1]

    force = '--force' in sys.argv
    append = '--append' in sys.argv
    skip_dup = '--skip-dup' in sys.argv
    after = opt_value('--after')
    prefix = opt_value('--prefix', '') or ''

    if not os.path.exists(src):
        print(f'找不到檔案：{src}')
        sys.exit(1)

    # ---- 起始編號 ----
    start = opt_value('--start')
    if start is not None:
        try:
            start = int(start)
        except ValueError:
            print(f'--start 要接數字，你給的是：{start}')
            sys.exit(1)
    elif append:
        nums = existing_numbers(outdir, prefix)
        start = (max(nums) + 1) if nums else 1
        print(f'--append：既有最大編號是 {max(nums) if nums else 0}，'
              f'新的從 {start:02d} 開始\n')
    else:
        start = 1

    os.makedirs(outdir, exist_ok=True)

    entries = parse(read_docx(src))
    if not entries:
        print('沒有解析到任何對話。請確認這份 .docx 是「保留對話格式」的匯出檔，'
              '內容應該要有 you asked: / message time: / gemini response: 這些標記。')
        sys.exit(1)

    # ---- 依對話時間過濾 ----
    if after:
        if after.lower() == 'auto':
            after = latest_time(outdir)
            if not after:
                print('--after auto：資料夾裡找不到對話時間，這次全部收進來\n')
            else:
                print(f'--after auto：資料夾裡最新一篇是 {after}，只收比這更新的')
        if after:
            before_n = len(entries)
            entries = [e for e in entries if e['time'] > after]
            print(f'--after：{before_n} 篇裡有 {len(entries)} 篇比 {after} 新\n')
            if not entries:
                print('沒有更新的對話，不需要做任何事。')
                sys.exit(0)

    # ---- 去重：跳過資料夾裡已經有的篇章 ----
    if skip_dup:
        have = existing_signatures(outdir)
        kept, dropped = [], []
        for e in entries:
            sig = signature(' '.join(e['en']))
            if sig in have:
                dropped.append(have[sig])
            else:
                kept.append(e)
                have[sig] = '(這次新增)'
        if dropped:
            print(f'--skip-dup：{len(dropped)} 篇已經收過了，跳過'
                  f'（對應到 {dropped[0]} 等檔案）')
        print(f'--skip-dup：實際要新增 {len(kept)} 篇\n')
        entries = kept
        if not entries:
            print('沒有新的內容，不需要做任何事。')
            sys.exit(0)

    # ---- 防呆：會不會蓋掉既有檔案 ----
    targets = [os.path.join(outdir, f'{prefix}{start + k:02d}.md')
               for k in range(len(entries))]
    clash = [t for t in targets if os.path.exists(t)]

    if clash and not force:
        print(f'⛔ 中止：這樣做會覆蓋 {len(clash)} 個既有檔案\n')
        for t in clash[:10]:
            print('   ' + t)
        if len(clash) > 10:
            print(f'   …還有 {len(clash) - 10} 個')
        print('\n可以這樣做：')
        print(f'  1. 輸出到新資料夾    python {os.path.basename(sys.argv[0])} '
              f'"{src}" 對照閱讀/另一個資料夾')
        print(f'  2. 接在編號後面繼續  python {os.path.basename(sys.argv[0])} '
              f'"{src}" {outdir} --append')
        print(f'  3. 檔名加前綴避開    python {os.path.basename(sys.argv[0])} '
              f'"{src}" {outdir} --prefix b')
        print(f'  4. 只收新增的部分    python {os.path.basename(sys.argv[0])} '
              f'"{src}" {outdir} --append --skip-dup')
        print(f'  5. 只收更新的對話    python {os.path.basename(sys.argv[0])} '
              f'"{src}" {outdir} --append --after auto')
        print('\n（真的要覆蓋才加 --force）')
        sys.exit(1)

    if clash and force:
        print(f'⚠️ --force：即將覆蓋 {len(clash)} 個既有檔案\n')

    print(f'找到 {len(entries)} 篇\n')

    rows, seen, flagged = [], {}, []
    for i, e in enumerate(entries, start):
        pairs = align(e['en'], e['zh'])
        odd = [1 for a, b in pairs if (len(a), len(b)) != (1, 1)]

        title = make_title(e, i)
        fname = f'{prefix}{i:02d}.md'
        with open(os.path.join(outdir, fname), 'w', encoding='utf-8') as f:
            f.write(make_page(e, title, pairs))
        rows.append(f'* [{title}]({outdir}/{fname})')

        key = e['en'][0][:120]
        dup = f'  ⚠️ 原文與第 {seen[key]} 篇重複' if key in seen else ''
        seen.setdefault(key, i)

        note = f'  ← 有 {len(odd)} 處合併，建議檢查' if odd else ''
        if odd:
            flagged.append(i)
        print(f"  {fname}  英文 {len(e['en']):>3} 段 / 中文 {len(e['zh']):>3} 段{note}{dup}")

    print(f'\n完全逐段對齊：{len(entries) - len(flagged)} / {len(entries)} 篇')
    if flagged:
        print('需要看一眼的篇數：' + '、'.join(f'{n:02d}' for n in flagged))

    print('\n把下面幾行貼進 SUMMARY.md：\n')
    print('\n'.join(rows))


if __name__ == '__main__':
    main()
