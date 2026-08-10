# 규정관리시스템 화면/데이터 구조 명세서

## 0. 분석 대상 및 원칙

분석 대상: 총신대학교 규정관리시스템(LKMS3 기반 상용 패키지)의 화면 소스 2건
- `main.jsp` (로그인 상태 인지 버전 — 상단에 `[로그인]` 링크, 좌측 카테고리 트리 + 우측 iframe(`nvFrm`)으로 목록 화면을 내장하는 구조)
- `regulationListCom.jsp` (위 iframe에 로드되는 규정 목록 그리드 화면)

여기에 이전 분석 단계에서 이미 확보한 `main.jsp`(비로그인/구버전, 최근 제·개정·공지사항 위주의 랜딩페이지)의 구조도 함께 반영한다.

이 문서는 **코드 이식이 아니라 정보 구조 추출**이 목적이므로:
- ExtJS/DWR/jQuery 관련 구현 세부사항(트리패널 옵션, 그리드 렌더러 등)은 "이런 기능이 있었다"는 사실만 남기고 구현 방식은 기술하지 않는다.
- `regulationView.jsp`, `regul_board_noForm.jsp`, `regulationMainSch.jsp`, `pdsMain.jsp`, `statisticsPopMain.jsp`, `adminMain.jsp` 등은 **소스를 직접 확보하지 못했고 참조(호출)만 확인된 화면**이다. 이런 화면은 "무엇을 받는지"까지만 적고, 내부 레이아웃은 추정하지 않는다.

---

## 1. 화면 목록과 각 화면의 역할

| 화면(파일) | 역할 | 소스 확보 여부 |
|---|---|---|
| `main.jsp` (구버전) | 비로그인 랜딩 페이지. 검색창 + 카테고리/부서 트리 + "최근 제·개정 정보" 목록 + "공지사항" 목록 + 방문자 통계(Today/Total) | 확보 |
| `main.jsp` (신버전) | 로그인 인지 랜딩 페이지. 상단 검색창 + 가나다/개정일 검색 탭 + 좌측 카테고리 트리 + 우측 iframe에 목록 화면을 내장 | 확보 |
| `regulationListCom.jsp` | 트리에서 카테고리/부서 폴더를 선택했을 때 우측 iframe에 표시되는 **규정 목록 그리드** 화면. 자체 검색(규정명/규정내용)과 페이징 보유 | 확보 |
| `regulationView.jsp` | 조문형(구조화된) 규정의 **상세 보기** 화면. `Bookid` 파라미터로 특정 규정을 연다 | 미확보 (호출부만 확인) |
| `regul_board_noForm.jsp` | 첨부파일/게시판 형태로 등록된 규정(`noFormYn=Y`)의 **상세 보기** 화면 | 미확보 (호출부만 확인) |
| `regulationMainSch.jsp` | 통합검색(`ptype=M`) 결과를 표시하는 화면으로 추정 (main.jsp가 검색 모드일 때 iframe에 로드) | 미확보 |
| `getNodes.jsp` | 좌측 트리의 노드 데이터를 내려주는 **AJAX 데이터 엔드포인트** (화면 아님) | 확보 (호출 파라미터만) |
| `getData.jsp` | 목록 그리드의 행 데이터를 내려주는 **AJAX 데이터 엔드포인트** (화면 아님) | 확보 (호출 파라미터만) |
| `pdsMain.jsp` | 공지사항 게시판 화면 | 미확보 (호출부만 확인) |
| `login.jsp` / `logout.jsp` | 로그인/로그아웃 처리 | 미확보 |
| `statisticsPopMain.jsp` | 통계 팝업 (메뉴 주석에만 등장, 실제 메뉴 항목으로는 노출되지 않음) | 미확보 |
| `adminMain.jsp` | 관리자(규정 등록/수정) 백오피스, 별도 로그인 체계로 추정 | 미확보, 범위 밖으로 간주 |

**신버전 `main.jsp`의 화면 배치**: 좌측 `categoryW`(트리 패널) + 우측 `mainContent`(iframe `nvFrm`). 트리에서 무엇을 클릭하든 결과는 항상 이 iframe 안에서 바뀐다 (풀 페이지 이동이 아님). 구버전 `main.jsp`는 반대로 트리/검색/최근목록/공지사항이 한 페이지 안에 나열되어 있고, 클릭 시 풀 페이지가 이동한다. → **동일 시스템의 두 가지 화면 모드(구형 풀페이지형 vs 신형 iframe형)가 공존**하는 것으로 보인다.

---

## 2. 좌측 트리의 노드 종류와 클릭 시 동작

### 2.1 트리 자체의 종류 (categoryTab으로 전환)

| key 값 | 트리 루트 제목 | stateCd | 의미 |
|---|---|---|---|
| `htree` | 총신대학교 | 현행 | 카테고리별 분류 트리 (기본값) |
| `dtree` | 부서별 규정 | 현행 | 담당 부서별 분류 트리 |
| `ctree` | 폐지 규정 | 폐지 | 폐지된 규정만 모은 트리 (상단 "폐지" 토글로 전환) |
| `fav` | 사용자님의 규정 | 현행 | 즐겨찾기(개인화) 트리 — 로그인 필요로 추정 |

- `카테고리별` / `부서별` 탭 클릭 → 트리 자체를 `htree` ↔ `dtree`로 교체 (같은 패널 안에서 재조회)
- 우측 상단 "폐지" 버튼(`changeRegulType('CT')`) 클릭 → 트리 모드가 아니라 **페이지 전체가 폐지 규정 모드로 전환** (Menuid/bookcd/selectedPageId/rType을 바꿔 재요청). 즉 카테고리·부서 탭 전환과는 층위가 다른, 상위 토글이다.
- 트리 데이터는 `getNodes.jsp`에서 `stateCd`, `key`, `bookcd` 파라미터로 조회한다.

### 2.2 노드 종류(`nodeKind`/`cls`)와 속성

트리 노드는 속성으로 `bookId`, `catId`, `noFormYn`, `cls`(노드 종류)를 가진다. `cls` 값:

- `folder` — 카테고리(또는 부서) 폴더 노드. 하위에 폴더 또는 규정 문서를 포함할 수 있다.
- `doc` / `file` / `fileIng` — 실제 규정 문서(리프 노드). 세 종류의 구분 기준은 소스만으로는 알 수 없으나(진행중 문서/일반 문서/첨부형 문서 구분으로 추정), 클릭 동작은 동일하게 처리된다.

### 2.3 클릭 시 동작

- **루트 노드 클릭**: `bookcd=key`(htree/dtree/ctree/fav), `catid=null`, `dept='0'`로 설정 → `regulationListCom.jsp`를 iframe(`nvFrm`)에 로드 (해당 트리 전체의 최상위 목록을 보여주는 것으로 추정)
- **`folder` 노드 클릭**:
  - 현재 활성 탭이 `category`면 → `catid = node.catId`
  - 현재 활성 탭이 `dept`면 → `dept = node.id`
  - 공통으로 `bookcd = key` 설정 후 `regulationListCom.jsp`를 iframe에 로드 (해당 폴더에 속한 규정 목록 표시)
- **`doc`/`file`/`fileIng` 노드 클릭**: `Bookid = node.bookId` 설정 →
  - `noFormYn == 'Y'` → `regul_board_noForm.jsp` 로드 (첨부/게시판형 규정)
  - 그 외 → `regulationView.jsp` 로드 (조문형 규정 상세)
  - 둘 다 iframe(`nvFrm`)에 로드됨

---

## 3. 목록 그리드에 표시되는 컬럼과 의미

`regulationListCom.jsp`의 그리드는 다음 컬럼을 화면에 표시한다:

| 컬럼 헤더 | 데이터 필드 | 의미 | 비고 |
|---|---|---|---|
| 번호 | `ordsort` | 목록 내 표시 순번 | 정수 정렬 |
| 규정코드 | `bookcd` | 규정이 속한 트리/분류 코드 (예: `A1`) | |
| 규정명 | `title` | 규정 제목 | 클릭 시 상세화면 이동, 기본 정렬 기준(DESC) |
| 제·개정 | `revcd` | 해당 이력 행이 "제정"인지 "개정"인지 구분하는 코드 | 한 규정당 여러 행(이력)이 존재할 수 있음을 시사 |
| 제·개정일 | `startdt` | 그 제정/개정이 시행된 날짜 | |
| 담당부서 | `deptname` | 규정을 관리하는 부서명 | **예외 처리 있음**: 특정 규정 3건(원본 문서 ID `obookid` 하드코딩: 산학협력단 정관, 법인 정관시행세칙, 법인 경조금 지급 규정, 총장후보추천위원회 시행세칙)은 원래 저장된 부서명 대신 "산학협력단" 또는 "법인사무국"으로 화면에서 강제 치환되어 표시됨 — 이는 데이터 정합성 문제를 화면단에서 임시로 땜질한 것으로 보이며, 재구현 시에는 **데이터 자체를 올바른 부서로 정정**하는 편이 바람직함 |

그리드 내부적으로는 화면에 보이지 않는 필드도 함께 내려받는다: `bookid`(상세화면 이동용 내부 ID), `obookid`(원본/정본 문서 ID — 위 부서명 예외 처리에 사용), `catid`, `bookcode`, `revcha`(개정 차수로 추정), `statecd`(현행/폐지 상태 코드), `noformyn`(첨부형 여부), `statehistoryid`(이력 행 ID).

행 클릭 시: `bookid`, `noformyn`을 읽어 §2.3과 동일한 규칙으로 `regulationView.jsp` 또는 `regul_board_noForm.jsp`로 이동.

그리드는 서버 페이징(`pageSize=15`)과 컬럼별 서버 정렬(`remoteSort`)을 사용하며, 데이터는 `getData.jsp`에서 받아온다.

---

## 4. 검색 옵션과 필터 조건

시스템 안에 검색 UI가 **세 군데**에 존재하며, 범위와 대상이 서로 다르다.

### 4.1 메인 화면 상단 통합검색 (`main.jsp`)
- 검색 범위 드롭다운: `규정명`(T) / `규정내용`(TB) / `규정번호`(N)
- 텍스트 입력 1개
- 제출 시 `Schtxtb`(검색어), `Smenu`(검색범위), `ptype=M`(통합검색 모드)을 담아 이동 — 트리/카테고리 범위와 무관하게 **전체 규정 대상 검색**으로 추정

### 4.2 목록 화면 내 검색 (`regulationListCom.jsp`)
- 검색 범위 드롭다운: `규정명`(1) / `규정내용`(2) — 상단 통합검색과 유사하지만 코드값 체계가 다름(T/TB/N vs 1/2)
- 텍스트 입력 1개
- 현재 선택된 `catid`/`dept`/`mtype`(트리 종류)는 그대로 유지한 채 `schGbn`, `schText`만 추가하여 그리드를 재조회 → **현재 카테고리/부서로 범위가 좁혀진 검색**

### 4.3 가나다순 / 개정일순 탭 (`main.jsp` 상단)
- `가나다 검색` 탭, `개정일 검색` 탭 — 클릭 시 `schMenu`(`abc`/`date`)와 `tabs`(`tabAbc`/`tabDate`) 값을 담아 이동
- 즐겨찾기(`즐겨찾기` 링크/버튼) — `rType=FAV`, `tabs=tabFav`로 이동. 좌측 트리의 `fav` 키와 대응되는 것으로 보임
- 이 세 가지가 정확히 어떤 화면(목록 컬럼/정렬)으로 귀결되는지는 `regulationMain.jsp`/`regulationMainSch.jsp` 소스를 확보하지 못해 **컬럼 구성까지는 확인 불가** — 다만 "규정 목록을 가나다순으로 재정렬해서 보여준다", "개정일 기준으로 재정렬해서 보여준다", "로그인 사용자가 즐겨찾기한 규정만 모아 보여준다"는 기능 의도는 명확함

### 4.4 폐지 규정 필터
- §2.1의 "폐지" 토글은 검색이 아니라 **상태 필터**(현행 vs 폐지)이며, 텍스트 검색과 조합해서 쓸 수 있는 구조(둘 다 최종적으로 `getData.jsp`/`getNodes.jsp`의 파라미터로 흡수됨)

---

## 5. 화면 간 이동 시 넘기는 파라미터

### 5.1 메인 메뉴 이동 (상단 lnb, 풀 페이지 이동)
`Menuid`, `bookcd`(메뉴별 코드: 규정=A1, 최근제·개정=A2, 서식=A3, 폐지규정=A6, 공지·게시=PDS), `selectedPageId`, `rType`(HT=현행/CT=폐지)

### 5.2 메인 → 목록 (iframe 로드, `regulationListCom.jsp`)
- 트리 루트 클릭: `bookcd`(=트리 key), `catid=null`, `dept='0'`
- 트리 폴더 클릭: `catid`(카테고리 탭일 때) 또는 `dept`(부서 탭일 때), `bookcd`(=트리 key)
- 항상 `target=nvFrm`으로 iframe 안에서만 갱신

### 5.3 목록 → 상세
- `Bookid`
- 분기: `noformyn == 'Y'` → `regul_board_noForm.jsp`, 그 외 → `regulationView.jsp`

### 5.4 데이터 엔드포인트 호출 파라미터
- `getNodes.jsp` (트리 데이터): `stateCd`(현행/폐지), `key`(htree/dtree/ctree/fav), `bookcd`
- `getData.jsp` (그리드 데이터): `mtype`(트리 종류), `catid`, `dept`, `schGbn`, `schText`, `start`, `limit`(페이징), 응답은 `{result: [...], total: N}` 형태

### 5.5 통합검색 / 가나다 / 개정일 / 즐겨찾기 이동 (모두 `regulationMain.jsp` 계열로 이동)
- 통합검색: `Schtxtb`, `Smenu`, `ptype=M`
- 가나다: `schMenu=abc`, `tabs=tabAbc`
- 개정일: `schMenu=date`, `tabs=tabDate`
- 즐겨찾기: `rType=FAV`, `tabs=tabFav`

### 5.6 (참고) 구버전 `main.jsp`에서 확인된 추가 파라미터
- 최근 제·개정 목록 클릭: `bookid`, `noFormYn` → 규정 상세로 이동 (§5.3과 동일한 분기 규칙)
- 공지사항 목록 클릭: `Bbsid`, `sMenuid`, `selectedPageId` → `pdsMain.jsp`

---

## 6. 재구현 시 참고할 점 (정보 구조 관점, 설계 제안 아님)

- 이 문서는 **"무엇이 있었는지"**를 정리한 것이며, FastAPI + SQLite + 순수 JS로 다시 만들 API/화면 구조는 별도로 설계해야 한다.
- §3의 부서명 하드코딩 예외 3건은 재구현 시 데이터를 직접 정정해서 없애는 것이 맞다 (화면 로직으로 다시 만들 필요 없음).
- `regulationView.jsp` / `regul_board_noForm.jsp` / `regulationMainSch.jsp` / `pdsMain.jsp`는 소스 미확보 상태이므로, 이 화면들의 상세 레이아웃이 필요하면 추가 소스 확보가 필요하다.
