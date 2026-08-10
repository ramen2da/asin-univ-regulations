import json

from fastapi import APIRouter, HTTPException, Query

from db import get_connection

router = APIRouter()


@router.get("/regulations")
def list_regulations(
    category_l0: str | None = None,
    category_l1: str | None = None,
    q: str | None = None,
    scope: str = Query("title", pattern="^(title|body)$"),
    sort: str = Query("seq", pattern="^(seq|abc|date)$"),
    page: int = 1,
    page_size: int = 20,
):
    conn = get_connection()

    where = ["r.status = '현행'"]
    params: list = []

    if category_l0:
        where.append("r.category_l0 = ?")
        params.append(category_l0)
    if category_l1:
        where.append("r.category_l1 = ?")
        params.append(category_l1)

    if q:
        if scope == "title":
            where.append("r.title LIKE ?")
            params.append(f"%{q}%")
        else:
            where.append(
                "r.id IN (SELECT regulation_id FROM articles WHERE body LIKE ?)"
            )
            params.append(f"%{q}%")

    where_sql = " AND ".join(where)

    order_sql = {
        "seq": "r.seq",
        "abc": "r.title",
        "date": "latest_amend DESC",
    }[sort]

    base_from = f"""
        FROM regulations r
        LEFT JOIN (
            SELECT regulation_id, MAX(amend_date) AS latest_amend
            FROM amendments GROUP BY regulation_id
        ) a ON a.regulation_id = r.id
        WHERE {where_sql}
    """

    total = conn.execute(f"SELECT COUNT(*) {base_from}", params).fetchone()[0]

    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT r.id, r.seq, r.title, r.category_l0, r.category_l1,
                   r.enact_date, a.latest_amend
            {base_from}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?""",
        [*params, page_size, offset],
    ).fetchall()
    conn.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [dict(r) for r in rows],
    }


@router.get("/regulations/recent")
def recent_regulations(limit: int = 10):
    conn = get_connection()
    rows = conn.execute(
        """SELECT r.id, r.title, MAX(a.amend_date) AS latest_amend
           FROM regulations r
           JOIN amendments a ON a.regulation_id = r.id
           WHERE r.status = '현행'
           GROUP BY r.id
           ORDER BY latest_amend DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/attachments")
def list_attachments(q: str | None = None, page: int = 1, page_size: int = 20):
    conn = get_connection()

    where = ["1=1"]
    params: list = []
    if q:
        where.append("(r.title LIKE ? OR a.label LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    where_sql = " AND ".join(where)

    base_from = f"""
        FROM attachments a
        JOIN regulations r ON r.id = a.regulation_id
        WHERE {where_sql}
    """

    total = conn.execute(f"SELECT COUNT(*) {base_from}", params).fetchone()[0]

    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT a.regulation_id, r.title AS regulation_title, a.ordinal,
                   a.label, a.start_page, a.end_page, a.file_url,
                   CASE WHEN a.rows_json IS NOT NULL THEN 1 ELSE 0 END AS has_table
            {base_from}
            ORDER BY r.seq, a.ordinal
            LIMIT ? OFFSET ?""",
        [*params, page_size, offset],
    ).fetchall()
    conn.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [dict(r) for r in rows],
    }


@router.get("/regulations/{regulation_id}")
def get_regulation(regulation_id: int):
    conn = get_connection()
    reg = conn.execute(
        "SELECT * FROM regulations WHERE id = ?", (regulation_id,)
    ).fetchone()
    if reg is None:
        conn.close()
        raise HTTPException(status_code=404, detail="규정을 찾을 수 없습니다")

    amendments = conn.execute(
        "SELECT amend_date FROM amendments WHERE regulation_id = ? ORDER BY ordinal",
        (regulation_id,),
    ).fetchall()
    articles = conn.execute(
        """SELECT chapter, section, gwan, no, sub_no, title, body
           FROM articles WHERE regulation_id = ? ORDER BY ordinal""",
        (regulation_id,),
    ).fetchall()
    addenda_rows = conn.execute(
        "SELECT line FROM addenda WHERE regulation_id = ? ORDER BY ordinal",
        (regulation_id,),
    ).fetchall()
    attachment_rows = conn.execute(
        """SELECT ordinal, label, start_page, end_page, lines_json, rows_json, file_url
           FROM attachments WHERE regulation_id = ? ORDER BY ordinal""",
        (regulation_id,),
    ).fetchall()
    conn.close()

    attachments = []
    for a in attachment_rows:
        att = {
            "ordinal": a["ordinal"],
            "label": a["label"],
            "start_page": a["start_page"],
            "end_page": a["end_page"],
            "lines": json.loads(a["lines_json"]),
            "file_url": a["file_url"],
        }
        if a["rows_json"]:
            att["rows"] = json.loads(a["rows_json"])
        attachments.append(att)

    return {
        **dict(reg),
        "amendments": [a["amend_date"] for a in amendments],
        "articles": [dict(a) for a in articles],
        "addenda": [a["line"] for a in addenda_rows],
        "attachments": attachments,
    }


@router.get("/revisions")
def list_all_revisions(page: int = 1, page_size: int = 20):
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        """SELECT rev.id, rev.regulation_id, r.title AS regulation_title,
                  rev.revised_at, rev.summary,
                  (SELECT COUNT(*) FROM revision_changes rc WHERE rc.revision_id = rev.id) AS changed_count
           FROM revisions rev
           JOIN regulations r ON r.id = rev.regulation_id
           ORDER BY rev.created_at DESC
           LIMIT ? OFFSET ?""",
        (page_size, offset),
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [dict(r) for r in rows],
    }


@router.get("/regulations/{regulation_id}/revisions")
def list_revisions(regulation_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, revised_at, summary FROM revisions WHERE regulation_id = ? ORDER BY revised_at",
        (regulation_id,),
    ).fetchall()
    conn.close()
    return {row["revised_at"]: {"id": row["id"], "summary": row["summary"]} for row in rows}


@router.get("/revisions/{revision_id}")
def get_revision(revision_id: int):
    conn = get_connection()
    rev = conn.execute("SELECT * FROM revisions WHERE id = ?", (revision_id,)).fetchone()
    if rev is None:
        conn.close()
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없습니다")
    changes = conn.execute(
        """SELECT article_no, article_sub_no, article_title, old_body, new_body
           FROM revision_changes WHERE revision_id = ? ORDER BY ordinal""",
        (revision_id,),
    ).fetchall()
    conn.close()
    return {**dict(rev), "changes": [dict(c) for c in changes]}
