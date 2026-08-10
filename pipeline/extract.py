import fitz
import re
import json
import sys

PDF_PATH = "규정집(2026.07.11).pdf"
OUT_PATH = "pipeline/output/regulations_sample.json"

HEADER_RE = re.compile(r'^(\d+)\.\s*(.+)$')
DIVIDER_RE = re.compile(r'^[ⅠⅡⅢⅣ]\.')
FOOTER_RE = re.compile(r'^-\s*\d+\s*-$')
CHAPTER_RE = re.compile(r'^제\s*(\d+)\s*장\s+(.*)$')
SECTION_RE = re.compile(r'^제\s*(\d+)\s*절\s+(.*)$')
GWAN_RE = re.compile(r'^제\s*(\d+)\s*관\s+(.*)$')
ARTICLE_RE = re.compile(r'^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\(([^)]*)\))?')
ADDENDA_RE = re.compile(r'^부\s*칙')
DATE_LINE_RE = re.compile(r'^(제정|개정)\s+([\d.\s]+)$')


def normalize_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


def load_pages(doc):
    return [doc[i].get_text() for i in range(len(doc))]


def group_regulations(pages):
    """Group consecutive pages sharing the same running header 'N. Title'."""
    groups = []
    current = None
    for idx, text in enumerate(pages):
        lines = text.split('\n')
        first_nonempty = next((l for l in lines if l.strip()), '')
        stripped = first_nonempty.strip()

        if not stripped or DIVIDER_RE.match(stripped):
            current = None
            continue

        m = HEADER_RE.match(stripped)
        if not m:
            if current is not None:
                current['pages'].append((idx, lines))
            continue

        header_key = normalize_ws(stripped)
        if current is not None and current['header'] == header_key:
            current['pages'].append((idx, lines))
        else:
            current = {
                'header': header_key,
                'index_no': m.group(1),
                'pages': [(idx, lines)],
            }
            groups.append(current)
    return groups


def clean_content_lines(group):
    """Strip the running header line and page-footer line from each page, return flat line list."""
    out = []
    for idx, lines in group['pages']:
        started_header = False
        for i, line in enumerate(lines):
            s = line.strip()
            if not started_header and s and HEADER_RE.match(s):
                started_header = True
                continue
            if FOOTER_RE.match(s):
                continue
            out.append(line)
    return out


def parse_front_matter(lines):
    """Extract title + enactment/amendment dates before the first chapter/article marker."""
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
            date = normalize_ws(date)
            if kind == '제정':
                enact_date = date
            else:
                amend_dates.append(date)
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
            no, sub_no, title = m.groups()
            current_article = {
                'chapter': chapter,
                'section': section,
                'gwan': gwan,
                'no': no,
                'sub_no': sub_no,
                'title': title,
                'body_lines': [s],
            }
            continue

        if current_article is not None:
            current_article['body_lines'].append(s)
        # else: stray line before any article (shouldn't normally happen)

    flush_article()
    return articles, addenda


def parse_regulation(group):
    lines = [l for l in clean_content_lines(group)]
    title, enact_date, amend_dates, body_lines = parse_front_matter(lines)
    articles, addenda = parse_body(body_lines)
    return {
        'index_no': group['index_no'],
        'title': title,
        'enact_date': enact_date,
        'amend_dates': amend_dates,
        'article_count': len(articles),
        'articles': articles,
        'addenda': addenda,
        'source_pages': [idx + 1 for idx, _ in group['pages']],
    }


def main():
    doc = fitz.open(PDF_PATH)
    pages = load_pages(doc)
    groups = group_regulations(pages)

    print(f"총 {len(pages)}페이지, {len(groups)}개 규정 그룹 발견", file=sys.stderr)

    # Validate on a handful of regulations first
    sample_titles = ['정  관', '정관 시행세칙', '법인 사무분장 규정', '규정류 관리규정', '직제규정']
    sample_groups = [g for g in groups if any(normalize_ws(t) in g['header'] for t in sample_titles)][:5]

    results = [parse_regulation(g) for g in sample_groups]

    import os
    os.makedirs('pipeline/output', exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"{len(results)}개 규정 샘플 파싱 완료 -> {OUT_PATH}", file=sys.stderr)
    for r in results:
        print(f"  - [{r['index_no']}] {r['title']}: 조문 {r['article_count']}개, 부칙 {len(r['addenda'])}줄, 페이지 {r['source_pages'][0]}~{r['source_pages'][-1]}", file=sys.stderr)


if __name__ == '__main__':
    main()
