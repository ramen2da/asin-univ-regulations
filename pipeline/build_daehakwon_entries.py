"""Reflects file/학칙/대학원규정/ (discovered 2026-08-27) into
regulations_final_clean.json: the 20 대학원 regulations added earlier this
session as seq 121-142 (extract_grdsch.py's batch, from an old website file
dump) turn out to include 6 separate per-school 학칙 + 6 separate per-school
학사내규 documents (seq 129-140) that were officially ABOLISHED 2018-12-14 and
replaced with ONE unified 아신대학교 대학원 학칙 and 학사내규 covering all 6
schools - confirmed by the abolished-batch's own successor document's 부칙:
"이 학칙의 시행과 동시에 일반대학원 학칙, 신학대학원 학칙, 선교대학원 학칙,
교육대학원 학칙, 상담대학원 학칙, 복지대학원 학칙은 폐지한다."

This is a one-shot data migration, not a repeatable pipeline step (unlike
build_grdsch_entries.py, which re-derives its whole batch from scratch every
run) - it asserts the expected starting shape (max seq 142, seq 129-140 still
present) so an accidental second run fails loudly instead of silently
corrupting the file, rather than trying to be idempotent against its own
prior output.

Net effect: -12 (the 6+6 obsolete school-specific entries) +7 (1 unified
학칙, 1 unified 학사내규, and 5 regulations that turned out to be either new
or so revised they're really replacements rather than updates - kept as new
entries alongside the 6 in-place content updates below, since none of them
share a title with what they replace)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_daehakwon import parse_regulation, parse_regulation_plain

SCRATCH = r'C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad'
OUT_PATH = os.path.join(os.path.dirname(__file__), 'output', 'regulations_final_clean.json')

OBSOLETE_SCHOOL_SEQS = list(range(129, 141))  # 6 학칙 + 6 학사내규, per-school

# seq -> (source txt path in SCRATCH, title) for in-place content updates
UPDATES = {
    124: (os.path.join(SCRATCH, '개인지도에_관한_규정.txt'), '개인지도에 관한 규정'),
    125: (os.path.join(SCRATCH, '학위논문에_관한_규정.txt'), '학위논문에 관한 규정'),
    126: (os.path.join(SCRATCH, '장학금_지급에_관한_규정.txt'), '장학금 지급에 관한 규정'),
    127: (os.path.join(SCRATCH, '재입학에_관한_규정.txt'), '재입학에 관한 규정'),
    128: (os.path.join(SCRATCH, '전과_및_전공변경에_관한_규정.txt'), '전과 및 전공변경에 관한 규정'),
}

# seq 122 comes from a kordoc-md source (heavy tables) with a corrected
# title ("교과과정" -> "교육과정", matching the new unified doc's own
# self-title) - handled separately from the plain-text UPDATES above.

NEW_ENTRIES = [
    # (kind, source path, title, l1)
    ('md', os.path.join(SCRATCH, 'daehakwon_hakchik.md'), '아신대학교 대학원 학칙', None),
    ('md', os.path.join(SCRATCH, 'hakssanaegyu.md'), '아신대학교 대학원 학사내규', None),
    ('plain', os.path.join(SCRATCH, 'gyeonggeon.txt'), '신학대학원 채플에 관한 규정', '신학대학원'),
    ('md', os.path.join(SCRATCH, 'janghakgum_sihaengsechik.md'), '장학금운영 시행세칙', None),
    ('md', os.path.join(SCRATCH, 'jeonmunsangdam.md'), '전문상담교사(1급) 양성과정(석사학위연계과정) 운영규정', '교육대학원'),
    ('plain', os.path.join(SCRATCH, '청강에_관한_규정.txt'), '청강에 관한 규정', None),
    ('plain', os.path.join(SCRATCH, '학점교환제에_관한_규정.txt'), '학점교환제에 관한 규정', None),
]


def build():
    with open(OUT_PATH, encoding='utf-8') as f:
        regs = json.load(f)

    max_seq = max(r['seq'] for r in regs)
    assert max_seq == 142, f'expected starting max seq 142, got {max_seq} - this script is not safe to re-run'
    present = {r['seq'] for r in regs}
    assert set(OBSOLETE_SCHOOL_SEQS) <= present, 'expected seq 129-140 to still be present'

    by_seq = {r['seq']: r for r in regs}

    # --- in-place content updates (plain-text sourced) ---
    for seq, (path, title) in UPDATES.items():
        rec = parse_regulation_plain(path, title)
        r = by_seq[seq]
        r['toc_title'] = title
        r['parsed_title'] = title
        r['enact_date'] = rec['enact_date']
        r['amend_dates'] = rec['amend_dates']
        r['article_count'] = rec['article_count']
        r['articles'] = rec['articles']
        r['addenda'] = rec['addenda']
        r['attachments'] = rec['attachments']

    # --- in-place update, seq 122 (교과과정 -> 교육과정, kordoc-md source) ---
    rec = parse_regulation(
        os.path.join(SCRATCH, 'gyoyukgwajeong.md'),
        title_hint='교육과정 및 이수학점에 관한 규정',
        preprocess_scratch_dir=SCRATCH,
    )
    r = by_seq[122]
    r['toc_title'] = '교육과정 및 이수학점에 관한 규정'
    r['parsed_title'] = '교육과정 및 이수학점에 관한 규정'
    r['enact_date'] = rec['enact_date']
    r['amend_dates'] = rec['amend_dates']
    r['article_count'] = rec['article_count']
    r['articles'] = rec['articles']
    r['addenda'] = rec['addenda']
    r['attachments'] = rec['attachments']

    # --- drop the 12 obsolete per-school 학칙/학사내규 entries ---
    regs = [r for r in regs if r['seq'] not in OBSOLETE_SCHOOL_SEQS]

    # --- append the new/replacement entries ---
    next_seq = max_seq + 1
    added = []
    for kind, path, title, l1 in NEW_ENTRIES:
        if kind == 'md':
            rec = parse_regulation(path, title_hint=title, preprocess_scratch_dir=SCRATCH)
        else:
            rec = parse_regulation_plain(path, title)
        entry = {
            'seq': next_seq,
            'l0': '대학원',
            'l1': l1,
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
        }
        regs.append(entry)
        added.append(entry)
        next_seq += 1

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(regs, f, ensure_ascii=False, indent=2)

    print(f'removed seq 129-140 (12 entries); updated seq 122,124-128; added seq {max_seq + 1}-{next_seq - 1} ({len(added)} entries)')
    for e in added:
        print(f'  seq {e["seq"]:3d} [{e["l0"]}/{e["l1"] or "-"}] {e["parsed_title"]} '
              f'(articles={e["article_count"]}, addenda={len(e["addenda"])})')


if __name__ == '__main__':
    build()
