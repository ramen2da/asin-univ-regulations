from collections import OrderedDict

from fastapi import APIRouter

from db import get_connection

router = APIRouter()

# Top-level category display order. Regulation seq values were assigned as
# each category's content was added over time (정관 first, 일반행정/부속기관/
# 산학협력단 next, 학사/대학원 last), so sorting purely by seq would not give
# the intended reading order - list it explicitly instead. Anything not in
# this list (there is currently nothing) sorts after, in first-seen order.
CATEGORY_ORDER = ["정관", "학사", "대학원", "일반행정", "부속기관 및 부설기관", "산학협력단"]


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

    def category_rank(l0):
        try:
            return CATEGORY_ORDER.index(l0)
        except ValueError:
            return len(CATEGORY_ORDER)

    ordered_l0 = sorted(tree.keys(), key=category_rank)

    result = []
    for l0 in ordered_l0:
        subs = tree[l0]
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
