"""Builds per-edition snapshots (pipeline/output/history/<date>.json) for the
2020-2022 규정집 volumes stored under file/11 규정/, which extract_history.py
does not cover (it only globs the 2023+ volumes in the project root).

Each volume's file name carries its effective date as 개정일YYYY.MM.DD (or a
bare YYYY.M.D tail); the snapshot uses the same record shape as the existing
2023+ snapshots so build_revision_history.py consumes both identically.
"""
import glob
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from extract_history import extract_snapshot

ROOT = os.path.join(os.path.dirname(__file__), '..', 'file', '11 규정')
OUT_DIR = os.path.join(os.path.dirname(__file__), 'output', 'history')

DATE_RE = re.compile(r'(20\d{2})\D{0,3}(\d{1,2})\D{1,2}(\d{1,2})')


def strip_page_noise(records):
    """The 2020-2021 volumes print each regulation's own "N. 규정명" running
    header and "- N -" page footer inline in the text stream, so they land
    mid-article after PyMuPDF joins the lines - and show up as false
    'changes' in the diff. Remove them, matching only titles that are real
    regulation names in this corpus."""
    titles = set()
    for r in records:
        if r.get('title'):
            titles.add(r['title'])
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'regulations.db'))
        titles.update(t for (t,) in conn.execute('SELECT title FROM regulations'))
        conn.close()
    except sqlite3.Error:
        pass
    title_re = re.compile(
        r'\s?\d{1,3}\.\s*(?:' + '|'.join(re.escape(t) for t in sorted(titles, key=len, reverse=True)) + r')\s?'
    )
    footer_re = re.compile(r'-\s*\d{1,3}\s*-')
    for r in records:
        for a in r.get('articles', []):
            for k in ('body', 'title'):
                if a.get(k):
                    a[k] = footer_re.sub('', title_re.sub(' ', a[k])).strip()
    return records


def edition_date(fn):
    base = os.path.basename(fn)
    m = re.search(r'\(개정일\s*(20\d{2}[^)]*)\)', base) or re.search(r'\((20\d{2}[^)]*)\)', base)
    raw = m.group(1) if m else base
    dm = DATE_RE.search(raw)
    if not dm:
        return None
    y, mo, d = (int(x) for x in dm.groups())
    return date(y, mo, d)


def main():
    files = glob.glob(os.path.join(ROOT, '**', '규정집*.pdf'), recursive=True)
    files = [f for f in files if '(이전자료)' not in f and '홈페이지' not in f and '업로드' not in f
             and '복사본' not in f and '/규정집 업로드' not in f]
    by_date = {}
    for f in sorted(files):
        d = edition_date(f)
        if d is None or not (date(2020, 1, 1) <= d <= date(2022, 12, 31)):
            continue
        by_date.setdefault(d, []).append(f)

    os.makedirs(OUT_DIR, exist_ok=True)
    summary = []
    for d in sorted(by_date):
        cands = by_date[d]
        path = sorted(cands, key=lambda p: (0 if p.lower().endswith('.pdf') else 1, p))[0]
        records = strip_page_noise(extract_snapshot(path))
        zero = sum(1 for r in records if r['article_count'] == 0)
        out_path = os.path.join(OUT_DIR, f'{d.isoformat()}.json')
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump({'date': d.isoformat(), 'source_file': os.path.basename(path),
                       'regulations': records}, fh, ensure_ascii=False, indent=2)
        summary.append([d.isoformat(), os.path.basename(path), len(records), zero])
        print(f'{d.isoformat()} groups={len(records)} zero_article={zero} candidates={len(cands)}', file=sys.stderr)

    summary_path = os.path.join(OUT_DIR, '_summary_2020_2022.json')
    with open(summary_path, 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
