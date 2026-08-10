from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import Cookie
from pydantic import BaseModel

from auth import create_session, destroy_session, require_admin, verify_password
from db import get_connection

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/admin/login")
def admin_login(body: LoginRequest, response: Response):
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")
    token = create_session()
    response.set_cookie("admin_session", token, httponly=True, samesite="lax")
    return {"ok": True}


@router.post("/admin/logout")
def admin_logout(response: Response, admin_session: str | None = Cookie(default=None)):
    if admin_session:
        destroy_session(admin_session)
    response.delete_cookie("admin_session")
    return {"ok": True}


@router.get("/admin/check")
def admin_check(_: None = Depends(require_admin)):
    return {"ok": True}


@router.get("/admin/regulations", dependencies=[Depends(require_admin)])
def list_regulations_for_admin():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, seq, title, category_l0, category_l1 FROM regulations ORDER BY seq"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/admin/regulations/{regulation_id}", dependencies=[Depends(require_admin)])
def get_regulation_for_edit(regulation_id: int):
    conn = get_connection()
    reg = conn.execute("SELECT * FROM regulations WHERE id = ?", (regulation_id,)).fetchone()
    if reg is None:
        conn.close()
        raise HTTPException(status_code=404, detail="규정을 찾을 수 없습니다")
    articles = conn.execute(
        """SELECT id, chapter, section, gwan, no, sub_no, title, body, ordinal
           FROM articles WHERE regulation_id=? ORDER BY ordinal""",
        (regulation_id,),
    ).fetchall()
    conn.close()
    return {**dict(reg), "articles": [dict(a) for a in articles]}


class ArticleEdit(BaseModel):
    id: int
    body: str


class SaveRevisionRequest(BaseModel):
    revised_at: str
    summary: str | None = None
    articles: list[ArticleEdit]


@router.post("/admin/regulations/{regulation_id}/save", dependencies=[Depends(require_admin)])
def save_revision(regulation_id: int, body: SaveRevisionRequest):
    revised_at = body.revised_at.replace("-", ".")

    conn = get_connection()
    cur = conn.cursor()

    current = {
        row["id"]: row
        for row in cur.execute(
            "SELECT id, no, sub_no, title, body FROM articles WHERE regulation_id=?",
            (regulation_id,),
        ).fetchall()
    }

    changes = []
    for edit in body.articles:
        row = current.get(edit.id)
        if row is None:
            continue
        if row["body"] != edit.body:
            changes.append(
                {
                    "id": edit.id,
                    "article_no": row["no"],
                    "article_sub_no": row["sub_no"],
                    "article_title": row["title"],
                    "old_body": row["body"],
                    "new_body": edit.body,
                }
            )

    if not changes:
        conn.close()
        return {"ok": True, "changed": 0}

    cur.execute(
        "INSERT INTO revisions (regulation_id, revised_at, summary, created_at) VALUES (?, ?, ?, ?)",
        (regulation_id, revised_at, body.summary, datetime.now(timezone.utc).isoformat()),
    )
    revision_id = cur.lastrowid

    for i, ch in enumerate(changes):
        cur.execute(
            """INSERT INTO revision_changes
               (revision_id, article_no, article_sub_no, article_title, old_body, new_body, ordinal)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                revision_id,
                ch["article_no"],
                ch["article_sub_no"],
                ch["article_title"],
                ch["old_body"],
                ch["new_body"],
                i,
            ),
        )
        cur.execute("UPDATE articles SET body=? WHERE id=?", (ch["new_body"], ch["id"]))

    exists = cur.execute(
        "SELECT 1 FROM amendments WHERE regulation_id=? AND amend_date=?",
        (regulation_id, revised_at),
    ).fetchone()
    if not exists:
        max_ord = cur.execute(
            "SELECT COALESCE(MAX(ordinal), -1) FROM amendments WHERE regulation_id=?",
            (regulation_id,),
        ).fetchone()[0]
        cur.execute(
            "INSERT INTO amendments (regulation_id, amend_date, ordinal) VALUES (?, ?, ?)",
            (regulation_id, revised_at, max_ord + 1),
        )

    conn.commit()
    conn.close()
    return {"ok": True, "changed": len(changes), "revision_id": revision_id}
