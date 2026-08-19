import sys
import re
import json
import glob
import os
from datetime import date

import fitz

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import group_regulations, clean_content_lines, parse_front_matter, parse_body
from toc import TOC_PAGE_RANGE

OUT_DIR = os.path.join(os.path.dirname(__file__), "output", "history")


def parse_filename_date(fn):
    m = re.search(r'\(([^)]+)\)', fn)
    raw = m.group(1)
    parts = [p for p in raw.split('.') if p]
    year = parts[0]
    rest = parts[1:]
    if len(year) > 4:
        leftover = year[4:]
        year = year[:4]
        rest = [leftover] + rest
    y = int(year)
    mo = int(rest[0])
    d = int(rest[1]) if len(rest) > 1 else 1
    return date(y, mo, d)


def extract_snapshot(pdf_path):
    doc = fitz.open(pdf_path)
    pages = [doc[i].get_text() for i in range(len(doc))]
    for i in TOC_PAGE_RANGE:
        pages[i] = ''
    groups = group_regulations(pages)
    doc.close()

    records = []
    for g in groups:
        lines = clean_content_lines(g)
        title, enact_date, amend_dates, body_lines = parse_front_matter(lines)
        articles, addenda, attachments = parse_body(body_lines)
        records.append({
            'index_no': g['index_no'],
            'first_header': g['first_header'],
            'title': title,
            'enact_date': enact_date,
            'amend_dates': amend_dates,
            'article_count': len(articles),
            'articles': articles,
            'pdf_pages': [p[0] + 1 for p in g['pages']],
        })
    return records


def main():
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), '..', '규정집(*.pdf')))
    dated = sorted((parse_filename_date(os.path.basename(f)), f) for f in files)

    os.makedirs(OUT_DIR, exist_ok=True)

    summary = []
    for d, path in dated:
        fn = os.path.basename(path)
        records = extract_snapshot(path)
        zero_article = sum(1 for r in records if r['article_count'] == 0)
        out_path = os.path.join(OUT_DIR, f"{d.isoformat()}.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({'date': d.isoformat(), 'source_file': fn, 'regulations': records}, f, ensure_ascii=False, indent=2)
        summary.append((d.isoformat(), fn, len(records), zero_article))
        print(f"{d.isoformat()}  {fn}  groups={len(records)}  zero_article={zero_article}", file=sys.stderr)

    with open(os.path.join(OUT_DIR, '_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
