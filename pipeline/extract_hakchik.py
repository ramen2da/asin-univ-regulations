import sys
import os
import re
import json

import fitz
from kiwipiepy import Kiwi

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import parse_body, normalize_ws
from table_extract_common import prose_lines_excluding_tables, extract_page_range_as_pdf

FORMS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "static", "forms")
CURRENT_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "학칙_260623개정(재입학개정 반영).pdf")

CHAPTER_START_RE = re.compile(r"^제\s*(\d+)\s*장\s*$")
CHAPTER_INLINE_RE = re.compile(r"^제\s*(\d+)\s*장\s+(.+)$")
SECTION_START_RE = re.compile(r"^제\s*(\d+)\s*절\s*$")
ARTICLE_RE = re.compile(r"^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\(([^)]*)\))?")
ADDENDA_SOLO_RE = re.compile(r"^부$")
ADDENDA_SOLO2_RE = re.compile(r"^칙$")
DATE_LINE_RE = re.compile(r"^(제정|개정)\s*([\d.]+)\.?$")
TIGHTEN_RE = re.compile(r"(제\s*\d+)\s*(조|장|절|관|항|호)(\s*의)?\s*(\d+)?")

_kiwi = None


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def _tighten(m):
    out = m.group(1).replace(" ", "") + m.group(2)
    if m.group(3):
        out += "의"
    if m.group(4):
        out += m.group(4)
    return out


def fix_spacing_ko(text):
    if not text:
        return text
    spaced = _get_kiwi().space(text)
    return TIGHTEN_RE.sub(_tighten, spaced)


def is_structural(line):
    return bool(
        ARTICLE_RE.match(line)
        or CHAPTER_START_RE.match(line)
        or CHAPTER_INLINE_RE.match(line)
        or SECTION_START_RE.match(line)
    )


def merge_fragmented_headers(lines):
    """제N 장 / 제N 절 headers often have their title spread across the next
    1-3 lines (short titles get letter-spaced/centered in the source PDF, one
    character per line). 부칙 markers are similarly split into a '부' line
    followed by a '칙' line, repeated once per historical amendment. Collapse
    both patterns into single synthesized lines matching the rest of the
    corpus's "제1장 총칙" / "부칙" convention."""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()

        if ADDENDA_SOLO_RE.match(line) and i + 1 < n and ADDENDA_SOLO2_RE.match(lines[i + 1].strip()):
            out.append("부칙")
            i += 2
            continue

        m = CHAPTER_START_RE.match(line)
        if m:
            frags = []
            j = i + 1
            while j < n and not is_structural(lines[j].strip()) and lines[j].strip():
                frags.append(lines[j].strip())
                j += 1
            out.append(f"제{m.group(1)}장 {''.join(frags)}")
            i = j
            continue

        m = CHAPTER_INLINE_RE.match(line)
        if m:
            out.append(f"제{m.group(1)}장 {m.group(2)}")
            i += 1
            continue

        m = SECTION_START_RE.match(line)
        if m:
            frags = []
            j = i + 1
            while j < n and not is_structural(lines[j].strip()) and lines[j].strip():
                frags.append(lines[j].strip())
                j += 1
            out.append(f"제{m.group(1)}절 {''.join(frags)}")
            i = j
            continue

        out.append(lines[i])
        i += 1
    return out


def extract_hakchik_pdf(pdf_path, seq=120, extract_attachments=False, forms_prefix="reg120_att"):
    """Parses a standalone 아신대학교 학칙 PDF edition into the same record
    shape as the main corpus. Table pages are auto-detected per edition
    (page numbers shift between editions as content is added/removed)."""
    doc = fitz.open(pdf_path)

    table_pages = []
    for i in range(len(doc)):
        # min_rows=1: this document's large credit-hour tables often split
        # into a 1-row header fragment plus a multi-row data block (the
        # header alone would otherwise fail the row>=2 check and leak
        # through as ungridded prose, corrupting whatever article follows).
        # But a loose 1-row/2-col threshold also catches this document's
        # letter-spaced chapter headings (each character centered as its own
        # "column") as false positives - a real 1-row data-table fragment
        # always has at least one numeric cell, a heading fragment never
        # does, so use that to tell them apart.
        page_i = doc[i]
        candidate_tables = page_i.find_tables()
        bboxes = []
        for t in candidate_tables.tables:
            if t.row_count >= 2 and t.col_count >= 2:
                bboxes.append(t.bbox)
            elif t.row_count == 1 and t.col_count >= 2:
                cells = t.extract()
                has_digit = any(c and re.search(r"\d", c) for row in cells for c in row)
                if has_digit:
                    bboxes.append(t.bbox)
        if bboxes:
            table_pages.append((i + 1, bboxes))

    raw_lines = []
    for i in range(len(doc)):
        page_no = i + 1
        bboxes = next((b for p, b in table_pages if p == page_no), None)
        if bboxes:
            lines = prose_lines_excluding_tables(doc[i], bboxes)
        else:
            lines = doc[i].get_text().split("\n")
        raw_lines.extend(lines)

    amend_dates = []
    enact_date = None
    remaining_lines = []
    for l in raw_lines:
        s = l.strip()
        m = DATE_LINE_RE.match(s)
        if m:
            d = m.group(2).rstrip(".")
            amend_dates.append(d)
            if m.group(1) == "제정" and enact_date is None:
                enact_date = d
            continue
        remaining_lines.append(l)

    merged = merge_fragmented_headers(remaining_lines)

    body_start = next(k for k, l in enumerate(merged) if is_structural(l.strip()))
    front = merged[:body_start]
    body_lines_plain = merged[body_start:]

    title = normalize_ws("".join(l.strip() for l in front if l.strip()))

    body_lines = [(0, l) for l in body_lines_plain]
    articles, addenda, _unused = parse_body(body_lines)

    for a in articles:
        a["body"] = fix_spacing_ko(a["body"])
        if a.get("title"):
            a["title"] = fix_spacing_ko(a["title"])
    addenda = [fix_spacing_ko(l) for l in addenda]

    attachments = []
    if extract_attachments:
        os.makedirs(FORMS_DIR, exist_ok=True)
        for idx, (page_no, _bboxes) in enumerate(table_pages):
            fname = f"{forms_prefix}{idx}.pdf"
            out_path = os.path.join(FORMS_DIR, fname)
            extract_page_range_as_pdf(pdf_path, page_no, page_no, out_path)
            attachments.append({
                "label": f"[별표] p.{page_no} (학점배당표/정원표 등)",
                "start_page": page_no,
                "end_page": page_no,
                "lines": [],
                "file_url": f"/forms/{fname}",
            })

    n_pages = len(doc)
    doc.close()

    return {
        "seq": seq,
        "l0": "학사",
        "l1": None,
        "index_no": "1",
        "toc_title": "아신대학교 학칙",
        "parsed_title": title,
        "enact_date": enact_date,
        "amend_dates": amend_dates,
        "article_count": len(articles),
        "articles": articles,
        "addenda": addenda,
        "attachments": attachments,
        "pdf_pages": list(range(1, n_pages + 1)),
        "table_pages": [p for p, _ in table_pages],
    }


def main():
    record = extract_hakchik_pdf(CURRENT_PDF_PATH, seq=120, extract_attachments=True)

    out_path = os.path.join(os.path.dirname(__file__), "output", "hakchik.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"parsed {len(record['articles'])} articles, {len(record['addenda'])} addenda lines, "
          f"{len(record['attachments'])} attachments", file=sys.stderr)
    print(f"title: {record['parsed_title']}", file=sys.stderr)
    print(f"enact_date: {record['enact_date']}, amend_dates count: {len(record['amend_dates'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
