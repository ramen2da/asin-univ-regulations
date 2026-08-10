import re
import fitz

TOC_PAGE_RANGE = range(2, 8)  # 0-indexed pages 3~8

ROMAN_RE = re.compile(r'^([ⅠⅡⅢⅣ])\.\s*(.*)$')
LETTER_RE = re.compile(r'^([A-D])\.\s*(.*)$')
NUM_RE = re.compile(r'^(\d+)\.\s*(.*)$')


def cluster_rows(words, y_tol=3.0):
    rows = []
    current_y = None
    current_row = []
    for w in sorted(words, key=lambda w: w[1]):
        y = w[1]
        if current_y is None or abs(y - current_y) <= y_tol:
            current_row.append(w)
            current_y = y if current_y is None else current_y
        else:
            rows.append(current_row)
            current_row = [w]
            current_y = y
    if current_row:
        rows.append(current_row)
    return [sorted(r, key=lambda w: w[0]) for r in rows]


def row_text(row):
    return ' '.join(w[4] for w in row)


def parse_toc(doc):
    entries = []
    cur_l0 = None  # 대분류
    cur_l1 = None  # 중분류

    for pidx in TOC_PAGE_RANGE:
        words = doc[pidx].get_text('words')
        rows = cluster_rows(words)
        for row in rows:
            text = row_text(row)
            if not text.strip() or text.strip() == '목 차':
                continue

            m = ROMAN_RE.match(text.strip())
            if m:
                cur_l0 = re.sub(r'\s+', ' ', m.group(2)).strip()
                cur_l1 = None
                continue

            m = LETTER_RE.match(text.strip())
            if m:
                rest = m.group(2).replace('·', '').strip()
                rest = re.sub(r'\s+', ' ', rest)
                # rest may end with a page number
                pm = re.match(r'^(.*?)\s*(\d+)$', rest)
                cur_l1 = pm.group(1).strip() if pm else rest
                continue

            m = NUM_RE.match(text.strip())
            if m:
                index_no = m.group(1)
                rest = m.group(2).replace('·', '').strip()
                rest = re.sub(r'\s+', ' ', rest)
                pm = re.match(r'^(.*?)\s*(\d+)$', rest)
                if not pm:
                    continue  # not a real entry (no trailing page number)
                title = pm.group(1).strip()
                page_display = int(pm.group(2))
                entries.append({
                    'l0': cur_l0,
                    'l1': cur_l1,
                    'index_no': index_no,
                    'title': title,
                    'page_display': page_display,
                })
                continue
            # else: department/sub-index rows or divider text - ignore

    return entries


def build_display_page_map(doc):
    """Map displayed page number (footer '- N -') -> pdf page index (0-based)."""
    footer_re = re.compile(r'^-\s*(\d+)\s*-$')
    mapping = {}
    for idx in range(len(doc)):
        text = doc[idx].get_text()
        for line in text.split('\n'):
            m = footer_re.match(line.strip())
            if m:
                n = int(m.group(1))
                if n not in mapping:
                    mapping[n] = idx
                break
    return mapping


if __name__ == '__main__':
    import json
    doc = fitz.open('규정집(2026.07.11).pdf')
    entries = parse_toc(doc)
    pagemap = build_display_page_map(doc)

    for e in entries:
        e['pdf_index'] = pagemap.get(e['page_display'])

    out_path = 'pipeline/output/toc.json'
    import os
    os.makedirs('pipeline/output', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    import sys
    print(f'TOC 항목 수: {len(entries)}', file=sys.stderr)
    missing = [e for e in entries if e['pdf_index'] is None]
    print(f'페이지 매핑 실패: {len(missing)}건', file=sys.stderr)
