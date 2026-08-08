#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Gemini 翻譯對話的 Google Docs（.docx）轉成 HonKit 雙欄對照頁面。

用法：
    python3 convert.py 陸漂文翻譯.docx 對照閱讀/陸漂文

需要先安裝 pandoc。
"""

import os
import re
import subprocess
import sys

SENT_END = re.compile(r'(?<=[.!?])(["\')\u2019\u201d]*)\s+')
TRANS_MARK = re.compile(r'(?m)^.{0,10}以下.{0,20}翻譯.*$')


def docx_to_md(path):
    out = subprocess.run(
        ["pandoc", "-t", "markdown", "--wrap=none", path],
        capture_output=True, text=True, check=True
    ).stdout
    return out.replace("\\'", "'").replace('\\"', '"')


def clean(s):
    # pandoc 會把破折號輸出成連續的 -，換回真正的破折號，
    # 否則在 Markdown 裡會被誤判成分隔線或標題底線。
    s = re.sub(r'-{3,}', lambda m: '\u2014' * max(1, len(m.group(0)) // 3), s)
    s = s.replace("\\", "")
    return s.strip()


def split_sentences(text):
    text = re.sub(r'\s+', ' ', text).strip()
    pieces = SENT_END.split(text)
    out, i = [], 0
    while i < len(pieces):
        seg = pieces[i]
        tail = pieces[i + 1] if i + 1 < len(pieces) else ""
        if seg.strip():
            out.append((seg + tail).strip())
        i += 2
    return out


def group_sentences(sents, weights):
    """把英文句子分成 len(weights) 組，各組長度比例對齊中文各段的長度比例。
    切點一定落在句尾，不會切在句子中間，順序也不會被打亂。"""
    n = len(weights)
    if n <= 1 or not sents:
        return [" ".join(sents)]

    wtotal = float(sum(weights)) or 1.0
    targets, acc = [], 0.0
    for w in weights[:-1]:
        acc += w / wtotal
        targets.append(acc)

    lens = [len(s) for s in sents]
    total = float(sum(lens)) or 1.0
    groups, buf, run, ti = [], [], 0.0, 0
    for s, L in zip(sents, lens):
        buf.append(s)
        run += L
        while ti < len(targets) and run / total >= targets[ti]:
            groups.append(" ".join(buf))
            buf, ti = [], ti + 1
    groups.append(" ".join(buf))
    while len(groups) < n:
        groups.append("")
    if len(groups) > n:
        groups[n - 1:] = [" ".join(x for x in groups[n - 1:] if x)]
    return groups


def parse(md):
    entries = []
    parts = re.split(r'(?m)^\*?User prompt:', md)
    for raw in parts[1:]:
        m = re.search(r'(?m)^Response:', raw)
        if not m:
            continue
        en = clean(raw[:m.start()].strip().rstrip('*)').strip())
        resp = raw[m.start():]
        resp = re.sub(r'(?m)^Response:\s*', '', resp, count=1)

        mark = TRANS_MARK.search(resp)
        if mark:
            note = clean(resp[:mark.start()])
            zh = clean(resp[mark.end():])
        else:
            note, zh = "", clean(resp)

        zh_paras = [p.strip() for p in re.split(r'\n\s*\n', zh) if p.strip()]
        entries.append({"en": en, "note": note, "zh": zh_paras})
    return entries


def title_of(entry, idx):
    first = entry["zh"][0] if entry["zh"] else ""
    first = re.sub(r'[（(].*', '', first).strip()
    first = re.sub(r'[。！？，、\s]+$', '', first)
    if len(first) > 24:
        first = first[:24] + "…"
    return f"{idx:02d} {first}" if first else f"{idx:02d}"


def make_page(entry, title):
    sents = split_sentences(entry["en"])
    groups = group_sentences(sents, [len(z) for z in entry["zh"]])

    out = [f"# {title}", ""]
    if entry["note"]:
        note = "\n".join(
            ("> " + ln.strip()) if ln.strip() else ">"
            for ln in entry["note"].split("\n")
        )
        out += [note, ""]
    out += ["<!--dual 🇬🇧 English|🇹🇼 中文翻譯-->", ""]
    for g, z in zip(groups, entry["zh"]):
        out += ["<!--src-->", "", g if g else "&nbsp;", ""]
        out += ["<!--tgt-->", "", z, ""]
    out += ["<!--/dual-->", ""]
    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    entries = parse(docx_to_md(src))
    print(f"找到 {len(entries)} 篇")

    summary, seen = [], {}
    for i, e in enumerate(entries, 1):
        title = title_of(e, i)
        fname = f"{i:02d}.md"
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as f:
            f.write(make_page(e, title))
        summary.append(f"* [{title}]({outdir}/{fname})")

        key = e["en"][:200]
        if key in seen:
            print(f"  ⚠️  第 {i} 篇的原文與第 {seen[key]} 篇重複")
        else:
            seen[key] = i
        print(f"  {fname}  英文 {len(e['en'])} 字元 / 中文 {len(e['zh'])} 段")

    print("\n把下面幾行貼進 SUMMARY.md：\n")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
