"""Converts the two historical per-regulation HWP dumps discovered this
session (file10-77.hwp, mtime 2012-06-22, and univ_01-22_1.hwp, mtime
~2014-03), matching to today's main-corpus regulations, into the same
"history snapshot" JSON shape build_revision_history.py already knows how
to diff against the live DB (see pipeline/output/history/*.json) - so this
data flows through the exact same, already-proven diff/noise-filtering/date-
resolution pipeline as the original 규정집 PDF-edition backfill, rather
than a second bespoke path.

Unlike that pipeline's compiled 규정집 editions (one PDF holding all ~113
regulations as of one date), this batch is one regulation per source file,
several of which needed their own title-cleanup since kordoc's front
matter here is noisier than the 대학원 batch (a leading TOC-style
"N. <title>" line duplicating the real title on the next line; or, on a
few files, a leftover worded amendment-date sentence that isn't dot-
formatted so extract_grdsch's DATE_LINE_RE front-matter pass doesn't
already strip it out).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_grdsch import (
    load_kordoc_markdown, parse_body, CHAPTER_RE, ARTICLE_RE,
)
from extract3 import DATE_LINE_RE, normalize_ws

SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'file')
MD_CACHE_DIR = r'C:\Users\bbuny\AppData\Local\Temp\hwp_check'
HIST_DIR = os.path.join(os.path.dirname(__file__), 'output', 'history')

DATE_ONLY_LINE_RE = re.compile(r'^(신설|개정|제정|폐지|전면\s*개정)\s*[\d년월일.\s,]+$')
LIST_PREFIX_RE = re.compile(r'^\d+[.\)]\s*')
MD_TABLE_ROW_RE = re.compile(r'^\|.*\|$')
MD_TABLE_DIVIDER_RE = re.compile(r'^\|[\s:|-]+\|$')
INLINE_DATE_RE = re.compile(r'(신설|개정|제정|폐지|전면\s*개정)\s*([\d]{4}\s*\.\s*[\d]{1,2}\s*\.\s*[\d]{1,2})')


def clean_title(front_lines):
    candidates = [
        l for l in front_lines
        if not DATE_ONLY_LINE_RE.match(l.strip()) and not MD_TABLE_ROW_RE.match(l.strip())
    ]
    if not candidates:
        candidates = front_lines
    candidates = [LIST_PREFIX_RE.sub('', c).strip() for c in candidates]
    candidates = [c for c in candidates if c]
    return candidates[-1] if candidates else ''


def parse_one(md_path):
    lines = load_kordoc_markdown(md_path)

    amend_dates = []
    enact_date = None
    remaining = []
    for l in lines:
        s = l.strip()
        m = DATE_LINE_RE.match(s)
        if m:
            d = m.group(2).strip().rstrip('.')
            amend_dates.append(d)
            if m.group(1) == '제정' and enact_date is None:
                enact_date = d
            continue
        # A handful of documents (long amendment histories) render their
        # 제정/개정 date list as a markdown table cell instead of one plain
        # line per date - "| 제정 1998. 09. 01<br>개정 2000. 12. 19... |
        # ...|" - rather than a separate regex path, just pull every
        # embedded "제정/개정 YYYY. MM. DD" out of the row's own text and
        # drop the row entirely (including its "| --- | --- |" divider,
        # which otherwise gets mistaken for a title candidate below).
        if MD_TABLE_ROW_RE.match(s):
            found = INLINE_DATE_RE.findall(s)
            for kind, d in found:
                d = re.sub(r'\s+', '', d)
                amend_dates.append(d)
                if kind == '제정' and enact_date is None:
                    enact_date = d
            if found or MD_TABLE_DIVIDER_RE.match(s):
                continue
        remaining.append(l)

    body_start = next(
        (i for i, l in enumerate(remaining) if CHAPTER_RE.match(l.strip()) or ARTICLE_RE.match(l.strip())),
        0,
    )
    front = remaining[:body_start]
    body_lines = remaining[body_start:]
    title = clean_title(front)

    articles, addenda, attachments = parse_body(body_lines)
    return {
        'index_no': '1',
        'first_header': title,
        'title': title,
        'enact_date': enact_date,
        'amend_dates': amend_dates,
        'article_count': len(articles),
        'articles': articles,
        'pdf_pages': [],
    }


BATCHES = [
    ('legacy_website_2012-06-22.json', '2012-06-22', [f'file{i:02d}' for i in range(10, 78) if i not in (23, 45, 63)]),
    ('legacy_website_2014-03-11.json', '2014-03-11', ['univ_01', 'univ_02', 'univ_03', 'univ_09', 'univ_21', 'univ_22', 'univ_22_1']),
]


def main():
    os.makedirs(HIST_DIR, exist_ok=True)
    for out_name, date, stems in BATCHES:
        regulations = []
        skipped = []
        for stem in stems:
            hwp_path = os.path.join(SRC_DIR, f'{stem}.hwp')
            if not os.path.exists(hwp_path):
                skipped.append(stem)
                continue
            md_path = os.path.join(MD_CACHE_DIR, f'{stem}.md')
            if not os.path.exists(md_path):
                skipped.append(stem)
                continue
            rec = parse_one(md_path)
            if rec['article_count'] == 0:
                skipped.append(stem)
                continue
            regulations.append(rec)

        out_path = os.path.join(HIST_DIR, out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({'date': date, 'source_file': out_name, 'regulations': regulations}, f, ensure_ascii=False, indent=2)
        print(f'{out_name}: {len(regulations)} regulations, {len(skipped)} skipped: {skipped}', file=sys.stderr)


if __name__ == '__main__':
    main()
