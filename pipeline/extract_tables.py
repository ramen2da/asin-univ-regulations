import json
import re
import sys

import fitz

PDF_PATH = "규정집(2026.07.11).pdf"
IN_PATH = "pipeline/output/regulations_final.json"
OUT_PATH = "pipeline/output/regulations_with_tables.json"


def normalize_for_match(s):
    return re.sub(r'\s+', '', s or '')


def flatten_table_text(rows):
    parts = []
    for row in rows:
        for cell in row:
            if cell:
                parts.append(cell)
    return normalize_for_match(' '.join(parts))


def overlap_score(table_text, attachment_text):
    """Rough containment-based overlap: fraction of attachment's distinctive
    3-char shingles that also appear in the table's flattened text."""
    if not attachment_text or not table_text:
        return 0.0
    shingles = {attachment_text[i:i + 3] for i in range(len(attachment_text) - 2)}
    if not shingles:
        return 0.0
    hits = sum(1 for sh in shingles if sh in table_text)
    return hits / len(shingles)


def is_degenerate(rows):
    """A find_tables() result where several original lines got mashed into a
    single cell (visible as embedded newlines) is a mis-detected borderless
    table, not a real grid - reject it rather than show garbled cells."""
    for row in rows:
        for cell in row:
            if cell and cell.count('\n') >= 3:
                return True
    return False


def find_best_table(doc, start_page, end_page, attachment_text):
    candidates = []
    for pno in range(start_page - 1, end_page):
        if pno < 0 or pno >= len(doc):
            continue
        page = doc[pno]
        try:
            tabs = page.find_tables()
        except Exception:
            continue
        for t in tabs.tables:
            if t.row_count < 2 or t.col_count < 2:
                continue
            try:
                rows = t.extract()
            except Exception:
                continue
            if is_degenerate(rows):
                continue
            score = overlap_score(flatten_table_text(rows), attachment_text)
            candidates.append((score, pno, rows))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0], reverse=True)
    best_score, _, best_rows = candidates[0]
    if best_score < 0.5:
        return None

    cleaned = [[(cell or '').strip() for cell in row] for row in best_rows]
    return cleaned


def main():
    doc = fitz.open(PDF_PATH)
    with open(IN_PATH, encoding='utf-8') as f:
        data = json.load(f)

    total = 0
    matched = 0

    for r in data:
        for att in r.get('attachments', []):
            total += 1
            if not att.get('start_page') or not att.get('end_page'):
                continue
            attachment_text = normalize_for_match(' '.join(att['lines']))
            rows = find_best_table(doc, att['start_page'], att['end_page'], attachment_text)
            if rows:
                att['rows'] = rows
                matched += 1

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'전체 첨부 {total}건 중 표 구조 매칭 {matched}건 -> {OUT_PATH}', file=sys.stderr)


if __name__ == '__main__':
    main()
