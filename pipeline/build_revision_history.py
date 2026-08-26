import sys
import os
import re
import json
import glob
import sqlite3
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(__file__))
from fix_spacing import collect_stats, find_candidates, apply_fix

HIST_DIR = os.path.join(os.path.dirname(__file__), 'output', 'history')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'regulations.db')


def normalize_title(t):
    return re.sub(r'[\s·․,()]', '', t or '')


# These two regulations' front-matter text glues in a predecessor regulation's
# name/history notes ahead of the real title (see load_data.py TITLE_OVERRIDES,
# a pre-existing quirk in the source PDF's front matter present in every
# edition, not something specific to one snapshot).
HISTORICAL_TITLE_OVERRIDES = [
    (re.compile('강사임용.*관한\\s*규정'), '강사임용 등에 관한 규정'),
    (re.compile('세계지역연구소\\s*운영규정'), '세계지역연구소 운영규정'),
]


def resolve_title(raw_title):
    for pattern, resolved in HISTORICAL_TITLE_OVERRIDES:
        if pattern.search(raw_title or ''):
            return resolved
    return raw_title


def load_snapshots():
    files = sorted(glob.glob(os.path.join(HIST_DIR, '*.json')))
    files = [f for f in files if not os.path.basename(f).startswith('_')]
    snapshots = []
    for f in files:
        with open(f, encoding='utf-8') as fh:
            snapshots.append(json.load(fh))
    return snapshots


def fix_all_bodies(snapshots):
    all_regs_for_stats = []
    for snap in snapshots:
        all_regs_for_stats.extend(snap['regulations'])
    joined_freq, split_freq = collect_stats(all_regs_for_stats)
    candidates = find_candidates(joined_freq, split_freq)
    counters = Counter()

    def fix(body):
        b = body
        for _ in range(4):
            nb = apply_fix(b, candidates, counters)
            if nb == b:
                break
            b = nb
        return b

    for snap in snapshots:
        for reg in snap['regulations']:
            for a in reg['articles']:
                a['body'] = fix(a['body'])

    print(f'spacing-fix candidates: {len(candidates)}', file=sys.stderr)
    return snapshots


TAG_RE = re.compile(r'\(([^()]*?(?:개정|신설|삭제|폐지)[^()]*?)\)')
DATE_RE = re.compile(r'\d{4}\.\s?\d{1,2}\.\s?\d{1,2}')


def extract_tag_dates(body):
    dates = set()
    for tag_match in TAG_RE.finditer(body or ''):
        inner = tag_match.group(1)
        for dm in DATE_RE.finditer(inner):
            d = re.sub(r'\s+', '', dm.group(0)).rstrip('.')
            y, mo, da = d.split('.')
            dates.add(f'{int(y):04d}.{int(mo):02d}.{int(da):02d}')
    return dates


ZERO_WIDTH_CHARS = '​‌‍﻿'
# Private-Use-Area codepoints (U+E000-U+F8FF): this corpus's PDFs embed custom
# font subsets where decorative brackets/symbols land on different PUA
# codepoints between editions despite rendering identically - not real content.
PUA_RE = re.compile('[-]')
# Interpunct-style list-separator dots (e.g. '위조․변조 및 훼손') - this 
# session's legacy HWP batch (file10-77/univ_XX snapshots) consistently 
# uses U+2024 ONE DOT LEADER where the current PDF corpus uses U+00B7 
# MIDDLE DOT for the exact same separator; same rendered glyph and 
# meaning, so treat as noise like the PUA case above, not real content.
INTERPUNCT_RE = re.compile('[․·‧・]')


def strip_for_noise_check(s):
    # "[표 - 별표 참조]" markers stand in for an excluded in-body table; their
    # exact position (which nearby article picks it up) is placed at the
    # median of the dropped table words' reading order, which can shift
    # between editions even when neither the table nor the article text
    # actually changed - not a real content difference, so ignore it here.
    s = (s or '').replace('[표 - 별표 참조]', '')
    s = re.sub(f'[\\s{ZERO_WIDTH_CHARS}]+', '', s)
    s = PUA_RE.sub('', s)
    s = INTERPUNCT_RE.sub('', s)
    s = re.sub(r'\.{1,}', '.', s)
    return s


def resolve_change_date(old_body, new_body, fallback_date):
    old_dates = extract_tag_dates(old_body)
    new_dates = extract_tag_dates(new_body)
    new_only = sorted(new_dates - old_dates)
    if len(new_only) == 1:
        return new_only[0], 'tag'
    if len(new_only) > 1:
        # Multiple amendment dates appeared between the two snapshots we have -
        # several real amendments happened in a gap our snapshots don't cover.
        # The latest tagged date is the most defensible single point to record.
        return new_only[-1], 'tag-multi'
    return fallback_date.replace('-', '.'), 'fallback'


def build_timeline(snapshots, title_to_id):
    timeline = defaultdict(list)
    for snap in snapshots:
        d = snap['date']
        seen_regids_this_snapshot = set()
        for reg in snap['regulations']:
            if reg['article_count'] == 0:
                continue
            key = normalize_title(resolve_title(reg['title']))
            regid = title_to_id.get(key)
            if regid is None or regid in seen_regids_this_snapshot:
                continue
            seen_regids_this_snapshot.add(regid)
            body_map = {(a['no'], a['sub_no']): a['body'] for a in reg['articles']}
            timeline[regid].append((d, body_map))
    return timeline


def article_label(no, sub_no, titles_by_key):
    t = titles_by_key.get((no, sub_no))
    base = f'제{no}조' + (f'의{sub_no}' if sub_no else '')
    return f'{base}({t})' if t else base


ARTICLE_OWN_TITLE_RE = re.compile(r'^제\s*\d+\s*조(?:\s*의\s*\d+)?\s*\(([^)]*)\)')


def _article_own_title(body):
    m = ARTICLE_OWN_TITLE_RE.match((body or '').strip())
    return m.group(1).strip() if m else None


def _titles_conflict(old_body, new_body):
    """True when the two bodies' own "제N조(제목)" headers name completely
    different topics. A handful of these older regulations (found via this
    session's legacy HWP batch, which reaches back to a 2012 snapshot) were
    restructured heavily enough between then and now that articles got
    inserted/removed and everything after shifted - comparing "article 8"
    in each snapshot then silently compares two unrelated provisions that
    only happen to share a number. A genuine amendment to an existing
    article essentially never renames what the article is about (the title
    is closer to the provision's fixed name; amendments touch its body) -
    a title come out totally different is a much stronger signal of
    renumbering than of a real edit, so this is checked only for
    'fallback'-dated changes (no amendment-tag evidence either way)."""
    old_t, new_t = _article_own_title(old_body), _article_own_title(new_body)
    if not old_t or not new_t:
        return False
    old_t, new_t = old_t.strip(), new_t.strip()
    if old_t == new_t:
        return False
    return old_t not in new_t and new_t not in old_t


def diff_regulation_timeline(regid, entries, current_body_map, current_date, titles_by_key):
    """entries: sorted list of (date, body_map) from historical snapshots (oldest
    first). Appends the live current state as the final point, then walks
    consecutive pairs looking for per-article text changes."""
    full = list(entries) + [(current_date, current_body_map)]

    changes_by_date = defaultdict(list)
    retitled_skipped = 0
    all_keys = set()
    for _, bm in full:
        all_keys.update(bm.keys())

    for key in all_keys:
        no, sub_no = key
        prev_body = None
        prev_present = False
        for d, bm in full:
            body = bm.get(key)
            present = body is not None
            if prev_present and present and body != prev_body:
                if strip_for_noise_check(prev_body) == strip_for_noise_check(body):
                    prev_body = body if present else prev_body
                    prev_present = prev_present or present
                    continue
                date, method = resolve_change_date(prev_body, body, d)
                if method == 'fallback' and _titles_conflict(prev_body, body):
                    retitled_skipped += 1
                    prev_body = body if present else prev_body
                    prev_present = prev_present or present
                    continue
                changes_by_date[date].append({
                    'article_no': int(no),
                    'article_sub_no': int(sub_no) if sub_no else None,
                    'article_title': titles_by_key.get(key),
                    'old_body': prev_body,
                    'new_body': body,
                    'method': method,
                    'observed_at_snapshot': d,
                })
            elif prev_present and not present:
                pass  # article removed - not modeled in this pass
            elif not prev_present and present and prev_body is None and d != full[0][0]:
                pass  # newly added article - not modeled in this pass
            prev_body = body if present else prev_body
            prev_present = prev_present or present
    return changes_by_date, retitled_skipped


# Manually reviewed after inspecting every non-tag-dated ("fallback") change:
# these are confirmed extraction artifacts, not real amendments, and are
# dropped rather than inserted as history. Keyed by (regulation_id, observed
# snapshot date, article_no, article_sub_no).
EXCLUDE_FALLBACK = {
    (1, '2026-06-23', 74, None),  # trailing "." after a date in a long tag list, nothing else differs
    (1, '2026-06-23', 72, None),  # an existing "(개정 2025.8.6.)" tag vanished - unexplained, not trustworthy
    (27, '2023-12-14', 88, None),  # "항신설" -> "개정" label swap for the same already-known date
    (85, '2023-04-28', 5, None),  # the regulation's own front-matter date history got injected mid-sentence
    (103, '2023-02-09', 5, None),  # 예비군중대운영규정 제5조's own "편제표" table renders as flattened
                                    # plain text in one PDF edition's extraction and a proper <table> in
                                    # the next - same table, just an extraction-quality difference between
                                    # two editions' own PDF renders, not a real amendment (found while
                                    # sampling this session's newly-added legacy-HWP-batch changes, but
                                    # this specific pair is between two of the original 18 PDF editions,
                                    # unrelated to that batch).
}

# For these the naive "date we first observed the change" is wrong; the
# regulation's own front-matter amendment history names the real date.
DATE_OVERRIDES = {
    (2, '2026.06.23'): '2026.05.26',
}


def main():
    snapshots = load_snapshots()
    snapshots = fix_all_bodies(snapshots)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    regs = conn.execute('SELECT id, title FROM regulations').fetchall()
    title_to_id = {normalize_title(r['title']): r['id'] for r in regs}

    articles = conn.execute('SELECT id, regulation_id, no, sub_no, title, body FROM articles').fetchall()
    current_by_reg = defaultdict(dict)
    titles_by_reg_key = defaultdict(dict)
    for a in articles:
        key = (a['no'], a['sub_no'])
        current_by_reg[a['regulation_id']][key] = a['body']
        titles_by_reg_key[a['regulation_id']][key] = a['title']

    existing_amend_dates = defaultdict(set)
    for row in conn.execute('SELECT regulation_id, amend_date FROM amendments'):
        existing_amend_dates[row['regulation_id']].add(row['amend_date'])
    conn.close()

    timeline = build_timeline(snapshots, title_to_id)

    today = snapshots[-1]['date']
    final = defaultdict(lambda: defaultdict(list))  # regid -> date -> [changes]
    dropped = 0
    retitled_total = 0

    for regid, entries in timeline.items():
        entries_sorted = sorted(entries, key=lambda x: x[0])
        changes, retitled = diff_regulation_timeline(
            regid, entries_sorted, current_by_reg.get(regid, {}), today, titles_by_reg_key.get(regid, {})
        )
        retitled_total += retitled
        for date, items in changes.items():
            for it in items:
                excl_key = (regid, it['observed_at_snapshot'], it['article_no'], it['article_sub_no'])
                if it['method'] == 'fallback' and excl_key in EXCLUDE_FALLBACK:
                    dropped += 1
                    continue
                final_date = DATE_OVERRIDES.get((regid, date), date)
                final[regid][final_date].append(it)

    total_changes = sum(len(items) for by_date in final.values() for items in by_date.values())
    print(f'regulations with confirmed historical changes: {len(final)}', file=sys.stderr)
    print(
        f'total article-change events to insert: {total_changes} '
        f'(dropped as noise: {dropped}, dropped as likely renumbering/title-mismatch: {retitled_total})',
        file=sys.stderr,
    )

    with open(os.path.join(os.path.dirname(__file__), 'output', 'revision_history_report.json'), 'w', encoding='utf-8') as f:
        json.dump({str(k): v for k, v in final.items()}, f, ensure_ascii=False, indent=2)

    # --- insert into DB ---
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    created_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

    revisions_created = 0
    changes_created = 0
    amendments_created = 0

    for regid, by_date in final.items():
        for date in sorted(by_date.keys()):
            items = by_date[date]
            cur.execute(
                'INSERT INTO revisions (regulation_id, revised_at, summary, created_at) VALUES (?, ?, ?, ?)',
                (regid, date, '과거 규정집 PDF 대조로 자동 확인된 개정 이력', created_at),
            )
            revision_id = cur.lastrowid
            revisions_created += 1
            for ordinal, it in enumerate(items):
                cur.execute(
                    '''INSERT INTO revision_changes
                       (revision_id, article_no, article_sub_no, article_title, old_body, new_body, ordinal)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (revision_id, it['article_no'], it['article_sub_no'], it['article_title'],
                     it['old_body'], it['new_body'], ordinal),
                )
                changes_created += 1

            if date not in existing_amend_dates[regid]:
                max_ord = cur.execute(
                    'SELECT COALESCE(MAX(ordinal), -1) FROM amendments WHERE regulation_id=?', (regid,)
                ).fetchone()[0]
                cur.execute(
                    'INSERT INTO amendments (regulation_id, amend_date, ordinal) VALUES (?, ?, ?)',
                    (regid, date, max_ord + 1),
                )
                existing_amend_dates[regid].add(date)
                amendments_created += 1

    conn.commit()
    conn.close()

    print(f'inserted: {revisions_created} revisions, {changes_created} revision_changes, {amendments_created} new amendment dates', file=sys.stderr)


if __name__ == '__main__':
    main()
