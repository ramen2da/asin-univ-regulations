"""Builds the 22 new regulation entries discovered this session (20 대학원
regulations entirely missing from the system, plus 학생준칙/학회설치 및
운영에 관한 규정 on the undergraduate side) and merges them into
regulations_final_clean.json as new seq 121-142."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_grdsch import parse_regulation

BASE = r'C:\Users\bbuny\AppData\Local\Temp\grdsch_full'
OUT_PATH = os.path.join(os.path.dirname(__file__), 'output', 'regulations_final_clean.json')

# (source markdown filename, title, l0, l1)
COMMON_GRDSCH = [
    ('file01.md', '대학원생 준칙'),
    ('file02.md', '교과과정 및 이수학점에 관한 규정'),
    ('file03.md', '선수학점에 관한 규정'),
    ('file04.md', '개인지도에 관한 규정'),
    ('file05.md', '학위논문에 관한 규정'),
    ('file06.md', '장학금 지급에 관한 규정'),
    ('file07.md', '재입학에 관한 규정'),
    ('file08.md', '전과 및 전공변경에 관한 규정'),
]

SCHOOLS = [
    ('', '일반대학원'),
    ('02', '신학대학원'),
    ('03', '선교대학원'),
    ('04', '교육대학원'),
    ('05', '상담대학원'),
    ('06', '복지대학원'),
]

UNDERGRAD_EXTRA = [
    ('std_junchic.md', '학생준칙'),
    ('std_install.md', '학회설치 및 운영에 관한 규정'),
]


def build():
    with open(OUT_PATH, encoding='utf-8') as f:
        regs = json.load(f)

    # Idempotent: drop any previously-built batch (seq 121+) before adding a
    # freshly reparsed one, so re-running this after a parser fix doesn't
    # duplicate the whole batch under a second seq range.
    regs = [r for r in regs if r['seq'] <= 120]
    max_seq = max(r['seq'] for r in regs)
    assert max_seq == 120, f'expected base max seq 120, got {max_seq}'
    next_seq = max_seq + 1

    new_entries = []

    for fn, title in COMMON_GRDSCH:
        rec = parse_regulation(os.path.join(BASE, fn), title_hint=title)
        new_entries.append({
            'seq': next_seq,
            'l0': '대학원',
            'l1': None,
            'index_no': '1',
            'toc_title': title,
            'parsed_title': title,
            'enact_date': rec['enact_date'],
            'amend_dates': rec['amend_dates'],
            'article_count': rec['article_count'],
            'articles': rec['articles'],
            'addenda': rec['addenda'],
            'attachments': rec['attachments'],
            'pdf_pages': [],
        })
        next_seq += 1

    for suffix, school in SCHOOLS:
        for kind, fname_base in (('학칙', f'grdsch_hakchic{suffix}.md'), ('학사내규', f'grdsch_hacksa{suffix}.md')):
            title = f'{school} {kind}'
            rec = parse_regulation(os.path.join(BASE, fname_base), title_hint=title)
            new_entries.append({
                'seq': next_seq,
                'l0': '대학원',
                'l1': school,
                'index_no': '1',
                'toc_title': title,
                'parsed_title': title,
                'enact_date': rec['enact_date'],
                'amend_dates': rec['amend_dates'],
                'article_count': rec['article_count'],
                'articles': rec['articles'],
                'addenda': rec['addenda'],
                'attachments': rec['attachments'],
                'pdf_pages': [],
            })
            next_seq += 1

    for fn, title in UNDERGRAD_EXTRA:
        rec = parse_regulation(os.path.join(BASE, fn), title_hint=title)
        new_entries.append({
            'seq': next_seq,
            'l0': '학사',
            'l1': None,
            'index_no': '1',
            'toc_title': title,
            'parsed_title': title,
            'enact_date': rec['enact_date'],
            'amend_dates': rec['amend_dates'],
            'article_count': rec['article_count'],
            'articles': rec['articles'],
            'addenda': rec['addenda'],
            'attachments': rec['attachments'],
            'pdf_pages': [],
        })
        next_seq += 1

    assert len(new_entries) == 22, len(new_entries)
    regs.extend(new_entries)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(regs, f, ensure_ascii=False, indent=2)

    print(f'added {len(new_entries)} new regulations (seq {max_seq + 1}-{next_seq - 1})')
    for e in new_entries:
        print(f'  seq {e["seq"]:3d} [{e["l0"]}/{e["l1"] or "-"}] {e["parsed_title"]} '
              f'(articles={e["article_count"]}, addenda={len(e["addenda"])})')


if __name__ == '__main__':
    build()
