import hashlib
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))
from extract_committee_archive import (
    BASE, list_sessions, list_stage_dirs, split_blocks, normalize_title, session_date,
)

CACHE_DIR = r'C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad\committee_md_cache'
os.makedirs(CACHE_DIR, exist_ok=True)


def kordoc_convert(src_path):
    """Converts one hwp/hwpx to markdown via kordoc, caching by a safe
    filename so re-runs don't reconvert. Returns the markdown text, or None
    if kordoc fails (a handful of files in this archive are corrupt/
    password-protected/non-hwp-despite-extension - skip those rather than
    aborting the whole run)."""
    safe = hashlib.md5(src_path.encode('utf-8')).hexdigest() + '.md'
    out_path = os.path.join(CACHE_DIR, safe)
    if not os.path.exists(out_path):
        try:
            subprocess.run(
                ['npx', '--yes', '--package', 'kordoc', '--package', 'pdfjs-dist',
                 'kordoc', src_path, '-o', out_path, '--silent'],
                capture_output=True, timeout=120, shell=True,
            )
        except Exception:
            return None
    if not os.path.exists(out_path):
        return None
    with open(out_path, encoding='utf-8') as f:
        return f.read()


def process_session(session_name, verbose=False):
    session_path = os.path.join(BASE, session_name)
    records = {}  # normalized_title -> dict(title, content, stage, file)
    for rank, stage_name, stage_path in list_stage_dirs(session_path):
        for fn in sorted(os.listdir(stage_path)):
            if not fn.lower().endswith(('.hwp', '.hwpx')):
                continue
            fp = os.path.join(stage_path, fn)
            if not os.path.isfile(fp):
                continue
            md = kordoc_convert(fp)
            if md is None:
                if verbose:
                    print(f'  [skip: convert failed] {stage_name}/{fn}')
                continue
            blocks = split_blocks(md)
            for title, content in blocks:
                if not content.strip():
                    continue
                key = normalize_title(title)
                if not key:
                    continue
                records[key] = {
                    'title_raw': title,
                    'content': content,
                    'stage': stage_name,
                    'file': fn,
                }
    return records


PENDING_SESSIONS = {'20262000(규정심의 91회)'}  # not yet finalized as of this archive snapshot

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sessions = [s for s in list_sessions() if s not in PENDING_SESSIONS] if not target else [target]
    result_path = os.path.join(CACHE_DIR, '_result.json')
    all_out = {}
    if os.path.exists(result_path):
        with open(result_path, encoding='utf-8') as f:
            all_out = json.load(f)
    for s in sessions:
        print(f'=== {s} ===', flush=True)
        recs = process_session(s, verbose=True)
        all_out[s] = recs
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(all_out, f, ensure_ascii=False, indent=2)
        for k, v in recs.items():
            print(f'  {k}  <-  [{v["stage"]}] {v["file"]}', flush=True)
    print('ALL DONE', flush=True)
