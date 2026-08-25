import sys
import os
import sqlite3
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from extract_hakchik import extract_hakchik_pdf
from build_revision_history import (
    strip_for_noise_check,
    resolve_change_date,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "regulations.db")
REGULATION_ID = 120

EDITIONS = [
    (date(2025, 9, 25), "학칙_250925개정(사회복지현장실습교육과정운영세칙 신설 반영).pdf"),
    (date(2026, 4, 30), "학칙_260430개정(2026편입생 본전공이수학점).pdf"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    current_rows = cur.execute(
        "SELECT id, no, sub_no, title, body FROM articles WHERE regulation_id=?", (REGULATION_ID,)
    ).fetchall()
    current_body = {(r["no"], r["sub_no"]): r["body"] for r in current_rows}
    current_title = {(r["no"], r["sub_no"]): r["title"] for r in current_rows}

    timeline = []
    for d, fn in EDITIONS:
        path = os.path.join(os.path.dirname(__file__), "..", fn)
        record = extract_hakchik_pdf(path, seq=REGULATION_ID)
        body_map = {(a["no"], a["sub_no"]): a["body"] for a in record["articles"]}
        timeline.append((d.isoformat(), body_map))
        print(f"{d.isoformat()}: {len(body_map)} articles parsed from {fn}", file=sys.stderr)

    today = date(2026, 6, 23).isoformat()  # date of the current (260623) edition
    full = timeline + [(today, current_body)]

    all_keys = set()
    for _, bm in full:
        all_keys.update(bm.keys())

    changes_by_date = defaultdict(list)
    dropped = 0
    for key in all_keys:
        no, sub_no = key
        prev_body = None
        prev_present = False
        for d, bm in full:
            body = bm.get(key)
            present = body is not None
            if prev_present and present and body != prev_body:
                if strip_for_noise_check(prev_body) == strip_for_noise_check(body):
                    dropped += 1
                else:
                    change_date, method = resolve_change_date(prev_body, body, d)
                    changes_by_date[change_date].append({
                        "article_no": int(no),
                        "article_sub_no": int(sub_no) if sub_no else None,
                        "article_title": current_title.get(key),
                        "old_body": prev_body,
                        "new_body": body,
                        "method": method,
                    })
            prev_body = body if present else prev_body
            prev_present = prev_present or present

    total = sum(len(v) for v in changes_by_date.values())
    print(f"detected {total} real changes across {len(changes_by_date)} dates (dropped as noise: {dropped})", file=sys.stderr)

    existing_amend_dates = {r["amend_date"] for r in cur.execute(
        "SELECT amend_date FROM amendments WHERE regulation_id=?", (REGULATION_ID,)
    ).fetchall()}

    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()

    revisions_created = 0
    changes_created = 0
    amendments_created = 0
    for change_date in sorted(changes_by_date.keys()):
        items = changes_by_date[change_date]
        dotted = change_date.replace("-", ".")
        cur.execute(
            "INSERT INTO revisions (regulation_id, revised_at, summary, created_at) VALUES (?, ?, ?, ?)",
            (REGULATION_ID, dotted, "과거 학칙 PDF 대조로 자동 확인된 개정 이력", created_at),
        )
        revision_id = cur.lastrowid
        revisions_created += 1
        for ordinal, it in enumerate(items):
            cur.execute(
                """INSERT INTO revision_changes
                   (revision_id, article_no, article_sub_no, article_title, old_body, new_body, ordinal)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (revision_id, it["article_no"], it["article_sub_no"], it["article_title"],
                 it["old_body"], it["new_body"], ordinal),
            )
            changes_created += 1
        if dotted not in existing_amend_dates:
            max_ord = cur.execute(
                "SELECT COALESCE(MAX(ordinal), -1) FROM amendments WHERE regulation_id=?", (REGULATION_ID,)
            ).fetchone()[0]
            cur.execute(
                "INSERT INTO amendments (regulation_id, amend_date, ordinal) VALUES (?, ?, ?)",
                (REGULATION_ID, dotted, max_ord + 1),
            )
            existing_amend_dates.add(dotted)
            amendments_created += 1

    conn.commit()
    conn.close()
    print(f"inserted: {revisions_created} revisions, {changes_created} changes, {amendments_created} new amendment dates", file=sys.stderr)


if __name__ == "__main__":
    main()
