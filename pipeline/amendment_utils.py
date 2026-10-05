"""Shared helper for inserting a newly-discovered amendment date into the
`amendments` table at its correct chronological position, rather than at
the end of the ordinal sequence.

Every place that adds an amendment date discovered from a snapshot-diff
pass (build_hakchik_history.py, build_revision_history.py,
load_revision_history.py) used to always append at MAX(ordinal)+1 - correct
only when the discovered date happens to be the regulation's most recent
one. When the diff pass processes historical editions out of date order (or
a later edition just happens to get diffed after an earlier one), the
appended date lands after amendments that are chronologically later than it
(confirmed: 아신대학교 학칙, "2026.04.30" appended after an already-present
"2026.06.23" - shows on the page as "..., 2025.09.25, 2026.06.23,
2026.04.30", visibly out of order). Amendment date strings are zero-padded
YYYY.MM(.DD) by this point in the pipeline, so a plain string comparison
sorts them chronologically - no date parsing needed.
"""


def insert_amendment_chronologically(cur, regulation_id, amend_date):
    """Inserts (regulation_id, amend_date) into `amendments`, shifting the
    ordinal of every existing row that sorts after it. Caller is
    responsible for checking the date isn't already present."""
    existing = cur.execute(
        'SELECT id, amend_date, ordinal FROM amendments WHERE regulation_id=? ORDER BY ordinal',
        (regulation_id,),
    ).fetchall()

    insert_at = len(existing)
    for i, row in enumerate(existing):
        if row[1] > amend_date:
            insert_at = i
            break

    for row in existing[insert_at:]:
        cur.execute('UPDATE amendments SET ordinal=? WHERE id=?', (row[2] + 1, row[0]))

    cur.execute(
        'INSERT INTO amendments (regulation_id, amend_date, ordinal) VALUES (?, ?, ?)',
        (regulation_id, amend_date, insert_at),
    )
