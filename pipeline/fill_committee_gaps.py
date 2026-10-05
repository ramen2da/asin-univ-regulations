"""Fills the revision-history gaps found by crosscheck_committee.py: for each
committee 신구대조표 record that has parsed article changes and no revision
of its regulation in the window after its meeting, adds a revision dated at
the first 규정집 edition published on or after the meeting (the same date
basis the snapshot diff uses), and appends it to the portable seed so
load_revision_history.py reproduces it on deploy.
"""
import glob
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

OUT = r'C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad\crosscheck_out.json'
HIST = os.path.join(os.path.dirname(__file__), 'output', 'history')
SEED = os.path.join(os.path.dirname(__file__), 'output', 'revision_history_seed.json')
SUMMARY = '위원회 신구조문대비표 대조로 확인된 개정 이력'


ELIDED_RE = re.compile(r'\(생략\)|\(현행과 같음\)|\(현행과 동일\)|\(현행과같음\)|\(변동\s*(없음|사항 없음)\)|\(현행\s*과\s*같음\)|\~|\(항 삭제\)|\(호 삭제\)')


def is_full_text(c):
    if not c['old_body'] or not c['new_body']:
        return False
    return not (ELIDED_RE.search(c['old_body']) or ELIDED_RE.search(c['new_body']))


def edition_dates():
    ds = []
    for f in glob.glob(os.path.join(HIST, '*.json')):
        b = os.path.basename(f)
        if b.startswith(('_', 'legacy')):
            continue
        y, m, d = b[:-5].split('-')
        ds.append(date(int(y), int(m), int(d)))
    return sorted(ds)


def main():
    results = json.load(open(OUT, encoding='utf-8'))
    editions = edition_dates()
    seed = json.load(open(SEED, encoding='utf-8'))
    existing = {(e['regulation_seq'], e['revised_at']) for e in seed}

    added = 0
    for r in results:
        if r['status'] != 'gap' or not r['changes']:
            continue
        s = r['session']
        sd = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        nxt = [e for e in editions if e >= sd]
        if not nxt:
            continue
        ed = nxt[0]
        if (ed - sd).days > 275:
            continue
        rev_date = f'{ed.year:04d}.{ed.month:02d}.{ed.day:02d}'
        key = (r['reg_id'], rev_date)
        if key in existing:
            continue
        full = [c for c in r['changes'] if is_full_text(c)]
        if not full:
            continue
        changes = []
        for i, c in enumerate(full):
            changes.append({
                'article_no': c['article_no'],
                'article_sub_no': c['article_sub_no'],
                'article_title': c['article_title'],
                'old_body': c['old_body'],
                'new_body': c['new_body'],
                'ordinal': i,
            })
        seed.append({'regulation_seq': r['reg_id'], 'revised_at': rev_date,
                     'summary': SUMMARY, 'changes': changes})
        existing.add(key)
        added += 1

    with open(SEED, 'w', encoding='utf-8') as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)
    print('added revisions:', added, 'seed total:', len(seed))


if __name__ == '__main__':
    main()
