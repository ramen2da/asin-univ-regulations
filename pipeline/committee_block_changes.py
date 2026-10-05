"""Turns one 신구조문대비표 block (the markdown body of a □/◉ regulation block
extracted from the committee archive) into article-level change records:
    {article_no, article_sub_no, article_title, old_body, new_body}

Handles the common markdown-table layout (현행규정 | 개정(안) | 비고). Rows
whose 현행 cell is 신설/empty mean the article is new; rows whose 개정 cell
is empty or says 삭제 mean it was removed. Cells are flattened to text
(<br>/<u>/** markup dropped). Anything that doesn't parse as a table is
returned as an empty list, so the caller can fall back to the snapshot diff.
"""
import re

ARTICLE_HEAD_RE = re.compile(r'제\s*(\d+)\s*조(?:\s*의\s*(\d+))?(?:\s*\(([^)]*)\))?')
TAG_RE = re.compile(r'<[^>]+>')
MD_DIVIDER_RE = re.compile(r'^\|?\s*:?-{2,}')


def _clean(cell):
    t = cell.replace('<br>', ' ').replace('<br/>', ' ')
    t = TAG_RE.sub('', t)
    t = t.replace('**', '').replace(' ', ' ')
    return re.sub(r'\s+', ' ', t).strip()


def _split_row(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]


def _article_key(text):
    m = ARTICLE_HEAD_RE.search(text or '')
    if not m:
        return None, None, None
    return m.group(1), m.group(2), (m.group(3) or '').strip() or None


def block_changes(block_text):
    rows = []
    for line in block_text.split('\n'):
        if not line.strip().startswith('|'):
            continue
        if MD_DIVIDER_RE.match(line.strip()):
            continue
        cells = _split_row(line)
        if len(cells) < 2:
            continue
        old_raw, new_raw = _clean(cells[0]), _clean(cells[1])
        if old_raw in ('현행규정', '현행학칙', '현 행') or new_raw in ('개 정 (안)', '개정(안)', '개정학칙', '개정 (안)'):
            continue
        if not old_raw and not new_raw:
            continue
        if old_raw in ('(신설)', '신설') or not old_raw:
            old_raw = ''
        if new_raw in ('삭제', '(삭제)') or not new_raw:
            new_raw = ''
        src = new_raw or old_raw
        no, sub_no, title = _article_key(src)
        if no is None:
            continue
        rows.append({
            'article_no': int(no),
            'article_sub_no': int(sub_no) if sub_no else None,
            'article_title': title,
            'old_body': old_raw or None,
            'new_body': new_raw or None,
        })
    return rows
