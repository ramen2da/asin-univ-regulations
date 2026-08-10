# 아신대학교 규정정보시스템

아신대학교 규정집(PDF)을 추출해 규정 조문·개정이력·별표/서식을 검색·열람할 수 있도록 만든 웹 시스템입니다. FastAPI + SQLite + 순수 JavaScript로 구현했습니다.

## 주요 기능

- 분류 트리 / 검색(규정명·본문)을 통한 규정 열람
- 조문별 열람, 제·개정이력, 신구조문대조표(개정 전후 비교)
- 별표·서식 PDF 원문 보기
- 관리자 화면: 비밀번호 로그인 후 조문 본문 수정 → 자동으로 개정이력·비교표 생성

## 로컬 실행

```bash
python -m venv venv
venv/Scripts/pip install -r requirements.txt
venv/Scripts/python app/db.py          # DB 스키마 생성
venv/Scripts/python app/load_data.py   # 규정 데이터 적재 (pipeline/output/regulations_final_clean.json 기준)
ADMIN_PASSWORD=원하는비밀번호 venv/Scripts/python -m uvicorn main:app --app-dir app --port 8000
```

브라우저에서 `http://127.0.0.1:8000` 접속. 관리자 화면은 `/admin.html`.

`ADMIN_PASSWORD`를 설정하지 않으면 실행할 때마다 임시 비밀번호가 생성되어 서버 로그에 출력됩니다.

## PDF 추출 파이프라인

`pipeline/` 폴더의 스크립트들이 원본 규정집 PDF를 파싱해 `pipeline/output/regulations_final_clean.json`을 생성합니다 (`extract3.py` → `fix_spacing.py` → `extract_tables.py` → `extract_attachment_files.py` 순으로 사용). 원본 PDF는 저장소에 포함되어 있지 않습니다.

## 배포 (Render)

리포지토리 루트의 `render.yaml`을 사용해 Render에서 Blueprint로 배포할 수 있습니다. 배포 시 `ADMIN_PASSWORD` 환경변수를 Render 대시보드에서 직접 설정해야 합니다 (저장소에는 포함되어 있지 않음).
