import json
import sys
from pathlib import Path

from db import get_connection, init_db

JSON_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "output" / "regulations_final_clean.json"

# A couple of titles ended up with historical renaming/repeal notes glued on
# during PDF extraction (the source document's front matter mixes the current
# title with notes about a predecessor regulation's name and dates). Override
# with the clean TOC title for these; the article/addenda content is correct
# either way, only the title string was affected.
TITLE_OVERRIDES = {
    110: "세계지역연구소 운영규정",
    42: "강사임용 등에 관한 규정",
    1: "정관",
}


def load():
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM attachments")
    cur.execute("DELETE FROM addenda")
    cur.execute("DELETE FROM articles")
    cur.execute("DELETE FROM amendments")
    cur.execute("DELETE FROM regulations")
    cur.execute("DELETE FROM regulations_fts")

    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    for r in data:
        pages = r.get("pdf_pages") or []
        pages_str = f"{pages[0]}-{pages[-1]}" if pages else None

        title = TITLE_OVERRIDES.get(r["seq"], r["parsed_title"] or r["toc_title"])

        cur.execute(
            """INSERT INTO regulations
               (id, seq, title, category_l0, category_l1, department, enact_date, status, source_pages)
               VALUES (?, ?, ?, ?, ?, NULL, ?, '현행', ?)""",
            (r["seq"], r["seq"], title,
             r["l0"], r["l1"], r["enact_date"], pages_str),
        )
        reg_id = r["seq"]

        for i, d in enumerate(r.get("amend_dates", [])):
            cur.execute(
                "INSERT INTO amendments (regulation_id, amend_date, ordinal) VALUES (?, ?, ?)",
                (reg_id, d, i),
            )

        for i, a in enumerate(r.get("articles", [])):
            cur.execute(
                """INSERT INTO articles
                   (regulation_id, chapter, section, gwan, no, sub_no, title, body, ordinal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (reg_id, a.get("chapter"), a.get("section"), a.get("gwan"),
                 int(a["no"]), int(a["sub_no"]) if a.get("sub_no") else None,
                 a.get("title"), a["body"], i),
            )

        for i, line in enumerate(r.get("addenda", [])):
            cur.execute(
                "INSERT INTO addenda (regulation_id, line, ordinal) VALUES (?, ?, ?)",
                (reg_id, line, i),
            )

        for i, att in enumerate(r.get("attachments", [])):
            cur.execute(
                """INSERT INTO attachments
                   (regulation_id, label, start_page, end_page, lines_json, rows_json, file_url, ordinal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (reg_id, att["label"], att.get("start_page"), att.get("end_page"),
                 json.dumps(att["lines"], ensure_ascii=False),
                 json.dumps(att["rows"], ensure_ascii=False) if att.get("rows") else None,
                 att.get("file_url"),
                 i),
            )

        body_concat = " ".join(a["body"] for a in r.get("articles", []))
        cur.execute(
            "INSERT INTO regulations_fts (rowid, title, body) VALUES (?, ?, ?)",
            (reg_id, title, body_concat),
        )

    conn.commit()
    n = cur.execute("SELECT COUNT(*) FROM regulations").fetchone()[0]
    conn.close()
    print(f"loaded {n} regulations")


if __name__ == "__main__":
    load()
