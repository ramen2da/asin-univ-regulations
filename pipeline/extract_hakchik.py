import sys
import os
import re
import json

import fitz
from kiwipiepy import Kiwi

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import parse_body, normalize_ws
from table_extract_common import find_table_bboxes, prose_lines_excluding_tables, extract_page_range_as_pdf

PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "학칙_260623개정(재입학개정 반영).pdf")
FORMS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "static", "forms")

CHAPTER_START_RE = re.compile(r"^제\s*(\d+)\s*장\s*$")
CHAPTER_INLINE_RE = re.compile(r"^제\s*(\d+)\s*장\s+(.+)$")
SECTION_START_RE = re.compile(r"^제\s*(\d+)\s*절\s*$")
ARTICLE_RE = re.compile(r"^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\(([^)]*)\))?")
ADDENDA_SOLO_RE = re.compile(r"^부$")
ADDENDA_SOLO2_RE = re.compile(r"^칙$")

# 1-indexed page numbers where find_tables() found a real table embedded in
# the running text (credit-hour / quota reference tables with no formal
# <별표>/[별표] marker of their own).
TABLE_PAGES = [11, 13, 14, 16, 28, 29]


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


def main():
    os.makedirs(FORMS_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)

    page_bboxes = {p: find_table_bboxes(doc[p - 1]) for p in TABLE_PAGES}

    raw_lines = []
    for i in range(len(doc)):
        page_no = i + 1
        if page_no in page_bboxes and page_bboxes[page_no]:
            lines = prose_lines_excluding_tables(doc[i], page_bboxes[page_no])
        else:
            lines = doc[i].get_text().split("\n")
        raw_lines.extend(lines)

    # The full 제정/개정 date history is printed as a standalone list of
    # "개정YYYY.MM.DD." lines injected mid-flow (right after the first
    # article, not as clean front matter like the main corpus) - pull every
    # such line out wherever it appears, in document order, and strip it from
    # the body text entirely.
    DATE_LINE_RE = re.compile(r"^(제정|개정)\s*([\d.]+)\.?$")
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

    # split off the title line before the first real structural line
    body_start = next(k for k, l in enumerate(merged) if is_structural(l.strip()))
    front = merged[:body_start]
    body_lines_plain = merged[body_start:]

    title = normalize_ws("".join(l.strip() for l in front if l.strip()))

    # parse_body needs (page_idx, line) tuples; page tracking isn't critical
    # here since we extract attachments separately by known page number.
    body_lines = [(0, l) for l in body_lines_plain]
    articles, addenda, _unused_attachments = parse_body(body_lines)

    kiwi = Kiwi()
    TIGHTEN_RE = re.compile(r"(제\s*\d+)\s*(조|장|절|관|항|호)(\s*의)?\s*(\d+)?")

    def tighten(m):
        out = m.group(1).replace(" ", "") + m.group(2)
        if m.group(3):
            out += "의"
        if m.group(4):
            out += m.group(4)
        return out

    def fix(text):
        if not text:
            return text
        spaced = kiwi.space(text)
        return TIGHTEN_RE.sub(tighten, spaced)

    for a in articles:
        a["body"] = fix(a["body"])
        if a.get("title"):
            a["title"] = fix(a["title"])
    addenda = [fix(l) for l in addenda]

    # attachments: extract each table page as a standalone PDF
    attachments = []
    for idx, page_no in enumerate(TABLE_PAGES):
        fname = f"reg120_att{idx}.pdf"
        out_path = os.path.join(FORMS_DIR, fname)
        extract_page_range_as_pdf(PDF_PATH, page_no, page_no, out_path)
        attachments.append({
            "label": f"[별표] p.{page_no} (학점배당표/정원표 등)",
            "start_page": page_no,
            "end_page": page_no,
            "lines": [],
            "file_url": f"/forms/{fname}",
        })

    doc.close()

    record = {
        "seq": 120,
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
        "pdf_pages": list(range(1, len(fitz.open(PDF_PATH)) + 1)),
    }

    out_path = os.path.join(os.path.dirname(__file__), "output", "hakchik.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"parsed {len(articles)} articles, {len(addenda)} addenda lines, {len(attachments)} attachments", file=sys.stderr)
    print(f"title: {title}", file=sys.stderr)
    print(f"enact_date: {enact_date}, amend_dates count: {len(amend_dates)}", file=sys.stderr)


if __name__ == "__main__":
    main()
