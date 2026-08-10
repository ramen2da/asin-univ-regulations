from collections import OrderedDict

from fastapi import APIRouter

from db import get_connection

router = APIRouter()


@router.get("/tree")
def get_tree():
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, seq, title, category_l0, category_l1
           FROM regulations
           WHERE status = '현행'
           ORDER BY seq"""
    ).fetchall()
    conn.close()

    tree = OrderedDict()
    for r in rows:
        l0 = r["category_l0"] or "(미분류)"
        l1 = r["category_l1"]
        tree.setdefault(l0, OrderedDict())
        key = l1 or "__direct__"
        tree[l0].setdefault(key, [])
        tree[l0][key].append({"id": r["id"], "title": r["title"], "seq": r["seq"]})

    result = []
    for l0, subs in tree.items():
        node = {"name": l0, "type": "category", "children": []}
        direct = subs.pop("__direct__", [])
        for reg in direct:
            node["children"].append({"type": "regulation", **reg})
        for l1, regs in subs.items():
            node["children"].append({
                "name": l1,
                "type": "category",
                "children": [{"type": "regulation", **reg} for reg in regs],
            })
        result.append(node)

    return result
