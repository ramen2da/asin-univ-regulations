import fitz
import re
import json
import os
import sys

from toc import parse_toc, TOC_PAGE_RANGE

PDF_PATH = "규정집(2026.07.11).pdf"
OUT_PATH = "pipeline/output/regulations_final.json"

DIVIDER_RE = re.compile(r'^[ⅠⅡⅢⅣ]\.')
HEADER_RE = re.compile(r'^(\d+)\.\s*(.+)$')
FOOTER_RE = re.compile(r'^-\s*\d+\s*-$')
CHAPTER_RE = re.compile(r'^제\s*(\d+)\s*장\s+(.*)$')
SECTION_RE = re.compile(r'^제\s*(\d+)\s*절\s+(.*)$')
GWAN_RE = re.compile(r'^제\s*(\d+)\s*관\s+(.*)$')
ARTICLE_RE = re.compile(r'^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\(([^)]*)\))?')
ADDENDA_RE = re.compile(r'^부\s*칙$|^부\s*칙\s')
DATE_LINE_RE = re.compile(r'^(제정|개정|전면\s*개정|폐지|신설)\s*([\d.\s,]+)$')

# Known source-PDF anomalies where a new regulation's running header does not
# actually change its printed number from the previous regulation's. Keyed by
# 0-based pdf page index where the NEW regulation genuinely starts.
FORCE_NEW_GROUP_AT = {491, 492}

# Known source-PDF anomaly in the opposite direction: the running header already
# shows the NEXT regulation's number/title, but the page's content is actually
# the tail end (addenda) of the PREVIOUS regulation. Keyed by 0-based pdf page
# index that should be forced to continue the currently-open group instead of
# starting a new one.
FORCE_CONTINUE_AT = {575}


def normalize_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


def group_regulations(pages, force_new_group_at=frozenset(), force_continue_at=frozenset()):
    """Group consecutive pages into regulations using the running header's leading
    index number ('N.') as the continuation key - robust to department-table
    suffixes like '3. 사무분장 규정-기획처'."""
    groups = []
    current = None
    for idx, text in enumerate(pages):
        lines = text.split('\n')
        first_nonempty = next((l for l in lines if l.strip()), '')
        stripped = first_nonempty.strip()

        if not stripped or DIVIDER_RE.match(stripped):
            continue

        m = HEADER_RE.match(stripped)
        if not m:
            if current is not None:
                current['pages'].append((idx, lines))
            continue

        idx_no = m.group(1)
        title_key = m.group(2).replace(' ', '').replace('·', '').replace('․', '')

        # Manually-identified anomaly in the source PDF: pdf index 491 ("15. 장애학생
        # 특별지원위원회 운영규정") and pdf index 492 ("15. 교육만족도조사 규정") share the
        # same mistaken running-header number for two genuinely different regulations
        # (the real "14" was never printed). Force a boundary there.
        force_new_group = idx in force_new_group_at
        force_continue = idx in force_continue_at

        try:
            is_backward_typo = int(idx_no) < int(current['index_no']) and int(idx_no) != 1
        except (ValueError, TypeError):
            is_backward_typo = False

        if current is not None and force_continue:
            current['pages'].append((idx, lines))
        elif current is not None and not force_new_group and (idx_no == current['index_no'] or is_backward_typo):
            # Exact repeat, or a smaller-than-current, non-restart number: almost
            # certainly a typo'd running header on a continuation page (e.g. "24."
            # printed instead of "26.") rather than a genuinely new regulation.
            current['pages'].append((idx, lines))
        else:
            current = {
                'index_no': idx_no,
                'title_key': title_key,
                'first_header': normalize_ws(stripped),
                'pages': [(idx, lines)],
            }
            groups.append(current)
    return groups


def clean_content_lines(group):
    """Returns a list of (pdf_page_index, line) tuples so addenda/attachment
    content can later be traced back to the exact PDF page it came from."""
    out = []
    for idx, lines in group['pages']:
        started_header = False
        for line in lines:
            s = line.strip()
            if not started_header:
                if not s:
                    continue
                started_header = True
                continue
            if FOOTER_RE.match(s):
                continue
            out.append((idx, line))
    return out


def parse_front_matter(lines):
    """lines: list of (pdf_page_index, line)."""
    body_start = None
    for i, (_, line) in enumerate(lines):
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
    for _, line in front:
        s = line.strip()
        if not s:
            continue
        m = DATE_LINE_RE.match(s)
        if m:
            kind, date = m.groups()
            for part in date.split(','):
                d = re.sub(r'\s+', '', part).strip('.')
                if d:
                    amend_dates.append(d)
            if kind == '제정' and enact_date is None:
                enact_date = amend_dates[-1] if amend_dates else None
        else:
            title_parts.append(s)

    title = normalize_ws(' '.join(title_parts))
    return title, enact_date, amend_dates, lines[body_start:]


ATTACHMENT_MARKER_RE = re.compile(r'^\[(별지서식|별표)[^\]]*\]')


def split_addenda(addenda_lines):
    """addenda_lines: list of (pdf_page_index, line). Separates real 부칙 text
    from attached forms/tables (별지서식, 별표), keeping track of the PDF page
    range each attachment spans so it can be matched back to the PDF later."""
    addenda = []
    attachments = []
    current = None

    for page_idx, line in addenda_lines:
        s = line.strip()
        if ATTACHMENT_MARKER_RE.match(s):
            current = {'label': s, 'lines': [], 'pages': set()}
            attachments.append(current)
        elif current is not None:
            current['lines'].append(s)
            current['pages'].add(page_idx)
        else:
            addenda.append(s)

    for att in attachments:
        pages = sorted(att['pages']) if att['pages'] else []
        att['start_page'] = (pages[0] + 1) if pages else None
        att['end_page'] = (pages[-1] + 1) if pages else None
        del att['pages']

    return addenda, attachments


def parse_body(lines):
    """lines: list of (pdf_page_index, line)."""
    chapter = None
    section = None
    gwan = None
    articles = []
    addenda_lines = []
    current_article = None
    in_addenda = False

    def flush_article():
        nonlocal current_article
        if current_article is not None:
            current_article['body'] = normalize_ws(' '.join(current_article['body_lines']))
            del current_article['body_lines']
            articles.append(current_article)
            current_article = None

    for page_idx, line in lines:
        s = line.strip()
        if not s:
            continue

        if ADDENDA_RE.match(s):
            flush_article()
            in_addenda = True
            continue

        if in_addenda:
            addenda_lines.append((page_idx, s))
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
    addenda, attachments = split_addenda(addenda_lines)
    return articles, addenda, attachments


def extract_pdf(pdf_path, force_new_group_at=frozenset(), force_continue_at=frozenset()):
    """Parse a regulation-book PDF into (results, problems, toc_entries, groups)."""
    doc = fitz.open(pdf_path)
    pages = [doc[i].get_text() for i in range(len(doc))]

    toc_entries = parse_toc(doc)

    pages_for_grouping = list(pages)
    for i in TOC_PAGE_RANGE:
        pages_for_grouping[i] = ''
    groups = group_regulations(pages_for_grouping, force_new_group_at, force_continue_at)

    n = min(len(toc_entries), len(groups))
    results = []
    problems = []

    for i in range(n):
        toc_e = toc_entries[i]
        g = groups[i]

        lines = clean_content_lines(g)
        title, enact_date, amend_dates, body_lines = parse_front_matter(lines)
        articles, addenda, attachments = parse_body(body_lines)

        rec = {
            'seq': i + 1,
            'l0': toc_e['l0'],
            'l1': toc_e['l1'],
            'index_no': g['index_no'],
            'toc_title': toc_e['title'],
            'parsed_title': title,
            'enact_date': enact_date,
            'amend_dates': amend_dates,
            'article_count': len(articles),
            'articles': articles,
            'addenda': addenda,
            'attachments': attachments,
            'pdf_pages': [p[0] + 1 for p in g['pages']],
        }
        results.append(rec)

        if len(articles) == 0:
            problems.append((i, toc_e['title'], 'zero articles'))
        if re.search(r'\d', title) and not amend_dates:
            problems.append((i, toc_e['title'], 'title looks glued with dates'))
        # cross-check toc title vs parsed title roughly
        toc_t_norm = toc_e['title'].replace(' ', '')
        parsed_t_norm = title.replace(' ', '')
        if toc_t_norm and toc_t_norm not in parsed_t_norm and parsed_t_norm not in toc_t_norm:
            problems.append((i, toc_e['title'], f'title mismatch vs parsed="{title}"'))

    doc.close()
    return results, problems, toc_entries, groups


def main():
    results, problems, toc_entries, groups = extract_pdf(
        PDF_PATH, FORCE_NEW_GROUP_AT, FORCE_CONTINUE_AT
    )

    print(f'TOC 항목 수: {len(toc_entries)} / 헤더 그룹 수: {len(groups)}', file=sys.stderr)

    os.makedirs('pipeline/output', exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'{len(results)}건 파싱 완료 (TOC/그룹 길이 불일치: {len(toc_entries) - len(groups)})', file=sys.stderr)
    print(f'의심 사례 {len(problems)}건', file=sys.stderr)
    for i, t, reason in problems:
        print(f'  [seq {i+1}] {t} - {reason}', file=sys.stderr)


if __name__ == '__main__':
    main()
