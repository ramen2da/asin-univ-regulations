"""Loads the pre-computed historical revision seed (from build_revision_history.py,
run against the historical 규정집 PDFs) into a freshly-built DB. Kept separate
from the PDF-extraction pipeline so deploys don't need the 17 historical PDFs
or pymupdf just to pick up this data - only load_data.py's regulations/articles
need to exist first."""
import sys
import os
import json
import sqlite3
from datetime import datetime, timezone

SEED_PATH = os.path.join(os.path.dirname(__file__), 'output', 'revision_history_seed.json')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'regulations.db')


def main():
    if not os.path.exists(SEED_PATH):
        print(f'no seed file at {SEED_PATH}, skipping', file=sys.stderr)
        return

    with open(SEED_PATH, encoding='utf-8') as f:
        seed = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    seq_to_id = {row['seq']: row['id'] for row in cur.execute('SELECT id, seq FROM regulations')}
    created_at = datetime.now(timezone.utc).isoformat()

    revisions_created = 0
    changes_created = 0
    amendments_created = 0
    skipped = 0

    for entry in seed:
        regid = seq_to_id.get(entry['regulation_seq'])
        if regid is None:
            skipped += 1
            continue

        exists = cur.execute(
            'SELECT 1 FROM revisions WHERE regulation_id=? AND revised_at=?',
            (regid, entry['revised_at']),
        ).fetchone()
        if exists:
            skipped += 1
            continue

        cur.execute(
            'INSERT INTO revisions (regulation_id, revised_at, summary, created_at) VALUES (?, ?, ?, ?)',
            (regid, entry['revised_at'], entry['summary'], created_at),
        )
        revision_id = cur.lastrowid
        revisions_created += 1

        for change in entry['changes']:
            cur.execute(
                '''INSERT INTO revision_changes
                   (revision_id, article_no, article_sub_no, article_title, old_body, new_body, ordinal)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (revision_id, change['article_no'], change['article_sub_no'], change['article_title'],
                 change['old_body'], change['new_body'], change['ordinal']),
            )
            changes_created += 1

        already = cur.execute(
            'SELECT 1 FROM amendments WHERE regulation_id=? AND amend_date=?',
            (regid, entry['revised_at']),
        ).fetchone()
        if not already:
            max_ord = cur.execute(
                'SELECT COALESCE(MAX(ordinal), -1) FROM amendments WHERE regulation_id=?', (regid,)
            ).fetchone()[0]
            cur.execute(
                'INSERT INTO amendments (regulation_id, amend_date, ordinal) VALUES (?, ?, ?)',
                (regid, entry['revised_at'], max_ord + 1),
            )
            amendments_created += 1

    conn.commit()
    conn.close()

    print(
        f'revision history seed: {revisions_created} revisions, {changes_created} changes, '
        f'{amendments_created} new amendment dates, {skipped} skipped (already present)',
        file=sys.stderr,
    )


if __name__ == '__main__':
    main()
