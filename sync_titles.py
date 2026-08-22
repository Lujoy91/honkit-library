#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
以 SUMMARY.md 為準，把各個 .md 檔的第一行標題同步成 SUMMARY 裡的連結文字。

兩個方向都支援：

  預設（SUMMARY → md）
      以 SUMMARY.md 為準去修各個 .md 的標題。
      用於：.md 被覆蓋掉、標題變回自動產生的版本，但 SUMMARY.md 還是好的。

  --to-summary（md → SUMMARY）
      以各個 .md 的標題為準去修 SUMMARY.md。
      用於：你直接改了 .md 裡的 # 標題，要讓側邊欄跟著更新。

用法（在 翻譯收藏 資料夾裡執行）：

    # 先預覽，不會動到任何檔案
    python sync_titles.py 對照閱讀/陸漂文 --to-summary

    # 確認沒問題後才實際寫入
    python sync_titles.py 對照閱讀/陸漂文 --to-summary --write

不指定資料夾就會處理 SUMMARY.md 裡列到的全部 .md。

只需要 Python 3，不需要裝任何東西。
"""

import os
import re
import sys

SUMMARY = 'SUMMARY.md'
ENTRY = re.compile(r'^\s*[\*\-]\s*\[([^\]]+)\]\(([^)]+\.md)\)', re.M)


def sync_to_summary(entries, only, write):
    """方向：各個 .md 的 # 標題  →  SUMMARY.md 的連結文字。"""
    with open(SUMMARY, encoding='utf-8', newline='') as f:
        text = f.read()
    original = text
    changed = same = skipped = 0

    for old_title, path in entries:
        clean_path = path.split('#')[0].strip()
        if only and not clean_path.replace('\\', '/').startswith(only):
            continue

        if not os.path.exists(clean_path):
            print(f'  ?  找不到 {clean_path}')
            skipped += 1
            continue

        with open(clean_path, encoding='utf-8', newline='') as f:
            head = f.readline()
        if not head.lstrip().startswith('#'):
            print(f'  ?  {clean_path} 第一行不是標題，跳過')
            skipped += 1
            continue

        new_title = head.lstrip('#').strip()
        if new_title == old_title.strip():
            same += 1
            continue

        line_pat = re.compile(
            r'(\*|-)(\s*\[)' + re.escape(old_title) + r'(\]\(' + re.escape(path) + r'\))')
        if not line_pat.search(text):
            print(f'  ?  SUMMARY.md 裡找不到 {clean_path} 的項目')
            skipped += 1
            continue

        print(f'  →  {clean_path}')
        print(f'       側邊欄現在：{old_title}')
        print(f'       改成：      {new_title}')
        changed += 1
        text = line_pat.sub(lambda m: m.group(1) + m.group(2) + new_title + m.group(3),
                            text, count=1)

    if write and text != original:
        with open(SUMMARY, 'w', encoding='utf-8', newline='') as f:
            f.write(text)

    print()
    print(f'需要修改 {changed} 個，{same} 個本來就一樣'
          + (f'，{skipped} 個跳過' if skipped else '') + '。')
    if changed and not write:
        print('以上只是預覽，SUMMARY.md 沒有被動到。')
        print('確認沒問題後，在指令最後加上 --write')
    elif changed and write:
        print('SUMMARY.md 已更新。接著跑 npm run build 就完成了。')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    write = '--write' in sys.argv
    to_summary = '--to-summary' in sys.argv
    only = args[0].replace('\\', '/').rstrip('/') if args else None

    if not os.path.exists(SUMMARY):
        print(f'找不到 {SUMMARY}。請在 翻譯收藏 資料夾裡執行這支腳本。')
        sys.exit(1)

    with open(SUMMARY, encoding='utf-8') as f:
        entries = ENTRY.findall(f.read())

    if not entries:
        print('SUMMARY.md 裡沒有找到任何 .md 連結。')
        sys.exit(1)

    changed = same = skipped = 0

    if to_summary:
        sync_to_summary(entries, only, write)
        return

    for title, path in entries:
        path = path.split('#')[0].strip()
        norm = path.replace('\\', '/')
        if only and not norm.startswith(only):
            continue

        title = title.strip()

        if not os.path.exists(path):
            print(f'  ?  找不到 {path}')
            skipped += 1
            continue

        # newline='' ：不做換行符轉換，確保除了第一行以外，整份檔案原封不動
        with open(path, encoding='utf-8', newline='') as f:
            content = f.read()

        m = re.match(r'([^\r\n]*)(\r\n|\r|\n|$)', content)
        head, eol = m.group(1), m.group(2)

        if not head.lstrip().startswith('#'):
            print(f'  ?  {path} 第一行不是標題，跳過')
            skipped += 1
            continue

        now = head.lstrip('#').strip()
        if now == title:
            same += 1
            continue

        print(f'  →  {path}')
        print(f'       現在：{now}')
        print(f'       改成：{title}')
        changed += 1

        if write:
            rest = content[len(head) + len(eol):]
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write('# ' + title + eol + rest)

    print()
    print(f'需要修改 {changed} 個，{same} 個本來就一樣'
          + (f'，{skipped} 個跳過' if skipped else '') + '。')

    if changed and not write:
        print('以上只是預覽，沒有動到任何檔案。')
        print('確認沒問題後，執行：python sync_titles.py --write')
    elif changed and write:
        print('已寫入。接著跑 npm run build 就完成了。')


if __name__ == '__main__':
    main()
