import sys
import os
import json

import fitz

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import extract_pdf, FORCE_NEW_GROUP_AT, FORCE_CONTINUE_AT
from table_extract_common import find_table_bboxes, prose_lines_excluding_tables, extract_page_range_as_pdf

PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "규정집(2026.07.11).pdf")
FORMS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "static", "forms")

# 1-indexed page numbers where find_tables() found a real bordered/gridded
# table on a page that isn't already covered by a declared [별표]/[별지서식]
# attachment - these tables were getting flattened into unreadable inline
# text by plain get_text() (columns read top-to-bottom before rows).
TABLE_PAGES = [28, 190, 193, 195, 223, 224, 238, 241, 326, 431, 436, 440, 531, 532, 536, 549]


def main():
    os.makedirs(FORMS_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)

    page_bboxes = {}
    for page_no in TABLE_PAGES:
        page = doc[page_no - 1]
        bboxes = find_table_bboxes(page)
        page_bboxes[page_no] = bboxes

    doc.close()

    # rebuild the flat per-page text list, patching only the affected pages
    doc = fitz.open(PDF_PATH)
    pages_text = []
    for i in range(len(doc)):
        page_no = i + 1
        if page_no in page_bboxes:
            lines = prose_lines_excluding_tables(doc[i], page_bboxes[page_no])
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

    # now extract each table page as its own standalone attachment PDF and
    # record which regulation (by seq) it belongs to for the next step
    table_pdfs = []
    for page_no in TABLE_PAGES:
        # find which regulation this page falls under
        owner = next((r for r in results if page_no in r["pdf_pages"]), None)
        if owner is None:
            print(f"WARNING: page {page_no} not claimed by any regulation", file=sys.stderr)
            continue
        table_pdfs.append((page_no, owner["seq"], owner["parsed_title"] or owner["toc_title"]))

    with open(os.path.join(os.path.dirname(__file__), "output", "inbody_table_pages.json"), "w", encoding="utf-8") as f:
        json.dump(table_pdfs, f, ensure_ascii=False, indent=2)

    for page_no, seq, title in table_pdfs:
        print(f"page {page_no} -> seq {seq} ({title})", file=sys.stderr)


if __name__ == "__main__":
    main()
