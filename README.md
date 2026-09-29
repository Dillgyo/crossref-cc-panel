# crossref-cc-panel

Crossref 공개 데이터 파일(Public Data File) 네 개 시점에서 CC 라이선스 메타데이터를 추출하고, 동일 DOI 코호트의 기재 상태 변화를 추적하는 분석 코드이다.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23019543.svg)](https://doi.org/10.5281/zenodo.23019543)

논문: (게재 확정 후 서지사항 기재)
저자: 이하형 (Lee, Hahyeong) — [ORCID 0009-0005-5282-8584](https://orcid.org/0009-0005-5282-8584), Hanyang Women's University Library
보존본: [10.5281/zenodo.23019543](https://doi.org/10.5281/zenodo.23019543) (Zenodo, 모든 판본을 가리키는 DOI)

> **정리 중** — 논문 게재 시점에 이 문단을 삭제하고 서지사항을 적는다. 그때까지 각 스크립트를 다시 실행하여 논문 수치와 대조한다.

---

## 1. 이 저장소의 범위

담는 것은 원본 tar에서 시작해 논문의 표와 그림에 이르는 처리 코드, 그리고 분석에 사용한 저널 목록과 외부 조회 결과이다.

담지 않는 것은 원본 데이터와 중간 산출물이다. Crossref 공개 데이터 파일은 연도판마다 수백 GB이고 중간 parquet도 그에 준하는 규모여서 저장소에 올릴 수 없다. 원본은 Crossref가 DOI를 붙여 공개 배포하므로 누구나 같은 파일을 내려받을 수 있다(3절).

Crossref는 매년 새 연도판을 발행하고 기존 연도판을 수정하지 않는다. 따라서 3절에 적은 DOI의 파일을 내려받으면 원본은 동일하다. 다만 DOAJ 목록과 Crossref REST API는 시점에 따라 달라지므로, 이 두 가지에 의존하는 부분은 6절의 유의사항을 따른다.

## 2. 실행 환경

| 항목 | 값 |
|---|---|
| Python | 3.13.7 |
| 주요 패키지 | duckdb 1.5.2, pandas 2.3.2, matplotlib 3.9.2, pyarrow |
| 운영체제 | Windows 11 |
| CPU | AMD Ryzen 7 5700G (8코어 16스레드) |
| RAM | 32 GB |
| 저장장치 | NVMe SSD 2 TB (SK hynix Platinum P31) |
| GPU | 사용하지 않는다 |
| 소요 시간 | 기록하지 않았다 (아래 참고) |

```bash
pip install -r requirements.txt
```

전체 소요 시간은 기록해 두지 않았다. 추출 단계는 `01_extract.py`에 `--limit 300`을 붙이면 앞쪽 300개 파일만 처리하고 전체 처리 시간을 추정해 출력하므로, 자신의 환경에서 먼저 재어 보기를 권한다.

DuckDB는 스크립트에 따라 메모리 한도를 4–6 GB, 스레드를 4개로 두고, 임시 폴더를 SSD의 `_tmp`에 지정하여 실행하였다. 스레드 수는 코어 수보다 적게 설정한 값이므로, 더 늘리면 시간이 줄어들 수 있다. RAM이 더 작은 환경에서도 메모리 한도를 낮추면 동작하나 시간이 늘어난다.

### CC 기재 판정 규칙

판정은 별도 단계로 분리되어 있지 않고, 이를 필요로 하는 각 스크립트의 SQL에 같은 조건절로 들어가 있다.

```sql
url ILIKE '%creativecommons.org%'
  AND coalesce(content_version, '') IN ('vor', 'am', 'unspecified')
```

`tdm`은 제외한다. 이 조건을 바꾸면 논문의 모든 수치가 달라지므로, 재현 시에는 스크립트별로 이 조건이 동일한지 확인한다. `tdm`을 포함한 경우와 `unspecified`를 제외한 경우의 민감도는 보충자료 표 S3에 있다.

### 전자우편 환경 변수

Crossref REST API와 Unpaywall API를 호출하는 스크립트는 연락용 전자우편이 필요하다. Crossref는 polite pool 사용을 위해 권장하고, Unpaywall은 `email` 파라미터를 필수로 요구한다. 환경 변수로 지정한다.

```
set CROSSREF_MAILTO=you@example.org        (Windows)
export CROSSREF_MAILTO=you@example.org     (Linux/macOS)
```

## 3. 데이터 준비

### 3.1 Crossref 공개 데이터 파일

네 개 연도판을 내려받는다. 아래 DOI가 이 연구가 사용한 판을 가리킨다.

| 본문 표기 | 등록된 데이터셋 명칭 | DOI | 형식 | 크기 |
|---|---|---|---|---|
| 2023년판 | April 2023 Public Data File | 10.13003/8wx5k | `.json.gz` (items 배열) | 173.1 GB |
| 2024년판 | April 2024 Public Data File | 10.13003/849J5WP | `.json.gz` (items 배열) | 197.6 GB |
| 2025년판 | March 2025 Public Data File from Crossref | 10.13003/87bfgcee6g | `.jsonl.gz` (한 줄 1건) | 183.4 GB |
| 2026년판 | March 2026 Public Data File from Crossref | 10.13003/nggf-vt1j | `.jsonl.gz` (한 줄 1건) | 207.8 GB |

크기는 1 GB를 1,024 MB로 계산한 값이다. 2025년판이 2024년판보다 작은 것은 내려받기가 중단된 결과가 아니라, 이 시점에 파일 형식이 items 배열을 담은 `.json.gz`에서 레코드당 한 줄인 `.jsonl.gz`로 바뀐 데 따른 것이다.

추출 코드는 두 형식을 모두 처리한다. 본문에서 각 연도판에 붙인 연월은 공식 명칭의 발행월이 아니라, 추출 집합에서 관찰된 `created` 최댓값을 가리킨다(논문 3.1절).

내려받은 파일이 올바른 판인지는 추출 후 `02_check_snapshot.py`가 출력하는 값으로 확인할 수 있다.

| 본문 표기 | `created` 최댓값 | `deposited` 최댓값 |
|---|---|---|
| 2023년판 | 2023-03-31 | 2023-04-02 |
| 2024년판 | 2024-04-30 | 2024-05-02 |
| 2025년판 | 2025-02-28 | 2025-03-02 |
| 2026년판 | 2026-02-28 | 2026-03-02 |

### 3.2 디스크 용량

원본 tar와 parquet 중간물을 함께 보관하려면 다음이 필요하다.

| 항목 | 용량 |
|---|---|
| 원본 tar 4개 합계 | 761.9 GB |
| parquet 중간물 4시점 합계 | 25.2 GB |
| 합계 | 787.1 GB |

parquet은 tar의 3.3%에 그친다. 추출 단계에서 journal-article·ISSN 보유·출판연도 2000년 이상으로 거르고 필요한 열만 남기기 때문이다.

용량을 줄이려면 한 연도판을 추출한 뒤 해당 tar를 지우고 다음 판을 내려받는다. 이 경우 동시에 필요한 공간은 가장 큰 tar 하나(207.8 GB)와 parquet 전체(25.2 GB)를 합한 233.0 GB다. 다만 `verify/raw_check.py`와 `verify/raw_trace.py`는 원본 tar를 다시 훑으므로, 그 검증까지 재현하려면 tar를 남겨 두어야 한다.

### 3.3 DOAJ 저널 목록

DOAJ 2026년 8월 17일판 공개 덤프에서 출발한다. 덤프 자체는 재배포하지 않는다.

| 파일 | SHA-256 |
|---|---|
| `doaj_journalcsv_20260817_2320_utf8.csv` (원본 덤프, 저장소에 없음) | `b30e555ae817d34db618c696122a6e76f90cca8b3827648b653c4a5ca048782b` |
| `data/doaj_panel_journals.csv` (필터 적용 결과) | `76ef25e1ec2a95828804e2bf558fcbbf9d3a0b251f9cced59102fb824db8632e` |

`data/doaj_panel_journals.csv`는 분석 모집단 13,806종이다. 열은 저널명, 인쇄판 ISSN, 온라인판 ISSN, 출판사, 저널 라이선스, DOAJ 등재일시, OA 시작연도이며, 원본 덤프에 다음 세 필터를 적용한 결과이다.

- 기록된 라이선스가 **모두** CC 계열인 저널만 남긴다. CC와 그 밖의 라이선스를 함께 기록한 저널 24종은 빠진다(23,325 → 23,149).
- DOAJ 등재일이 2021년 12월 31일 이전인 저널만 남긴다. 관찰 시작 시점보다 충분히 앞서 등재된 저널로 한정하기 위한 것이다(23,149 → 14,030).
- OA 시작연도가 DOAJ 등재연도보다 늦게 기록된 저널 224종을 제외한다(14,030 → 13,806). 이들을 포함한 민감도 분석은 논문 4.9절에 있다.

`data/doaj_excluded_224.csv`는 위 마지막 단계에서 제외한 224종의 목록이다. `09_excluded_224.py`가 차집합으로 복원하여 만든다.

DOAJ 덤프는 날짜별로 보존되지 않으므로, 논문의 수치를 재현하려면 `data/`의 파일을 그대로 사용한다.

### 3.4 외부 조회 결과

Crossref REST API와 Unpaywall API의 응답은 조회 시점에 따라 달라진다. 논문에 보고한 값을 재현하려면 저장소에 포함된 다음 파일을 사용한다. 다시 조회하면 같은 값이 나오지 않는다.

| 파일 | 내용 |
|---|---|
| `data/external_check.csv` | 미기재 표본 500건의 Unpaywall 응답 |
| `data/external_positive.csv` | 기재 표본 500건의 Unpaywall 응답 |
| `data/unpaywall_requery.jsonl` | 미기재 표본 재조회 원본 (2026년 9월) |
| `data/missing_dois.csv` | 추출되지 않은 DOI의 원인 분류 |

## 4. 실행 순서

### 4.1 추출과 패널 구성

| 스크립트 | 하는 일 |
|---|---|
| `01_extract.py` | tar를 스트리밍으로 읽어 `works`·`licenses` parquet 생성. 거르는 기준은 journal-article, ISSN 있음, 출판연도 2000년 이상 |
| `02_check_snapshot.py` | 추출 결과 점검. 행 수, 중복 DOI, 빈 값 비율, `created`·`deposited` 최댓값, content-version 분포, CC 기재 비율 |
| `03_base_2023.py` | 2023년 단면 집계. DOAJ 저널 대조와 저널별 하한연도 적용으로 기준 코호트를 정한다 |
| `04_state_panel.py` | 네 시점을 이어 붙여 `state_panel.parquet` 생성. 2023년판에 있고 2026년판까지 남은 DOI가 최종 패널이다 |

`01_extract.py` 실행 예:

```
python 01_extract.py D:\crossref\April_2023_Public_Data_File_from_Crossref.tar 2023 D:\crossref\parquet
```

앞쪽 몇 개 파일로 먼저 시험하려면 `--limit 300`을 붙인다. 전체 처리 시간을 추정해 출력한다.

`state_panel.parquet`의 열 구성:

| 열 | 뜻 |
|---|---|
| `doi` | 소문자로 정규화한 DOI |
| `member`, `publisher`, `container_title` | 회원사 번호, 출판사명, 저널명 |
| `pub_year` | 출판연도 |
| `created` | Crossref 최초 등록 일시 |
| `cc23`–`cc26` | 각 시점 CC 기재 여부 (1/0) |
| `dep23`–`dep26` | 각 시점 `deposited` 일시 |
| `in24`–`in26` | 해당 시점 파일에 레코드가 있었는지 (1/0) |

`cc`와 `in`을 분리한 것이 이 패널의 핵심이다. 라이선스 기재가 사라진 것과 레코드 자체가 사라진 것은 다른 현상이므로 구분하여 집계한다.

### 4.2 논문 산출물

| 스크립트 | 논문의 어느 부분 |
|---|---|
| `05_tables.py` | 본문 표 1–9 전부, 그림 1–3의 작도용 데이터, 4.8절 라이선스 시작일 |
| `06_figures.py` | `05_tables.py`가 저장한 CSV로 그림 1–3을 그린다 |
| `07_supplement.py` | 보충자료 표 S1–S5, 본문 4.4·4.5·4.9절 |
| `08_unpaywall.py` | 보충자료 표 S6, 본문 5.4절 |
| `09_excluded_224.py` | 제외한 224종을 복원하고 표 S3의 해당 행을 재계산. `data/doaj_excluded_224.csv`를 만든다 |
| `10_member_stable.py` | member가 두 연도판에서 같은 부분집합으로 4.4절 집중도를 다시 계산 |

`05`–`10`은 논문에 실린 값을 스크립트 안의 `EXPECTED`에 담고 있으며, 계산 결과마다 `일치` 또는 `불일치 (원고 …)`를 함께 출력한다. 재현 여부를 출력만 보고 판단할 수 있다.

두 항목은 다음 규칙을 따른다.

- 그림 2는 라이선스가 **처음 확인된** 스냅숏의 `deposited` 월로 집계한다. 논문 그림 2의 캡션에 기술된 규칙이다.
- 표 6과 그림 3은 저널을 **DOAJ 저널 단위**로 묶는다. 논문 3.2절이 저널 연결을 ISSN으로 수행한다고 밝힌 것과 일치시키기 위한 것이다. 대조를 위해 레코드의 `container_title`로 묶은 값도 함께 출력한다.

경로는 환경 변수로 덮어쓸 수 있다.

```
set CROSSREF_ROOT=E:\crossref
set CROSSREF_PARQUET=E:\crossref\parquet
set CROSSREF_DOAJ=E:\crossref-cc-panel\data\doaj_panel_journals.csv
```

`09_excluded_224.py`는 원본 DOAJ 덤프가 있어야 한다. `set CROSSREF_DOAJ_DUMP=D:\doaj_journalcsv_20260817_2320_utf8.csv`로 지정한다.

### 4.3 verify/

논문의 수치를 재현하는 데 필수는 아니다. 분석 과정과 심사 대응에서 개별 항목을 확인하려고 그때그때 쓴 코드 59개이며, 순서대로 실행하는 파이프라인이 아니다. 본체와 달리 경로가 하드코딩되어 있고 입력 파일을 가린다. 파일별 설명은 `verify/README.md`에 있다.

## 5. 폴더 구조

```
crossref-cc-panel/
├── README.md
├── requirements.txt
├── CITATION.cff
├── LICENSE
├── .gitignore
├── .gitattributes
├── 01_extract.py            추출
├── 02_check_snapshot.py     추출 점검
├── 03_base_2023.py          기준 코호트
├── 04_state_panel.py        패널 구성
├── 05_tables.py             본문 표 1–9, 그림 데이터
├── 06_figures.py            그림 1–3
├── 07_supplement.py         표 S1–S5
├── 08_unpaywall.py          표 S6
├── 09_excluded_224.py       제외 224종
├── 10_member_stable.py      member 유지 집합
├── verify/                  점검 코드 59개 + README.md
└── data/
    ├── doaj_panel_journals.csv   분석 모집단 13,806종
    ├── doaj_excluded_224.csv     제외한 224종
    ├── external_check.csv        Unpaywall 미기재 표본 500건
    ├── external_positive.csv     Unpaywall 기재 표본 500건
    ├── unpaywall_requery.jsonl   재조회 원본
    └── missing_dois.csv          추출되지 않은 DOI의 원인 분류
```

## 6. 재현 시 유의사항

`01`–`04`와 `verify/`는 경로가 코드에 하드코딩되어 있다. `D:\crossref\...` 형태로 들어간 곳을 자신의 환경에 맞게 바꿔야 한다. `05`–`10`은 환경 변수로 덮어쓸 수 있다(4.2절).

DOAJ 덤프는 시점에 따라 내용이 바뀐다. `data/doaj_panel_journals.csv`는 2026년 8월 17일판에서 만든 것이므로, 새 덤프로 다시 만들면 저널 수와 하한 연도가 달라진다.

Crossref REST API와 Unpaywall API를 쓰는 스크립트는 실행 시점의 응답을 받는다. 공개 데이터 파일은 고정되어 있으나 API는 계속 갱신되므로, 논문에 보고한 API 대조 수치와 같은 값이 나오지는 않는다. 이 점은 논문 5.4절에 한계로 적었고, 논문의 값을 재현하려면 `data/`에 넣어 둔 응답 파일을 쓴다(3.4절).

## 7. 라이선스

코드는 MIT 라이선스로 공개한다.

Crossref 공개 데이터 파일과 DOAJ 덤프 자체는 각 배포처의 조건을 따른다. 이 저장소는 원본 데이터를 재배포하지 않는다.
