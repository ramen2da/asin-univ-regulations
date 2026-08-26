"""Parses the 대학원 규정 batch discovered in file/학칙/대학원규정/ (2026-08-27):
a single unified 대학원 학칙 + 학사내규 that superseded the 6 separate
per-school 학칙/학사내규 documents added earlier this session (extract_grdsch.py's
batch, abolished 2018-12-14), plus several updated/new smaller regulations.

Reuses extract_grdsch.py's kordoc-markdown parsing machinery (chapter/section/
gwan regexes, table stashing, attachment splitting) and extract_hakchik.py's
addenda-line-merging + kiwi-based spacing correction (these PDFs wrap prose
across raw lines exactly like the standalone 학칙 PDF did, splitting mid-word
with no space at the break).

Two document-specific quirks not seen in either prior batch:
  - A chapter header split across two separate lines ("제 1" / "장총칙") in
    the 학사내규 conversion - merge_fragmented_chapter_lines() below re-joins it.
  - A handful of 부칙 markers rendered by kordoc as tiny 2-column Markdown
    tables ("|부|칙|") instead of a plain "부 칙" text line, seen once in
    전문상담교사 alongside one genuine Markdown data table (grade-scale tables
    in the 학칙) that DOES need to become a real <table> for the UI - both are
    handled by convert_md_tables() below, which tells them apart by checking
    whether the first row literally reads "부칙".
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract3 import ARTICLE_RE, ADDENDA_RE, DATE_LINE_RE, normalize_ws
from extract_grdsch import (
    CHAPTER_RE, SECTION_RE, GWAN_RE, ATTACHMENT_MARKER_RE,
    load_kordoc_markdown,
)
from extract_hakchik import fix_spacing_ko, ADDENDA_NEW_UNIT_RE

# extract_hakchik's ADDENDA_NEW_UNIT_RE was tuned for the standalone 학칙 PDF,
# whose attachment convention is "<서식 N호>" - this batch's 대학원 학칙 uses
# "<별지서식 N호>" instead, which that regex's "<서식|\[서식" alternative does
# not match (different word, not a substring match) - extend it locally
# rather than editing the shared main-corpus regex.
EXTRA_UNIT_RE = re.compile(r'^[<\[]별지서식')


def merge_addenda_lines(lines):
    units = []
    current = []
    prev_forces_new = False
    for l in lines:
        s = l.strip()
        if not s:
            continue
        starts_new = prev_forces_new or bool(ADDENDA_NEW_UNIT_RE.match(s)) or bool(EXTRA_UNIT_RE.match(s))
        if current and starts_new:
            units.append(' '.join(current))
            current = []
        current.append(s)
        prev_forces_new = '<table' in s or s == '부칙'
    if current:
        units.append(' '.join(current))
    return units

MD_ROW_RE = re.compile(r'^\s*\|(.+)\|\s*$')
MD_DIVIDER_CELL_RE = re.compile(r'^:?-{2,}:?$')
PAGE_NO_CELL_RE = re.compile(r'^-\s*\d+\s*-$')
BOLD_MARK_RE = re.compile(r'\*\*')

CHAPTER_FRAG_RE = re.compile(r'^제\s*\d*\s*$')

# kordoc's own Markdown rendering doubles up a nested/indented 호 list item's
# number as "1. N. " instead of just "N. " (its outer list-bullet numbering
# leaking in alongside the source document's own item number) - anchored to
# a leading "1." specifically so it never touches a genuine "YYYY. M." date
# fragment (which never starts with a bare "1").
DOUBLE_LIST_NUM_RE = re.compile(r'^1\.\s+(\d+\.\s)')

# Same kordoc quirk, different marker: a ①-⑳ 항 clause that starts a new
# Markdown list item gets a literal "- " bullet prefix (its own circled
# number is not Markdown syntax kordoc recognizes as a list marker).
DASH_HANG_RE = re.compile(r'^-\s*([①-⑳])')


def fix_doubled_list_numbers(lines):
    out = [DOUBLE_LIST_NUM_RE.sub(r'\1', l) for l in lines]
    return [DASH_HANG_RE.sub(r'\1', l) for l in out]


def _split_md_row(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]


def convert_md_tables(text):
    """Converts Markdown pipe-table blocks kordoc occasionally emits (instead
    of HTML <table>) into real <table> HTML - except a degenerate 부칙-as-
    table artifact, which becomes plain "부칙" + flattened text lines instead."""
    lines = text.split('\n')
    out = []
    i, n = 0, len(lines)
    while i < n:
        if MD_ROW_RE.match(lines[i]):
            block = []
            j = i
            while j < n and MD_ROW_RE.match(lines[j]):
                block.append(_split_md_row(lines[j]))
                j += 1
            has_divider = len(block) >= 2 and all(MD_DIVIDER_CELL_RE.match(c) for c in block[1] if c) and \
                all(MD_DIVIDER_CELL_RE.match(c) or not c for c in block[1])
            first_row_joined = ''.join(block[0])
            if re.fullmatch(r'부\s*칙', first_row_joined):
                out.append('부칙')
                for row in block[1:]:
                    cells = [c for c in row if c and not PAGE_NO_CELL_RE.match(c) and not MD_DIVIDER_CELL_RE.match(c)]
                    t = ' '.join(cells).strip()
                    if t:
                        out.append(t)
            else:
                header = block[0]
                body_rows = block[2:] if has_divider else block[1:]
                th = ''.join(f'<th>{html.escape(c)}</th>' for c in header)
                trs = [f'<tr>{th}</tr>']
                for row in body_rows:
                    tds = ''.join(f'<td>{html.escape(c)}</td>' for c in row)
                    trs.append(f'<tr>{tds}</tr>')
                out.append('<table class="inline-table">' + ''.join(trs) + '</table>')
            i = j
            continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)


def merge_fragmented_chapter_lines(lines):
    """'제 1' followed by '장총칙' (chapter header split across two kordoc
    lines) - re-join whenever concatenating the next 1-3 lines produces a
    line CHAPTER_RE/SECTION_RE/GWAN_RE actually matches."""
    out = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if CHAPTER_FRAG_RE.match(s):
            merged = s
            j = i + 1
            matched = None
            while j < n and j < i + 4:
                merged = merged + lines[j].strip()
                if CHAPTER_RE.match(merged) or SECTION_RE.match(merged) or GWAN_RE.match(merged):
                    matched = merged
                    j += 1
                    break
                j += 1
            if matched:
                out.append(matched)
                i = j
                continue
        out.append(s)
        i += 1
    return out


def parse_body(lines):
    """Same shape/contract as extract_grdsch.parse_body, but:
    - a 2nd+ 부칙 marker while already inside the addenda section is kept as
      its own "부칙" boundary line (extract_grdsch's version silently drops
      it, since its source batch never had more than one 부칙 block per doc)
    - article bodies and addenda both go through fix_spacing_ko (kiwi) to
      repair the mid-word line-wrap joins these PDF-sourced documents have
    """
    chapter = section = gwan = None
    articles = []
    addenda_lines = []
    current_article = None
    in_addenda = False

    def flush_article():
        nonlocal current_article
        if current_article is not None:
            raw = normalize_ws(' '.join(current_article['body_lines']))
            current_article['body'] = fix_spacing_ko(raw)
            if current_article['title']:
                current_article['title'] = fix_spacing_ko(current_article['title'])
            del current_article['body_lines']
            articles.append(current_article)
            current_article = None

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if ADDENDA_RE.match(s):
            flush_article()
            if in_addenda:
                addenda_lines.append('부칙')
            in_addenda = True
            continue

        if in_addenda:
            addenda_lines.append(s)
            continue

        m = CHAPTER_RE.match(s)
        if m:
            flush_article()
            chapter = normalize_ws(f"제{m.group(1)}장 {m.group(2)}").strip()
            section = gwan = None
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
                'chapter': chapter, 'section': section, 'gwan': gwan,
                'no': no, 'sub_no': sub_no, 'title': art_title,
                'body_lines': [s],
            }
            continue

        if current_article is not None:
            current_article['body_lines'].append(s)

    flush_article()

    units = merge_addenda_lines(addenda_lines)
    addenda, attachments = [], []
    current = None
    for u in units:
        u2 = fix_spacing_ko(u) if not u.startswith('<div class="article-table-wrap"') else u
        if u == '부칙':
            current = None
            addenda.append('부칙')
            continue
        if ATTACHMENT_MARKER_RE.match(u):
            current = {'label': u2, 'lines': []}
            attachments.append(current)
        elif current is not None:
            current['lines'].append(u2)
        else:
            addenda.append(u2)

    return articles, addenda, attachments


def parse_regulation(md_path, title_hint=None, preprocess_scratch_dir=None):
    with open(md_path, encoding='utf-8') as f:
        raw = f.read()
    raw = convert_md_tables(raw)
    raw = BOLD_MARK_RE.sub('', raw)
    # 장학금운영 시행세칙's kordoc conversion glued the final article's last
    # sentence directly onto the following 부칙 marker with no line break at
    # all ("...시 행한다.부칙") - ADDENDA_RE only matches "부칙" at a line
    # start, so split it back onto its own line wherever this exact artifact
    # occurs (narrow pattern: immediately after a "다." sentence end, since
    # that's the only place it happens - never mid-sentence).
    raw = re.sub(r'(다\.)부칙', r'\1\n부칙', raw)

    tmp_path = md_path
    if preprocess_scratch_dir:
        tmp_path = os.path.join(preprocess_scratch_dir, '_pre_' + os.path.basename(md_path))
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(raw)

    lines = load_kordoc_markdown(tmp_path)
    lines = merge_fragmented_chapter_lines(lines)
    lines = fix_doubled_list_numbers(lines)

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
    parsed_title = re.sub(r'^\d+\)\s*', '', parsed_title)

    articles, addenda, attachments = parse_body(body_lines)

    if not amend_dates:
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


def parse_regulation_plain(txt_path, title_hint):
    """For the smaller regulations extracted straight from PyMuPDF text (not
    via kordoc) - same 제N조/부칙 structure and same mid-word line-wrap-join
    problem, but no chapters/tables/attachments worth handling, and the
    front-matter is just the repeated title line (dropped automatically:
    parse_body ignores any line seen before the first 제N조 match)."""
    with open(txt_path, encoding='utf-8') as f:
        lines = f.read().split('\n')

    body_start = next(
        (i for i, l in enumerate(lines) if CHAPTER_RE.match(l.strip()) or ARTICLE_RE.match(l.strip())),
        0,
    )
    articles, addenda, attachments = parse_body(lines[body_start:])

    amend_dates = []
    seen = set()
    date_source = list(addenda) + [a['body'] for a in articles]
    for line in date_source:
        for y, mo, d in re.findall(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', line):
            dotted = f'{y}.{int(mo):02d}.{int(d):02d}'
            if dotted not in seen:
                seen.add(dotted)
                amend_dates.append(dotted)
    enact_date = amend_dates[0] if amend_dates else None

    return {
        'toc_title': title_hint,
        'parsed_title': title_hint,
        'enact_date': enact_date,
        'amend_dates': amend_dates,
        'article_count': len(articles),
        'articles': articles,
        'addenda': addenda,
        'attachments': attachments,
    }
