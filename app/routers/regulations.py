import html
import json
import re

from fastapi import APIRouter, HTTPException, Query

from db import get_connection

router = APIRouter()

SNIPPET_CONTEXT = 40


def make_snippet(body, query, context=SNIPPET_CONTEXT):
    idx = body.lower().find(query.lower())
    if idx == -1:
        return html.escape(body[:context * 2]) + ("…" if len(body) > context * 2 else "")

    start = max(0, idx - context)
    end = min(len(body), idx + len(query) + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    before = html.escape(body[start:idx])
    match = html.escape(body[idx:idx + len(query)])
    after = html.escape(body[idx + len(query):end])
    return f"{prefix}{before}<mark>{match}</mark>{after}{suffix}"


def article_label(no, sub_no, title):
    base = f"제{no}조" + (f"의{sub_no}" if sub_no else "")
    return f"{base}({title})" if title else base


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

    if q and scope == "body":
        where = ["r.status = '현행'", "a.body LIKE ?"]
        params: list = [f"%{q}%"]
        if category_l0:
            where.append("r.category_l0 = ?")
            params.append(category_l0)
        if category_l1:
            where.append("r.category_l1 = ?")
            params.append(category_l1)
        where_sql = " AND ".join(where)

        base_from = f"""
            FROM articles a
            JOIN regulations r ON r.id = a.regulation_id
            WHERE {where_sql}
        """

        total = conn.execute(f"SELECT COUNT(*) {base_from}", params).fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""SELECT r.id AS regulation_id, r.title AS regulation_title,
                       r.category_l0, r.category_l1,
                       a.no, a.sub_no, a.title AS article_title, a.body
                {base_from}
                ORDER BY r.seq, a.ordinal
                LIMIT ? OFFSET ?""",
            [*params, page_size, offset],
        ).fetchall()
        conn.close()

        results = [
            {
                "regulation_id": row["regulation_id"],
                "regulation_title": row["regulation_title"],
                "category_l0": row["category_l0"],
                "category_l1": row["category_l1"],
                "article_no": row["no"],
                "article_sub_no": row["sub_no"],
                "article_label": article_label(row["no"], row["sub_no"], row["article_title"]),
                "snippet": make_snippet(row["body"], q),
            }
            for row in rows
        ]
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "scope": "body",
            "results": results,
        }

    where = ["r.status = '현행'"]
    params: list = []

    if category_l0:
        where.append("r.category_l0 = ?")
        params.append(category_l0)
    if category_l1:
        where.append("r.category_l1 = ?")
        params.append(category_l1)

    if q:
        where.append("r.title LIKE ?")
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
        "scope": "title",
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
def list_all_revisions(
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    conn = get_connection()

    where = ["1=1"]
    params: list = []
    if q:
        where.append("r.title LIKE ?")
        params.append(f"%{q}%")
    if date_from:
        where.append("rev.revised_at >= ?")
        params.append(date_from.replace("-", "."))
    if date_to:
        where.append("rev.revised_at <= ?")
        params.append(date_to.replace("-", "."))
    where_sql = " AND ".join(where)

    base_from = f"""
        FROM revisions rev
        JOIN regulations r ON r.id = rev.regulation_id
        WHERE {where_sql}
    """

    total = conn.execute(f"SELECT COUNT(*) {base_from}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT rev.id, rev.regulation_id, r.title AS regulation_title,
                   rev.revised_at, rev.summary,
                   (SELECT COUNT(*) FROM revision_changes rc WHERE rc.revision_id = rev.id) AS changed_count
            {base_from}
            ORDER BY rev.revised_at DESC, rev.created_at DESC
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
