import json
import os
import sys

import fitz

PDF_PATH = "규정집(2026.07.11).pdf"
IN_PATH = "pipeline/output/regulations_with_tables.json"
OUT_PATH = "pipeline/output/regulations_with_files.json"
FORMS_DIR = "app/static/forms"


def main():
    doc = fitz.open(PDF_PATH)
    with open(IN_PATH, encoding='utf-8') as f:
        data = json.load(f)

    os.makedirs(FORMS_DIR, exist_ok=True)

    count = 0
    skipped = 0
    for r in data:
        for ordinal, att in enumerate(r.get('attachments', [])):
            if not att.get('start_page') or not att.get('end_page'):
                skipped += 1
                continue

            start = att['start_page'] - 1
            end = att['end_page'] - 1

            sub = fitz.open()
            sub.insert_pdf(doc, from_page=start, to_page=end)

            fname = f"reg{r['seq']}_att{ordinal}.pdf"
            sub.save(os.path.join(FORMS_DIR, fname))
            sub.close()

            att['file_url'] = f"/forms/{fname}"
            count += 1

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'{count}개 파일 추출 완료, {skipped}개 건너뜀 -> {FORMS_DIR}', file=sys.stderr)


if __name__ == '__main__':
    main()
