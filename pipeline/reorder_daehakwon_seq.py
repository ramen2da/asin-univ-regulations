"""Renumbers the "대학원" category's l1=None regulations so the tree lists
them in a sensible reading order instead of raw creation order: the
foundational 학칙 + 학사내규 pair leads the category (matching the pattern
already used elsewhere in the site - 학교법인 정관(1) + 정관시행세칙(2) lead
"정관"; 산학협력단 정관(118) + 운영규정(119) lead "산학협력단"), and
장학금 지급에 관한 규정 (the parent rule) sits directly beside 장학금운영
시행세칙 (its implementing detail), instead of being separated by unrelated
regulations.

Safe to renumber (id == seq in this schema, so this changes primary keys):
none of these seq values have any revision_changes rows yet (confirmed via
the seed - the whole 대학원 batch predates any matched historical snapshot),
so there are no foreign keys to fix up elsewhere.
"""
import json

OLD_TO_NEW = {
    143: 121,  # 아신대학교 대학원 학칙
    144: 122,  # 아신대학교 대학원 학사내규
    121: 123,  # 대학원생 준칙
    123: 124,  # 선수학점에 관한 규정
    122: 125,  # 교육과정 및 이수학점에 관한 규정
    124: 126,  # 개인지도에 관한 규정
    125: 127,  # 학위논문에 관한 규정
    127: 128,  # 재입학에 관한 규정
    128: 129,  # 전과 및 전공변경에 관한 규정
    148: 130,  # 청강에 관한 규정
    149: 131,  # 학점교환제에 관한 규정
    126: 132,  # 장학금 지급에 관한 규정
    146: 133,  # 장학금운영 시행세칙
}

path = 'pipeline/output/regulations_final_clean.json'
with open(path, encoding='utf-8') as f:
    regs = json.load(f)

touched = set(OLD_TO_NEW)
present = {r['seq'] for r in regs}
assert touched <= present, touched - present

for r in regs:
    if r['seq'] in OLD_TO_NEW:
        r['seq'] = OLD_TO_NEW[r['seq']]

regs.sort(key=lambda r: r['seq'])

with open(path, 'w', encoding='utf-8') as f:
    json.dump(regs, f, ensure_ascii=False, indent=2)

print('renumbered', len(OLD_TO_NEW), 'entries')
for r in regs:
    if r['seq'] in OLD_TO_NEW.values():
        print(f"  seq {r['seq']:3d}  {r['toc_title']}")
