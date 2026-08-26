"""Exports the current DB's revisions/revision_changes into
pipeline/output/revision_history_seed.json, the portable seed file
load_revision_history.py replays on every Render deploy (Render's build
only runs load_data.py + load_revision_history.py - it never re-derives
revision history from PDFs, so this file is the only thing that keeps the
deployed site's 개정내역/신구조문대조표 in sync with whatever local fixes
changed article bodies since the last export)."""
import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'regulations.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), 'output', 'revision_history_seed.json')


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    inner_cur = conn.cursor()  # a query on `cur` inside the loop below would
                                # silently replace `cur`'s own in-progress
                                # result set and truncate the outer iteration

    seq_by_id = {row['id']: row['seq'] for row in cur.execute('SELECT id, seq FROM regulations')}

    seed = []
    for rev in list(cur.execute('SELECT id, regulation_id, revised_at, summary FROM revisions ORDER BY regulation_id, revised_at')):
        seq = seq_by_id.get(rev['regulation_id'])
        if seq is None:
            continue
        changes = [
            {
                'article_no': c['article_no'],
                'article_sub_no': c['article_sub_no'],
                'article_title': c['article_title'],
                'old_body': c['old_body'],
                'new_body': c['new_body'],
                'ordinal': c['ordinal'],
            }
            for c in inner_cur.execute(
                'SELECT article_no, article_sub_no, article_title, old_body, new_body, ordinal '
                'FROM revision_changes WHERE revision_id=? ORDER BY ordinal',
                (rev['id'],),
            )
        ]
        seed.append({
            'regulation_seq': seq,
            'revised_at': rev['revised_at'],
            'summary': rev['summary'],
            'changes': changes,
        })

    conn.close()

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)

    total_changes = sum(len(e['changes']) for e in seed)
    print(f'exported {len(seed)} revisions, {total_changes} changes to {OUT_PATH}')


if __name__ == '__main__':
    main()
