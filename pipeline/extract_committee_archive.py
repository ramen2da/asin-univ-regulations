"""Extracts 신구조문대비표 (old/new article comparison) blocks from the
committee-meeting archive at file/11 규정/ (36 규정심의위원회 sessions,
2020-03-18 through 2026, discovered 2026-08-27).

Core idea: within one session, the SAME regulation's comparison table can
appear in multiple stage folders as it moves through approval (부서제출 →
규정심의상정 → 규정심의통과 → 교수회의 → 대학평의원회 → 최종개정), and the
wording can genuinely change between stages (committee revises what a
department proposed - see 제70회, 교육연구소 운영규정 제16조의2, changed
from "인건비" to "강사료 및 수당" between 규정심의상정 and 규정심의통과).
Rather than hand-picking one "final" folder per session (fragile - 36
sessions each name their stages differently, and some split into parallel
일반규정/학칙 tracks with different final dates), this walks EVERY numbered
stage folder in order and lets a LATER stage's version of the same
regulation overwrite an EARLIER stage's - so whatever's captured is
automatically the most-recent-available (usually the actually-approved)
wording, and a stage where the committee changed something naturally wins
over the stage before it.

A session with no numbered stage subfolders at all (e.g. 79회, 90회) is
treated as if its own root folder were the single stage.
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_daehakwon import fix_spacing_ko

BASE = r'c:\new\file\11 규정'

# Folders that hold published/compiled output, not per-item comparison
# tables - never a "stage" to parse for □ blocks.
NOT_A_STAGE_RE = re.compile(r'^(홈페이지|규정집|새 폴더)')

STAGE_RANK_RE = re.compile(r'^(\d+)(?:[-.](\d+))?')

# □ is the dominant regulation-name marker (1264 occurrences across this
# archive); ◉ is used the same way in a minority of documents (189
# occurrences, e.g. "### ◉ 학술연구비지원 규정"). Other bullet-like
# characters seen in this corpus (◆ "개정 주요골자" summary bullets, ▶
# sub-point bullets, ○○○ redaction placeholders) are NOT regulation-name
# markers and must stay excluded, or they'd each become a bogus "regulation"
# key.
BLOCK_HEADER_RE = re.compile(r'^#{0,6}\s*\*{0,2}[□◉]\s*(.+?)\*{0,2}\s*$')
MD_HEADING_STRIP_RE = re.compile(r'^#{1,6}\s*')

# The doc-level title line ("신·구조문대비표" / "신구조문대비표") that
# precedes the first □ block - not itself a regulation block.
DOC_TITLE_RE = re.compile(r'^\*{0,2}신\s*[·ㆍ]?\s*구\s*조문\s*대비표\*{0,2}$')

SUFFIX_STRIP_RE = re.compile(
    r'\s*[\(（][^()（）]*[\)）]\s*$'  # trailing (...) parenthetical
)
TRAILING_VERB_RE = re.compile(
    r'(개정|신설|폐지|수정개정|전면개정|전면개편|변경)+\s*(\(안\)|안)?\s*$'
)


def normalize_title(raw):
    """Strips session-specific suffixes ("개정(안)", "(수정개정)", trailing
    session/date parentheticals, "제N조 신구조문대비표" style prefixes) down
    to the bare regulation name, so the same regulation tracked across
    stages with slightly different □ labels still collapses to one key."""
    t = raw.strip()
    # repeatedly strip trailing parentheticals and amendment-verb suffixes -
    # some titles stack both ("학칙(69회 규정심의)", "규정 개정(안)")
    for _ in range(4):
        t2 = SUFFIX_STRIP_RE.sub('', t).strip()
        t2 = TRAILING_VERB_RE.sub('', t2).strip()
        if t2 == t:
            break
        t = t2
    t = re.sub(r'\s+', '', t)
    return t


def stage_rank(name):
    if NOT_A_STAGE_RE.match(name):
        return None
    m = STAGE_RANK_RE.match(name)
    if not m:
        return (9999, 0)  # unnumbered but not excluded ("최종개정", "규정 변경") - sorts last
    major = int(m.group(1))
    minor = int(m.group(2)) if m.group(2) else 0
    return (major, minor)


def list_stage_dirs(session_path):
    entries = []
    for name in sorted(os.listdir(session_path)):
        p = os.path.join(session_path, name)
        if not os.path.isdir(p):
            continue
        rank = stage_rank(name)
        if rank is None:
            continue
        entries.append((rank, name, p))
    entries.sort(key=lambda e: e[0])
    if not entries:
        return [((0, 0), '', session_path)]
    return entries


def split_blocks(markdown_text):
    """Splits one converted document into (title, block_text) pairs, one
    per □ regulation marker. Content before the first marker (usually just
    the "신·구조문대비표" doc title) is dropped."""
    lines = markdown_text.split('\n')
    blocks = []
    current_title = None
    current_lines = []

    def flush():
        if current_title is not None:
            blocks.append((current_title, '\n'.join(current_lines).strip()))

    for line in lines:
        s = line.strip()
        m = BLOCK_HEADER_RE.match(s)
        if m:
            flush()
            current_title = m.group(1).strip()
            current_lines = []
            continue
        if DOC_TITLE_RE.match(MD_HEADING_STRIP_RE.sub('', s)):
            continue
        if current_title is not None:
            current_lines.append(line)
    flush()
    return blocks


def list_sessions():
    return sorted(
        d for d in os.listdir(BASE)
        if d.startswith('202') and os.path.isdir(os.path.join(BASE, d))
    )


def session_date(session_name):
    return session_name[:8]
