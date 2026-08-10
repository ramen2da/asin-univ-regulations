import fitz
import re
import json
import os
import sys

from toc import parse_toc, build_display_page_map

PDF_PATH = "규정집(2026.07.11).pdf"
OUT_PATH = "pipeline/output/regulations_full.json"

FOOTER_RE = re.compile(r'^-\s*\d+\s*-$')
CHAPTER_RE = re.compile(r'^제\s*(\d+)\s*장\s+(.*)$')
SECTION_RE = re.compile(r'^제\s*(\d+)\s*절\s+(.*)$')
GWAN_RE = re.compile(r'^제\s*(\d+)\s*관\s+(.*)$')
ARTICLE_RE = re.compile(r'^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\(([^)]*)\))?')
ADDENDA_RE = re.compile(r'^부\s*칙$|^부\s*칙\s')
DATE_LINE_RE = re.compile(r'^(제정|개정|전면개정|폐지|신설|전면\s*개정)\s*([\d.\s,]+)$')


def normalize_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


def extract_range_lines(pages, start, end):
    """pages: list of page texts. start/end inclusive pdf indices. Drops first non-empty
    line of each page (running header) and footer page-number lines."""
    out = []
    for idx in range(start, end + 1):
        lines = pages[idx].split('\n')
        dropped_header = False
        for line in lines:
            s = line.strip()
            if not dropped_header:
                if not s:
                    continue
                dropped_header = True
                continue  # drop the header line itself
            if FOOTER_RE.match(s):
                continue
            out.append(line)
    return out


def parse_front_matter(lines):
    body_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if CHAPTER_RE.match(s) or ARTICLE_RE.match(s) or ADDENDA_RE.match(s):
            body_start = i
            break
    if body_start is None:
        body_start = len(lines)

    front = lines[:body_start]
    title_parts = []
    enact_date = None
    amend_dates = []
    for line in front:
        s = line.strip()
        if not s:
            continue
        m = DATE_LINE_RE.match(s)
        if m:
            kind, date = m.groups()
            for d in re.split(r'[,\s]+', date.strip()):
                d = d.strip('., ')
                if d:
                    amend_dates.append(d)
            if kind == '제정' and enact_date is None:
                enact_date = amend_dates[-1] if amend_dates else None
        else:
            title_parts.append(s)

    title = normalize_ws(' '.join(title_parts))
    return title, enact_date, amend_dates, lines[body_start:]


def parse_body(lines):
    chapter = None
    section = None
    gwan = None
    articles = []
    addenda = []
    current_article = None
    in_addenda = False

    def flush_article():
        nonlocal current_article
        if current_article is not None:
            current_article['body'] = normalize_ws(' '.join(current_article['body_lines']))
            del current_article['body_lines']
            articles.append(current_article)
            current_article = None

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if ADDENDA_RE.match(s):
            flush_article()
            in_addenda = True
            continue

        if in_addenda:
            addenda.append(s)
            continue

        m = CHAPTER_RE.match(s)
        if m:
            flush_article()
            chapter = normalize_ws(f"제{m.group(1)}장 {m.group(2)}")
            section = None
            gwan = None
            continue

        m = SECTION_RE.match(s)
        if m:
            flush_article()
            section = normalize_ws(f"제{m.group(1)}절 {m.group(2)}")
            gwan = None
            continue

        m = GWAN_RE.match(s)
        if m:
            flush_article()
            gwan = normalize_ws(f"제{m.group(1)}관 {m.group(2)}")
            continue

        m = ARTICLE_RE.match(s)
        if m:
            flush_article()
            no, sub_no, art_title = m.groups()
            current_article = {
                'chapter': chapter,
                'section': section,
                'gwan': gwan,
                'no': no,
                'sub_no': sub_no,
                'title': art_title,
                'body_lines': [s],
            }
            continue

        if current_article is not None:
            current_article['body_lines'].append(s)

    flush_article()
    return articles, addenda


def main():
    doc = fitz.open(PDF_PATH)
    pages = [doc[i].get_text() for i in range(len(doc))]
    entries = parse_toc(doc)
    pagemap = build_display_page_map(doc)
    for e in entries:
        e['pdf_index'] = pagemap.get(e['page_display'])

    results = []
    problems = []
    for i, e in enumerate(entries):
        start = e['pdf_index']
        end = (entries[i + 1]['pdf_index'] - 1) if i + 1 < len(entries) else len(pages) - 1
        if start is None or end is None or end < start:
            problems.append((e, 'invalid range'))
            continue

        lines = extract_range_lines(pages, start, end)
        title, enact_date, amend_dates, body_lines = parse_front_matter(lines)
        articles, addenda = parse_body(body_lines)

        rec = {
            'l0': e['l0'],
            'l1': e['l1'],
            'index_no': e['index_no'],
            'toc_title': e['title'],
            'parsed_title': title,
            'enact_date': enact_date,
            'amend_dates': amend_dates,
            'article_count': len(articles),
            'articles': articles,
            'addenda': addenda,
            'pdf_page_range': [start + 1, end + 1],
        }
        results.append(rec)

        if len(articles) == 0:
            problems.append((e, 'zero articles'))
        if re.search(r'\d', title) and not amend_dates:
            problems.append((e, 'title looks glued with dates'))

    os.makedirs('pipeline/output', exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'전체 규정 {len(entries)}건 중 {len(results)}건 파싱 완료', file=sys.stderr)
    print(f'의심 사례 {len(problems)}건', file=sys.stderr)
    for e, reason in problems:
        print(f"  [{e['index_no']}] {e['title']} (p.{e['page_display']}) - {reason}", file=sys.stderr)


if __name__ == '__main__':
    main()
