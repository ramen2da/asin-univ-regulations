import json
import re
import sys

sys.path.insert(0, 'pipeline')
from extract_committee_archive import normalize_title

with open('pipeline/output/regulations_final_clean.json', encoding='utf-8') as f:
    regs = json.load(f)


INTERPUNCT_RE = re.compile('[·‧․∙・]')  # · ‧ ․ ∙ ・


def db_norm(t):
    t = re.sub(r'\s+', '', t or '')
    t = re.sub(r'^아신대학교', '', t)
    t = INTERPUNCT_RE.sub('', t)
    return t


db_by_norm = {}
for r in regs:
    db_by_norm.setdefault(db_norm(r['toc_title']), []).append(r)

with open(r'C:/Users/bbuny/AppData/Local/Temp/claude/c--new/7e763b8e-60b7-4dbf-b332-b8513c094a74/scratchpad/committee_md_cache/_result.json', encoding='utf-8') as f:
    extracted = json.load(f)

matched, unmatched = [], []
for session, recs in extracted.items():
    date = session[:8]
    for key, v in recs.items():
        cands = db_by_norm.get(db_norm(key))
        if cands and len(cands) == 1:
            matched.append((date, key, v['title_raw'], cands[0]['seq'], cands[0]['toc_title']))
        elif cands and len(cands) > 1:
            unmatched.append((date, key, v['title_raw'], 'AMBIGUOUS: ' + ','.join(str(c['seq']) for c in cands)))
        else:
            unmatched.append((date, key, v['title_raw'], 'NO MATCH'))

print('matched:', len(matched), 'unmatched:', len(unmatched))
with open(r'C:/Users/bbuny/AppData/Local/Temp/claude/c--new/7e763b8e-60b7-4dbf-b332-b8513c094a74/scratchpad/match_report.txt', 'w', encoding='utf-8') as f:
    f.write(f'=== MATCHED ({len(matched)}) ===\n')
    for row in matched:
        f.write('\t'.join(str(x) for x in row) + '\n')
    f.write(f'\n=== UNMATCHED ({len(unmatched)}) ===\n')
    for row in unmatched:
        f.write('\t'.join(str(x) for x in row) + '\n')
