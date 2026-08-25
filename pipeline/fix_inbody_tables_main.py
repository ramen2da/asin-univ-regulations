import sys
import os
import json

import fitz

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import FORCE_NEW_GROUP_AT, FORCE_CONTINUE_AT
from table_extract_common import find_real_tables, prose_lines_excluding_tables, table_to_html, extract_page_range_as_pdf

PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "규정집(2026.07.11).pdf")
FORMS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "static", "forms")

# 1-indexed page numbers where find_tables() found a real bordered/gridded
# table on a page that isn't already covered by a declared [별표]/[별지서식]
# attachment - these tables were getting flattened into unreadable inline
# text by plain get_text() (columns read top-to-bottom before rows).
TABLE_PAGES = [28, 190, 193, 195, 223, 224, 238, 241, 326, 431, 436, 440, 531, 532, 536, 549]

# page 549's refund-schedule table is boxed near the bottom of the page,
# physically below the "제4장" chapter heading even though its content is
# 제12조(수업료 반환)'s refund amounts - natural reading order would splice
# it in after that heading, landing it in the dead zone between a flushed
# article and the next one, where parse_body silently drops it. Anchor it
# to the end of article 12's own text instead.
ANCHOR_OVERRIDES = {
    549: ["해외송금 환불 시 발생되는"],
}


def main():
    os.makedirs(FORMS_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)

    # Filenames are keyed by page number (unique within this source PDF), not
    # by owning regulation - which regulation a page belongs to is only
    # known *after* group_regulations runs below. table.extract() has to
    # happen right here too (see table_extract_common's docstring on why),
    # so both the PDF file and the HTML are built eagerly per page, before
    # moving on to any other page.
    page_tables = {}
    page_markers = {}
    for page_no in TABLE_PAGES:
        tables = find_real_tables(doc[page_no - 1])
        if tables:
            page_tables[page_no] = tables
            fname = f"inbody_p{page_no}.pdf"
            url = f"/forms/{fname}"
            page_markers[page_no] = [table_to_html(t, source_url=url) for t in tables]
            extract_page_range_as_pdf(PDF_PATH, page_no, page_no, os.path.join(FORMS_DIR, fname))

    pages_text = []
    for i in range(len(doc)):
        page_no = i + 1
        if page_no in page_tables:
            anchors = ANCHOR_OVERRIDES.get(page_no, [None] * len(page_tables[page_no]))
            lines = prose_lines_excluding_tables(
                doc[i], page_tables[page_no], markers=page_markers[page_no], anchor_overrides=anchors
            )
            pages_text.append("\n".join(lines))
        else:
            pages_text.append(doc[i].get_text())
    doc.close()

    # extract_pdf() opens its own doc and calls get_text() internally, so
    # re-implement its page-list construction here with our patched text
    # substituted in for the affected pages.
    import extract3
    from toc import parse_toc, TOC_PAGE_RANGE

    real_doc = fitz.open(PDF_PATH)

    toc_entries = parse_toc(real_doc)
    pages_for_grouping = list(pages_text)
    for i in TOC_PAGE_RANGE:
        pages_for_grouping[i] = ""
    groups = extract3.group_regulations(pages_for_grouping, FORCE_NEW_GROUP_AT, FORCE_CONTINUE_AT)

    n = min(len(toc_entries), len(groups))
    results = []
    for i in range(n):
        toc_e = toc_entries[i]
        g = groups[i]
        lines = extract3.clean_content_lines(g)
        title, enact_date, amend_dates, body_lines = extract3.parse_front_matter(lines)
        articles, addenda, attachments = extract3.parse_body(body_lines)
        results.append({
            "seq": i + 1,
            "l0": toc_e["l0"],
            "l1": toc_e["l1"],
            "index_no": g["index_no"],
            "toc_title": toc_e["title"],
            "parsed_title": title,
            "enact_date": enact_date,
            "amend_dates": amend_dates,
            "article_count": len(articles),
            "articles": articles,
            "addenda": addenda,
            "attachments": attachments,
            "pdf_pages": [p[0] + 1 for p in g["pages"]],
        })
    real_doc.close()

    print(f"TOC {len(toc_entries)} / groups {len(groups)} / results {len(results)}", file=sys.stderr)

    out_path = os.path.join(os.path.dirname(__file__), "output", "regulations_patched.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"wrote {out_path}", file=sys.stderr)

    for page_no in TABLE_PAGES:
        owner = next((r for r in results if page_no in r["pdf_pages"]), None)
        label = f"{owner['seq']} ({owner['parsed_title'] or owner['toc_title']})" if owner else "UNCLAIMED"
        print(f"page {page_no} -> seq {label}", file=sys.stderr)


if __name__ == "__main__":
    main()
