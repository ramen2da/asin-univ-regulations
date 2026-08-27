"""Adds the regulations discovered via the committee-archive cross-check
(file/11 규정/, session 2020-2026) that turned out to be real, currently-
active regulations missing from the system entirely - not just outdated
copies of something already present. Source text pulled from
file/11 규정/홈페이지업로드파일_규정외/file/ (the site's own last full
export of individually-published regulation PDFs) for the 9 established
ones, and directly from the committee archive's own extracted 신구조문대비표
"개정안" column for 외국인 유학생 관리 규정 (신설 2026, no prior text to
find - the amendment table's "new" side IS the complete regulation).

A further ~5 candidates from the same cross-check (AIGS 외국인유학생 장학금
지급에 관한 규정, 국제교육원 학사내규, 신학대학원 목회학석사 트랙제 운영에
관한 규정, 경건훈련에 관한 규정, 교과목 개설에 관한 시행세칙's exact current
scope) could not be resolved to a findable founding text within this pass
and are deliberately left out - only the ones with the ones with a genuine
recoverable full text.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_daehakwon import parse_regulation, parse_body, BOLD_MARK_RE

SCRATCH = r'C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad\new_regs'
OUT_PATH = os.path.join(os.path.dirname(__file__), 'output', 'regulations_final_clean.json')

# (kind, source, title, l0, l1)
NEW_ENTRIES = [
    ('md', 'ondevice.md', '원격수업 개발 및 운영규정', '학사', None),
    ('md', 'subclass.md', '수업평가 규정', '학사', None),
    ('md', 'aigs4c.md', '아신4C교양인증제 운영규정', '학사', None),
    ('md', 'tesol.md', 'TESOL 운영규정', '학사', None),
    ('md', 'admission.md', '대학입학전형공정관리위원회 규정', '학사', None),
    ('md', 'divisional.md', '학부제운영 시행세칙', '학사', None),
    ('md', 'coursework.md', '교과목 개설에 관한 시행세칙', '학사', None),
    ('md', 'tuition_committee.md', '등록금심의위원회 규정', '일반행정', '재무회계'),
    ('md', 'tuition_committee_rules.md', '등록금심의위원회 운영세칙', '일반행정', '재무회계'),
]


def build():
    with open(OUT_PATH, encoding='utf-8') as f:
        regs = json.load(f)

    max_seq = max(r['seq'] for r in regs)
    next_seq = max(max_seq, 149) + 1

    added = []
    for kind, fn, title, l0, l1 in NEW_ENTRIES:
        rec = parse_regulation(os.path.join(SCRATCH, fn), title_hint=title, preprocess_scratch_dir=SCRATCH)
        entry = {
            'seq': next_seq, 'l0': l0, 'l1': l1, 'index_no': '1',
            'toc_title': title, 'parsed_title': title,
            'enact_date': rec['enact_date'], 'amend_dates': rec['amend_dates'],
            'article_count': rec['article_count'], 'articles': rec['articles'],
            'addenda': rec['addenda'], 'attachments': rec['attachments'],
            'pdf_pages': [],
        }
        regs.append(entry)
        added.append(entry)
        next_seq += 1

    # 외국인 유학생 관리 규정 - plain text already extracted from the
    # committee archive (신설 2026, no prior founding doc to locate)
    waegug_path = os.path.join(
        r'C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad',
        'new_외국인유학생관리규정_20260526.txt',
    )
    with open(waegug_path, encoding='utf-8') as f:
        lines = BOLD_MARK_RE.sub('', f.read()).split('\n')
    articles, addenda, attachments = parse_body(lines[1:])  # skip title line
    entry = {
        'seq': next_seq, 'l0': '학사', 'l1': None, 'index_no': '1',
        'toc_title': '외국인 유학생 관리 규정', 'parsed_title': '외국인 유학생 관리 규정',
        'enact_date': '2026.05.26', 'amend_dates': ['2026.05.26'],
        'article_count': len(articles), 'articles': articles,
        'addenda': addenda, 'attachments': attachments,
        'pdf_pages': [],
    }
    regs.append(entry)
    added.append(entry)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(regs, f, ensure_ascii=False, indent=2)

    print(f'added {len(added)} entries (seq {max(max_seq, 149) + 1}-{next_seq})')
    for e in added:
        print(f"  seq {e['seq']:3d} [{e['l0']}/{e['l1'] or '-'}] {e['toc_title']} "
              f"(articles={e['article_count']})")


if __name__ == '__main__':
    build()
