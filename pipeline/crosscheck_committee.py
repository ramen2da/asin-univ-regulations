"""Cross-checks the committee archive's 신구조문대비표 records against the
revision history in the DB. For each committee record matched to a current
regulation, looks for a revision of that regulation dated within the
window [session date, session date + 9 months] (final 규정집 publication
follows the meeting by weeks to months). Records with no such revision are
gaps; the parsed article changes are saved for review and, if approved,
for filling the history.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from committee_block_changes import block_changes

CACHE = r'C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad\committee_md_cache\_result.json'
OUT = r'C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad\crosscheck_out.json'
DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'regulations.db')
INTER = re.compile('[·‧․∙・]')


def norm(t):
    t = re.sub(r'\s+', '', t or '')
    t = re.sub(r'^아신대학교', '', t)
    return INTER.sub('', t)


def add_months(d, m):
    y, mo = divmod(d.month - 1 + m, 12)
    return date(d.year + y, mo + 1, min(d.day, 28))


def main():
    conn = sqlite3.connect(DB)
    regs = conn.execute("SELECT id, title FROM regulations WHERE status='현행'").fetchall()
    by_key = {}
    for rid, t in regs:
        by_key.setdefault(norm(t), []).append(rid)
    revs = {}
    for rid, d in conn.execute('SELECT regulation_id, revised_at FROM revisions'):
        revs.setdefault(rid, []).append(d)

    committee = json.load(open(CACHE, encoding='utf-8'))
    results = []
    for session, recs in committee.items():
        s = session[:8]
        sd = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        for key, v in recs.items():
            cands = by_key.get(norm(key), [])
            if len(cands) != 1:
                results.append({'session': s, 'title': key, 'status': 'unmatched', 'reg_id': None,
                                'changes': block_changes(v['content'])})
                continue
            rid = cands[0]
            end = add_months(sd, 9)
            hit = [d for d in revs.get(rid, []) if sd <= date(*map(int, d.split('.')[:3])) <= end]
            status = 'covered' if hit else 'gap'
            results.append({'session': s, 'title': key, 'status': status, 'reg_id': rid,
                            'existing': hit, 'changes': block_changes(v['content'])})

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    from collections import Counter
    print(Counter(r['status'] for r in results))
    print('gap records with changes:', sum(1 for r in results if r['status'] == 'gap' and r['changes']))


if __name__ == '__main__':
    main()
