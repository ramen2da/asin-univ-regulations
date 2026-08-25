"""Shared helpers for pulling PDF-native tables that are embedded directly in a
regulation's body text (not marked with a formal [별표]/<별표> tag, so the
main pipeline never split them out as attachments) out of the flowing text
and rendering them as real inline <table> HTML instead - reused for both the
main 규정집 corpus and the standalone 학칙 PDF.
"""
import html
import fitz


def find_real_tables(page, min_rows=2, min_cols=2):
    """Returns the pymupdf Table objects on this page that pass the row/col
    threshold (not just their bboxes, so callers can also read cell data)."""
    tables = page.find_tables()
    return [t for t in tables.tables if t.row_count >= min_rows and t.col_count >= min_cols]


def table_to_html(table, source_url=None, css_class="inline-table"):
    rows = table.extract()
    parts = ['<div class="article-table-wrap">', f'<table class="{css_class}"><tbody>']
    for row in rows:
        parts.append("<tr>")
        for cell in row:
            text = html.escape(cell or "").replace("\n", "<br>")
            parts.append(f"<td>{text}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    if source_url:
        parts.append(f'<a class="table-src-link" href="{source_url}" target="_blank">원본 페이지 보기 (PDF)</a>')
    parts.append("</div>")
    return "".join(parts)


def prose_lines_excluding_tables(page, tables, pad=2, markers=None, anchor_overrides=None):
    """tables: list of pymupdf Table objects (from find_real_tables), used
    here only for their .bbox - NOT re-read via .extract() at this point.
    PyMuPDF Table objects go stale once the shared Document/Page cursor has
    moved on to other pages, silently returning a *different* page's cell
    data instead of raising - so any .extract() call must happen right when
    the table is found, never deferred. markers: pre-rendered HTML/text
    strings, one per table in the same order, computed eagerly by the
    caller at detection time; each is spliced in at that table's original
    reading-order position (based on PyMuPDF's block/line numbering).
    Defaults to a plain-text pointer per table if not given.

    anchor_overrides: optional list matching tables, each either None (use
    the natural reading-order position) or a substring. Some tables are
    printed as a boxed callout near the bottom of the page, physically
    below a chapter/section heading that has nothing to do with the
    table's actual subject - natural reading order would then splice the
    marker in *after* that heading, landing it in the gap between a
    flushed article and the next one, where parse_body's state machine
    silently drops it (current_article is None there). When given, the
    marker is instead spliced in directly after the last prose line
    containing that substring, regardless of the table's physical bbox."""
    if markers is None:
        markers = ["[표 - 별표 참조]"] * len(tables)
    if anchor_overrides is None:
        anchor_overrides = [None] * len(tables)

    def in_bbox(w, bbox):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        bx0, by0, bx1, by1 = bbox
        return bx0 - pad <= cx <= bx1 + pad and by0 - pad <= cy <= by1 + pad

    words = page.get_text("words")
    kept = {}
    dropped_keys_per_table = [[] for _ in tables]
    for w in words:
        key = (w[5], w[6])
        matched = False
        for idx, t in enumerate(tables):
            if in_bbox(w, t.bbox):
                dropped_keys_per_table[idx].append(key)
                matched = True
                break
        if not matched:
            kept.setdefault(key, []).append(w)

    entries = [(key, " ".join(w[4] for w in sorted(ws, key=lambda w: w[0]))) for key, ws in kept.items()]
    entries.sort(key=lambda e: e[0])

    for idx in range(len(tables)):
        dk = dropped_keys_per_table[idx]
        if not dk:
            continue
        substr = anchor_overrides[idx]
        if substr:
            insert_at = None
            for i, (_, text) in enumerate(entries):
                if substr in text:
                    insert_at = i + 1
            if insert_at is not None:
                entries.insert(insert_at, (entries[insert_at - 1][0], markers[idx]))
                continue
        marker_key = sorted(dk)[len(dk) // 2]
        lo, hi = 0, len(entries)
        while lo < hi:
            mid = (lo + hi) // 2
            if entries[mid][0] < marker_key:
                lo = mid + 1
            else:
                hi = mid
        entries.insert(lo, (marker_key, markers[idx]))

    return [text for _, text in entries]


def extract_page_range_as_pdf(src_doc_path, start_page, end_page, out_path):
    """start_page/end_page: 1-indexed, inclusive."""
    doc = fitz.open(src_doc_path)
    sub = fitz.open()
    sub.insert_pdf(doc, from_page=start_page - 1, to_page=end_page - 1)
    sub.save(out_path)
    sub.close()
    doc.close()
