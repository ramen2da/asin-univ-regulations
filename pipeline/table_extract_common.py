"""Shared helpers for pulling PDF-native tables that are embedded directly in a
regulation's body text (not marked with a formal [별표]/<별표> tag, so the
main pipeline never split them out as attachments) out of the flowing text
and into standalone PDF attachments instead - reused for both the main
규정집 corpus and the standalone 학칙 PDF.
"""
import fitz


def find_table_bboxes(page, min_rows=2, min_cols=2):
    tables = page.find_tables()
    return [t.bbox for t in tables.tables if t.row_count >= min_rows and t.col_count >= min_cols]


def prose_lines_excluding_tables(page, bboxes, pad=2, marker="[표 - 별표 참조]"):
    """Returns a list of text lines for the page with any word inside a table
    bbox removed, and a single marker line spliced in at the table's original
    reading-order position (based on PyMuPDF's block/line numbering) so
    readers know a table used to be there."""
    words = page.get_text("words")

    def in_table(w):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        for bx0, by0, bx1, by1 in bboxes:
            if bx0 - pad <= cx <= bx1 + pad and by0 - pad <= cy <= by1 + pad:
                return True
        return False

    kept = {}
    dropped_keys = []
    for w in words:
        key = (w[5], w[6])
        if in_table(w):
            dropped_keys.append(key)
        else:
            kept.setdefault(key, []).append(w)

    entries = [(key, " ".join(w[4] for w in sorted(ws, key=lambda w: w[0]))) for key, ws in kept.items()]

    if bboxes and dropped_keys:
        marker_key = sorted(dropped_keys)[len(dropped_keys) // 2]
        entries.append((marker_key, marker))

    entries.sort(key=lambda e: e[0])
    return [text for _, text in entries]


def extract_page_range_as_pdf(src_doc_path, start_page, end_page, out_path):
    """start_page/end_page: 1-indexed, inclusive."""
    doc = fitz.open(src_doc_path)
    sub = fitz.open()
    sub.insert_pdf(doc, from_page=start_page - 1, to_page=end_page - 1)
    sub.save(out_path)
    sub.close()
    doc.close()
