import sys
import os
import re
import json

import fitz
from kiwipiepy import Kiwi

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import parse_body, normalize_ws
from table_extract_common import table_to_html, prose_lines_excluding_tables, extract_page_range_as_pdf

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


TABLE_BLOCK_RE = re.compile(r'<div class="article-table-wrap">.*?</div>')


def fix_spacing_ko(text):
    if not text:
        return text
    # kiwi's space() only understands prose - fed an inline <table> block it
    # would happily insert/strip spaces inside tag names and attributes and
    # corrupt the markup, so pull any table block out before spacing and
    # splice the untouched HTML back in afterward.
    stash = []
    masked = TABLE_BLOCK_RE.sub(lambda m: stash.append(m.group(0)) or f"@@{len(stash) - 1}@@", text)
    spaced = _get_kiwi().space(masked)
    tightened = TIGHTEN_RE.sub(_tighten, spaced)
    # kiwi's spacer can itself insert a stray space inside the placeholder
    # (e.g. "@@0@@" -> "@@0 @@") since it has no notion of an opaque token -
    # tolerate optional whitespace around the index when restoring.
    return re.sub(r"@@\s*(\d+)\s*@@", lambda m: stash[int(m.group(1))], tightened)


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


def extract_hakchik_pdf(pdf_path, seq=120, extract_attachments=False, forms_prefix="hakchik_inbody_p"):
    """Parses a standalone 아신대학교 학칙 PDF edition into the same record
    shape as the main corpus. Table pages are auto-detected per edition
    (page numbers shift between editions as content is added/removed).
    Tables are always rendered as inline <table> HTML spliced into the
    article body (matching the main corpus - see fix_inbody_tables_main.py).
    extract_attachments controls only whether a per-page source PDF is
    written to disk and linked from the table ("원본 페이지 보기 (PDF)") -
    only worth doing for the current/live edition; historical editions
    used for revision-history diffing don't need a servable file, just the
    inline HTML for accurate old-vs-new body comparison."""
    doc = fitz.open(pdf_path)

    # Table objects must be read (table_to_html -> .extract()) immediately
    # here, in the same loop iteration that finds them - PyMuPDF Table
    # objects go stale once the Document/Page cursor moves to another page
    # and silently return a *different* page's cell data instead of
    # raising, so nothing here is deferred to a later pass over the pages.
    if extract_attachments:
        os.makedirs(FORMS_DIR, exist_ok=True)

    page_tables = {}
    page_markers = {}
    for i in range(len(doc)):
        page_i = doc[i]
        page_no = i + 1
        candidate_tables = page_i.find_tables()
        tables = []
        for t in candidate_tables.tables:
            if t.row_count >= 2 and t.col_count >= 2:
                tables.append(t)
            elif t.row_count == 1 and t.col_count >= 2:
                # min_rows=1: this document's large credit-hour tables often
                # split into a 1-row header fragment plus a multi-row data
                # block (the header alone would otherwise fail the row>=2
                # check and leak through as ungridded prose, corrupting
                # whatever article follows). But a loose 1-row/2-col
                # threshold also catches this document's letter-spaced
                # chapter headings (each character centered as its own
                # "column") as false positives - a real 1-row data-table
                # fragment always has at least one numeric cell, a heading
                # fragment never does, so use that to tell them apart.
                cells = t.extract()
                has_digit = any(c and re.search(r"\d", c) for row in cells for c in row)
                if has_digit:
                    tables.append(t)
        if tables:
            page_tables[page_no] = tables
            source_url = None
            if extract_attachments:
                fname = f"{forms_prefix}{page_no}.pdf"
                source_url = f"/forms/{fname}"
                extract_page_range_as_pdf(pdf_path, page_no, page_no, os.path.join(FORMS_DIR, fname))
            markers = [table_to_html(t, source_url=source_url) for t in tables]
            page_markers[page_no] = markers

    raw_lines = []
    for i in range(len(doc)):
        page_no = i + 1
        if page_no in page_tables:
            lines = prose_lines_excluding_tables(doc[i], page_tables[page_no], markers=page_markers[page_no])
        else:
            lines = doc[i].get_text().split("\n")
        raw_lines.extend(lines)

    # The 조기졸업(제54조) eligible-department table sits right at a page
    # break in at least one edition, so find_tables() (a per-page operation,
    # blind to page boundaries) sometimes splits it into two fragments: the
    # bulk of the rows on one page, plus the last row ("선교중국어학과 45")
    # stranded as its own 1-row table at the top of the next. Depending on
    # the edition, natural bbox-median reading order then scatters these
    # across different articles (article 50, mid-sentence inside article
    # 55-2, or correctly article 54) even though it's the same static table
    # every time - a pure extraction artifact, not a real regulatory
    # change. Pull any such fragment (identified by content, not position)
    # out of wherever it landed and append it to the end of article 54's
    # own text instead, in every edition, so revision-history diffing
    # doesn't see a false change. Anchored on the article-54 *header* line
    # rather than a phrase from its body text, since a phrase can be word-
    # wrapped across two separate reconstructed lines and fail a plain
    # substring match, while the header is always its own single line.
    def _is_special_marker(line):
        return "<table" in line and ("본 전공만 이수" in line or ("선교중국어학과" in line and line.count("<tr>") == 1))

    specials = [l for l in raw_lines if _is_special_marker(l)]
    if specials:
        raw_lines = [l for l in raw_lines if not _is_special_marker(l)]
        start_idx = next(
            (i for i, l in enumerate(raw_lines) if (m := ARTICLE_RE.match(l.strip())) and m.group(1) == "54" and not m.group(2)),
            None,
        )
        if start_idx is not None:
            end_idx = next(
                (j for j in range(start_idx + 1, len(raw_lines)) if is_structural(raw_lines[j].strip())),
                len(raw_lines),
            )
            raw_lines[end_idx:end_idx] = specials

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
        "attachments": [],
        "pdf_pages": list(range(1, n_pages + 1)),
        "table_pages": sorted(page_tables.keys()),
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
