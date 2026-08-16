#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Gemini 對話匯出的 .docx 轉成 HonKit 雙欄對照頁面。

適用格式：每則對話含 `you asked:` / `message time:` / `gemini response:` 三個標記
（就是那個能完整保留對話格式的匯出工具產出的樣子）。

用法：
    python3 convert2.py 陸漂文翻譯_.docx 對照閱讀/陸漂文

需要先安裝 pandoc。
"""

import math
import os
import re
import subprocess
import sys

ASK = re.compile(r'(?m)^you asked:.*$')
RESP = re.compile(r'(?m)^gemini response:.*$')
TIME = re.compile(r'(?m)^message time:\s*(.*)$')
MARK = re.compile(r'(?m)^.*以下.{0,25}翻譯.*$')
FROM = re.compile(r'https?://\S+')


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


def clean(s):
    # pandoc 會把破折號輸出成連續的 -，換回真正的破折號，
    # 否則在 Markdown 裡會被誤判成分隔線或標題底線。
    s = re.sub(r'-{3,}', lambda m: '\u2014' * max(1, len(m.group(0)) // 3), s)
    return s.replace('\\', '').strip()


def paras(text):
    return [clean(p) for p in re.split(r'\n\s*\n', text) if p.strip()]


# ---------- 對齊 ----------

def align(en, zh):
    """用動態規劃把英文段落對到中文段落。

    允許 1:1、1:2、2:1、2:2 以及單邊刪除，成本依「中文字數 / 英文字數」的
    比例落差計算。非 1:1 的罰分刻意設得很高，所以只有在段落數對不起來、
    或長度落差大到不合理時才會合併，段落數一致的情況幾乎都會維持 1:1。
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

def docx_to_md(path):
    return subprocess.run(
        ['pandoc', '-t', 'markdown', '--wrap=none', path],
        capture_output=True, text=True, check=True
    ).stdout.replace("\\'", "'").replace('\\"', '"')


def parse(md):
    m = FROM.search(md.split('\n')[0]) if md else None
    source = m.group(0).rstrip('*') if m else ''

    entries = []
    for block in ASK.split(md)[1:]:
        rm = RESP.search(block)
        if not rm:
            continue

        head = block[:rm.start()]
        tm = TIME.search(head)
        when = tm.group(1).strip() if tm else ''

        en = [p for p in paras(TIME.sub('', head))
              if not is_zh(p) and not p.lstrip().startswith('\u26a0')
              and not is_junk(p)]

        resp = RESP.sub('', block[rm.start():], count=1)
        mk = MARK.search(resp)
        note = clean(resp[:mk.start()]) if mk else ''
        zh = [p for p in paras(resp[mk.end():] if mk else resp)
              if not is_junk(p)]

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


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    entries = parse(docx_to_md(src))
    print(f'找到 {len(entries)} 篇\n')

    rows, seen, flagged = [], {}, []
    for i, e in enumerate(entries, 1):
        pairs = align(e['en'], e['zh'])
        odd = [(len(a), len(b)) for a, b in pairs if (len(a), len(b)) != (1, 1)]

        title = make_title(e, i)
        fname = f'{i:02d}.md'
        with open(os.path.join(outdir, fname), 'w', encoding='utf-8') as f:
            f.write(make_page(e, title, pairs))
        rows.append(f'* [{title}]({outdir}/{fname})')

        key = e['en'][0][:120]
        dup = f"  ⚠️ 原文與第 {seen[key]} 篇重複" if key in seen else ''
        seen.setdefault(key, i)

        note = ''
        if odd:
            note = f"  ← 有 {len(odd)} 處合併，建議檢查"
            flagged.append(i)
        print(f"  {fname}  英文 {len(e['en']):>3} 段 / 中文 {len(e['zh']):>3} 段{note}{dup}")

    print(f"\n完全逐段對齊：{len(entries) - len(flagged)} / {len(entries)} 篇")
    if flagged:
        print("需要看一眼的篇數：" + '、'.join(f'{n:02d}' for n in flagged))

    print('\n把下面幾行貼進 SUMMARY.md：\n')
    print('\n'.join(rows))


if __name__ == '__main__':
    main()
