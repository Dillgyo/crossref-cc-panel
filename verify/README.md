# verify/

논문의 수치를 재현하는 데 필수는 아니다. 분석 과정과 심사 대응에서 개별 항목을
확인하려고 그때그때 쓴 코드이며, 순서대로 실행하는 파이프라인이 아니다.
본체 `01`–`10`과 달리 경로가 하드코딩되어 있고 입력 파일을 가리는 경우가 있다.

설명은 각 파일의 독스트링, 첫 주석, 또는 출력 문구에서 뽑았다.

| 파일 | 하는 일 |
|---|---|
| `aip_check.py` | ── A. 1001 패턴의 출판사 분포 ── |
| `audit_calc.py` | (설명문 없음) 1. 2783-5502 저널의 누락 원인 / API DOI 예시: |
| `burst.py` | (설명문 없음) 1. Wolters Kluwer 보강분의 재등록 월 (2024 스냅숏 기준 / 2. AIP 보강분의 재등록 월 (2026 스냅숏 기준 |
| `calc_all.py` | (설명문 없음) CROSSREF_MAILTO / url ILIKE '%creativecommons.org%' AND coalesce(content_ver |
| `ci.py` | (설명문 없음) 외부 검증 표본의 신뢰구간 (Wilson 95% / 미기재 표본 CC 확인 |
| `country.py` | 원본에서 국가·언어 열 이름 찾기 |
| `decomp.py` | (설명문 없음) 신규 실제 {a_new:.3f} / 과거 실제 {a_old:.3f} / 과거구성 적용 {cf_old:.3 / 과거 구성 기준] 구성 효과 {a_new-cf_old:.3f}%p + 출판사 내 효과 {cf_old-a_ |
| `dep_check.py` | deposited 역행 148,327건의 원인 확인 |
| `dep_check2.py` | deposited 역행이 어느 시점에서 발생했는지, 오프셋이 정확히 몇 시간인지 확인 |
| `distinct_cc.py` | (설명문 없음) |
| `dup_check.py` | (설명문 없음) 중복 DOI |
| `external.py` | (설명문 없음) CROSSREF_MAILTO / 건 (2023·2026 모두 미기재 |
| `external_pos.py` | (설명문 없음) CROSSREF_MAILTO / 건 (Crossref에 CC 기재됨 |
| `figdata.py` | (설명문 없음) fig1_year_by_snapshot / fig2_monthly_backfill |
| `final3.py` | (설명문 없음) 1. 출판사별 기재 시작 연도 (2026 스냅숏 기준, 미기재 1만 건 이상 / 2-1. 보강된 논문의 CC 종류 분포 |
| `fixcheck.py` | (설명문 없음) A. 4.1절 100건의 내역 / B. 집중도: 상위 5개 출판사 미기재 실측 |
| `four.py` | (설명문 없음) 의심 DOI가 우리 추출에 있는지 |
| `frontiers.py` | (설명문 없음) 1. Frontiers 비어 있는 논문의 연도 분포 / 2. 비어 있는 논문에 라이선스가 아예 없는지, 다른 형태로 있는지 |
| `issn_both.py` | (설명문 없음) CROSSREF_MAILTO / total-results |
| `m9794.py` | (설명문 없음) member 9794 레코드 예시 - 2026 / ISSN이 빈 레코드는 애초에 추출되지 않았으므로, 전체 규모 확인 |
| `member_check.py` | (설명문 없음) |
| `missing_all.py` | (설명문 없음) CROSSREF_MAILTO / 종 — 이어서 진행 |
| `missing_check.py` | (설명문 없음) CROSSREF_MAILTO / 미확인 저널 |
| `missing_dois.py` | (설명문 없음) CROSSREF_MAILTO / 3_조건충족논문존재 |
| `new_and_start.py` | (설명문 없음) 1. 신규 등록분 전체 / 2. 출판사별: 옛 논문 보강률 vs 신규분 기재율 |
| `one_journal.py` | (설명문 없음) |
| `panel185.py` | (설명문 없음) 패널 내 중간 부재 185건의 원인 |
| `panel_audit.py` | 패널 무결성과 저널 단위 재집계 점검 |
| `panel_audit2.py` | 그림 3 저널 단위 재집계 (수정판) |
| `panel_check.py` | (설명문 없음) 모집단 ISSN 수: / 1. 저널 커버리지 |
| `pub_break.py` | (설명문 없음) 1. 보강 논문이 많은 출판사 15곳 / 2. 보강 시점 분포 (보강된 논문 기준 |
| `pubnorm.py` | (설명문 없음) member 하나당 publisher 문자열이 여러 개인 경우: |
| `pubnorm2.py` | (설명문 없음) 민감도: 대상 / 보강 / 보강률 / tdm 포함: {r[0]:,} / {r[1]:,} / {100*r[1]/r[0]:.2f}% |
| `raw_check.py` | (설명문 없음) container-title / 진행 {pct:.1%} \| 찾은 레코드 {len(found)} \| 남은 시간 약 {(time.time() |
| `raw_trace.py` | (설명문 없음) published-print / published-online |
| `recheck.py` | (설명문 없음) 1-1. 같은 조건의 집합 대조 (DOI 단위 / 1-2. 표 7 재계산 (B 기준, DOI 단위 |
| `recheck2.py` | (설명문 없음) 0. DOI별 속성이 갈리는 경우 / 1-1. 표 7 (DOI 단위, 재확인 |
| `rev1.py` | (설명문 없음) 동일 출판사 내 신규출판 vs 과거출판 신규등록 (backfile 500건 이상 / 출판사별 차이의 중앙값 |
| `rev2.py` | (설명문 없음) 1. 각 스냅숏의 수록 cutoff (deposited 최댓값 / {y}: deposited 최대 {r[0]} / created 최대 {r[1]} |
| `rev3.py` | (설명문 없음) 1. 구성효과 분해 (직접표준화 / 2. 224종 포함 시 민감도 — 별도 계산 필요 여부 확인 |
| `rev4.py` | (설명문 없음) 1. 중간 시점 레코드 부재 여부 / 2. 1001 패턴 2,612건의 중간 시점 레코드 존재 여부 |
| `rev5.py` | 1. ISSN 공유 저널 |
| `rev6.py` | (설명문 없음) 1. CC로 판정된 URL의 종류 (2026, vor·am·unspecified / 2. 기타에 해당하는 URL 예시 |
| `rev7.py` | (설명문 없음) 1. 표 8 재계산 (created >= 2023-04 / 2. 미기재 표본 500건 전수 분류 |
| `s2_note.py` | 표 S2 각주의 4,092건이 어느 정의에서 나오는지 찾는다. |
| `sd_check.py` | (설명문 없음) 2783-5502로 조회된 DOI: / 원본 파일에서 찾은 수: |
| `sens224.py` | (설명문 없음) CC + 2021년까지 등재: / 이 중 OA 시작연도 > 등재연도: |
| `sensitivity.py` | tdm 포함 기준 |
| `shift.py` | (설명문 없음) 전환 출판연도: 2023 스냅숏 기준 vs 2026 스냅숏 기준 |
| `tdm_check.py` | (설명문 없음) 1. CC 기재 방식별 논문 수 / 2. tdm 등에만 있는 논문이 많은 출판사 10곳 |
| `three.py` | (설명문 없음) |
| `title_check.py` | (설명문 없음) 고유 저널명: / 같은 이름이 여러 번 나오는 저널 |
| `trace_all.py` | (설명문 없음) CROSSREF_MAILTO / total-results |
| `trace_missing.py` | (설명문 없음) CROSSREF_MAILTO / issn:{issn},type:journal-article |
| `trans_check.py` | (설명문 없음) url ILIKE '%creativecommons.org%' AND coalesce(content_ver / 1. 비표준 표기 19,090의 단위와 포함 관계 |
| `tz_check.py` | deposited 역행의 오프셋이 미국 동부 시간대와 맞는지 월별로 확인한다. |
| `underest.py` | (설명문 없음) 출판사별 과소추정 폭 |
| `verify.py` | (설명문 없음) |
| `why.py` | (설명문 없음) CROSSREF_MAILTO / container-title |
