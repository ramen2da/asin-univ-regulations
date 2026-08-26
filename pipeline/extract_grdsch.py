"""Parses the 20 대학원(Graduate School) regulations plus the 2 학부 regulations
(학생준칙, 학회설치 및 운영에 관한 규정) that turned out to be entirely absent
from the current system, extracted this session from the school's old website
file dump (file01-08.hwp, grdsch_hakchic*.hwp, grdsch_hacksa*.hwp, and the
std_junchic.pdf/std_install.pdf pair).

These come from kordoc's Markdown conversion of the source HWP/PDF files, not
from extract3.py's PDF pipeline, so they need their own light parser - but the
underlying 제N장/제N조/부칙 structure is the same, so this reuses
extract3.py's ARTICLE_RE/ADDENDA_RE/DATE_LINE_RE/normalize_ws directly. Only
the chapter/section/gwan regexes are redefined locally, loosened to accept
zero spaces before the title (some of these documents have "제2장입학" with
no space at all, which extract3.py's main-corpus regexes - tuned for a PDF
that's always spaced - would not match), and the attachment marker recognizes
both "[별표 1]" (main corpus convention) and "<별표 1>" (this batch's own
convention, same as the standalone 학칙 PDF earlier this session).
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import ARTICLE_RE, ADDENDA_RE, DATE_LINE_RE, normalize_ws

CHAPTER_RE = re.compile(r'^제\s*(\d+)\s*장\s*(.*)$')
SECTION_RE = re.compile(r'^제\s*(\d+)\s*절\s*(.*)$')
GWAN_RE = re.compile(r'^제\s*(\d+)\s*관\s*(.*)$')
ATTACHMENT_MARKER_RE = re.compile(r'^[\[<](별지서식|별표)[^\]>]*[\]>]')
MD_HEADING_RE = re.compile(r'^#{1,6}\s*')
TABLE_BLOCK_RE = re.compile(r'<table\b.*?</table>', re.DOTALL)

# A handful of the source HWP documents were laid out as a single borderless
# frame around the whole page - kordoc reads that as one big OUTER <table>
# whose one cell contains a second, INNER <table> that's the real per-
# chapter/article content, one row per paragraph. One of these documents
# also has real embedded data tables (credit-hour tables) nested a further
# level inside one of those paragraph cells, so naive non-greedy regex
# (<td>(.*?)</td>) grabs the *nested* table's first closing tag instead of
# the outer cell's own - silently truncating everything after it. Track
# <table> nesting depth explicitly instead, so only true top-level <tr>/
# <td> boundaries of the outer "layout" table are split on; content of any
# table nested inside a cell is left as opaque HTML for that cell to carry
# (flattened along with the rest of the cell's text, same tradeoff as the
# main corpus's occasional un-gridded in-body tables).
LAYOUT_WRAPPER_OPEN_RE = re.compile(r'^\s*<table>\s*<tr>\s*<th>\s*<table>\s*', re.IGNORECASE)


def _top_level_segments(content, tag_pattern):
    """Splits content into the inner text of each top-level <tag>...</tag>
    span matching tag_pattern (e.g. "tr", or "td|th"), skipping any such
    tag found inside a nested <table> rather than matching its first,
    wrong, closing tag."""
    segments = []
    table_depth = 0
    seg_start = None
    tag_re = re.compile(rf'<(/?)({tag_pattern}|table)\b[^>]*>', re.IGNORECASE)
    for m in tag_re.finditer(content):
        name = m.group(2).lower()
        closing = bool(m.group(1))
        if name == 'table':
            table_depth += -1 if closing else 1
            continue
        if table_depth > 0:
            continue
        if not closing:
            seg_start = m.end()
        elif seg_start is not None:
            segments.append(content[seg_start:m.start()])
            seg_start = None
    return segments


def _unwrap_layout_table(raw):
    raw = raw.strip()
    m = LAYOUT_WRAPPER_OPEN_RE.match(raw)
    if not m:
        return None
    inner = raw[m.end():]
    # inner now runs to the matching close of the *inner* <table>, followed
    # by the outer wrapper's own closing tags and nothing else - trim the
    # trailing "</table></th></tr></table>" (in whatever exact spacing).
    inner = re.sub(r'\s*</table>\s*</th>\s*</tr>\s*</table>\s*$', '', inner, flags=re.IGNORECASE)

    lines = []
    for row in _top_level_segments(inner, 'tr'):
        for cell in _top_level_segments(row, 'td|th'):
            text = cell.replace('<br>', '\n').replace('<br/>', '\n')
            text = re.sub(r'<[^>]+>', ' ', text)  # flatten any nested table's own tags
            for piece in text.split('\n'):
                piece = html.unescape(piece).strip()
                if piece:
                    lines.append(piece)
    return lines


def load_kordoc_markdown(md_path):
    """Reads a kordoc Markdown conversion into a flat list of non-empty lines,
    with heading markers stripped (kordoc's heading level tracks the source
    HWP's font styling, not semantic structure - plenty of articles get
    promoted to a heading level here, so parsing must key off the actual
    제N조/제N장 text, never off '#' vs '##' vs '###')."""
    with open(md_path, encoding='utf-8') as f:
        raw = f.read()

    unwrapped = _unwrap_layout_table(raw)
    if unwrapped is not None:
        return unwrapped

    # A <table>...</table> block is often kordoc's own multi-line HTML, and
    # splitting the raw text on '\n' first would shred it - protect each
    # block as a single already-line-ified unit before the line split.
    stash = []

    def _stash(m):
        # kordoc emits a bare <table>, with none of the site's own styling
        # hooks - tag and wrap it the same way the main corpus's own
        # in-body-table extraction does (table_extract_common.table_to_html),
        # so it picks up the existing .inline-table CSS (borders, cell
        # padding) and the wrapper's horizontal scroll for wide tables,
        # instead of rendering as bare unstyled HTML.
        tagged = re.sub(r'^<table\b', '<table class="inline-table"', m.group(0), count=1, flags=re.IGNORECASE)
        stash.append(f'<div class="article-table-wrap">{tagged}</div>')
        return f'@@TABLE{len(stash) - 1}@@'

    masked = TABLE_BLOCK_RE.sub(_stash, raw)
    lines = []
    for line in masked.split('\n'):
        s = MD_HEADING_RE.sub('', line).strip()
        if not s:
            continue
        m = re.fullmatch(r'@@TABLE(\d+)@@', s)
        if m:
            s = stash[int(m.group(1))]
        lines.append(s)
    return lines


def split_addenda(addenda_lines):
    """Same shape as extract3.split_addenda, but recognizing both
    "[별표 N]" and "<별표 N>" attachment markers."""
    addenda = []
    attachments = []
    current = None

    for line in addenda_lines:
        s = line.strip()
        if ATTACHMENT_MARKER_RE.match(s):
            current = {'label': s, 'lines': []}
            attachments.append(current)
        elif current is not None:
            current['lines'].append(s)
        else:
            addenda.append(s)

    return addenda, attachments


def parse_body(lines):
    """lines: flat list of strings (no page tracking - these are short
    single-source documents, not a paginated PDF)."""
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

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if ADDENDA_RE.match(s):
            flush_article()
            in_addenda = True
            continue

        if in_addenda:
            addenda_lines.append(s)
            continue

        m = CHAPTER_RE.match(s)
        if m:
            flush_article()
            chapter = normalize_ws(f"제{m.group(1)}장 {m.group(2)}").strip()
            section = None
            gwan = None
            continue

        m = SECTION_RE.match(s)
        if m:
            flush_article()
            section = normalize_ws(f"제{m.group(1)}절 {m.group(2)}").strip()
            gwan = None
            continue

        m = GWAN_RE.match(s)
        if m:
            flush_article()
            gwan = normalize_ws(f"제{m.group(1)}관 {m.group(2)}").strip()
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
        # A line before the first 제1조 that isn't a chapter/section/gwan
        # header is front-matter (title repeated as its own paragraph,
        # enact/amend date lines already pulled out by the caller before
        # this function runs) - safe to drop, matching extract3.py's own
        # front-matter handling.

    flush_article()
    addenda, attachments = split_addenda(addenda_lines)
    return articles, addenda, attachments


def parse_regulation(md_path, title_hint=None):
    """Parses one kordoc-converted regulation into the same record shape
    used by regulations_final_clean.json. title_hint overrides the title
    line kordoc emitted (sometimes just repeats the filename-derived label,
    e.g. "1) 정 관", not the real title) - pass the confirmed real title."""
    lines = load_kordoc_markdown(md_path)

    amend_dates = []
    enact_date = None
    remaining = []
    for l in lines:
        m = DATE_LINE_RE.match(l.strip())
        if m:
            d = m.group(2).strip().rstrip('.')
            amend_dates.append(d)
            if m.group(1) == '제정' and enact_date is None:
                enact_date = d
            continue
        remaining.append(l)

    body_start = next(
        (i for i, l in enumerate(remaining) if CHAPTER_RE.match(l.strip()) or ARTICLE_RE.match(l.strip())),
        0,
    )
    front = remaining[:body_start]
    body_lines = remaining[body_start:]

    parsed_title = normalize_ws(''.join(l.strip() for l in front if l.strip()))
    # Strip a leading kordoc list-numbering artifact like "1) " / "3) " that
    # sometimes prefixes the title (kordoc read it off the source's own
    # outline numbering, not part of the regulation's actual name).
    parsed_title = re.sub(r'^\d+\)\s*', '', parsed_title)

    articles, addenda, attachments = parse_body(body_lines)

    # Several of these documents (unlike the main PDF corpus, and unlike the
    # standalone 학칙 PDF) have no dotted "제정 YYYY. MM. DD" front-matter
    # line at all - their only date record is the worded "YYYY년 MM월 DD일"
    # sentences inside 부칙 itself ("이 학칙은 1988년 3월 28일부터
    # 시행한다."). Fall back to pulling dates out of the addenda text when
    # the front-matter pass above found none, keeping first-seen order.
    if not amend_dates:
        # A few of these documents have no separate 부칙 section at all -
        # the enactment history is just the text of their own last article
        # (typically titled "시행"), e.g. "이 내규는 1996년 3월 1일부터
        # 시행한다. 이 개정내규는 1998년 3월 1일부터 시행한다. ...". Scan
        # article bodies too when addenda alone came up empty.
        seen = set()
        date_source = list(addenda) + [a['body'] for a in articles]
        for line in date_source:
            for y, mo, d in re.findall(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', line):
                dotted = f'{y}.{int(mo):02d}.{int(d):02d}'
                if dotted not in seen:
                    seen.add(dotted)
                    amend_dates.append(dotted)
        if amend_dates:
            enact_date = amend_dates[0]

    return {
        'toc_title': title_hint or parsed_title,
        'parsed_title': title_hint or parsed_title,
        'enact_date': enact_date,
        'amend_dates': amend_dates,
        'article_count': len(articles),
        'articles': articles,
        'addenda': addenda,
        'attachments': attachments,
    }
