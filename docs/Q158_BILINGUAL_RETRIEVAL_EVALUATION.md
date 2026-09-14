# Q158 한·영 로컬 검색 평가

## 구현과 범위

`pdf2md/bm25.py`는 외부 모델 없이 BM25 기준선을 제공한다. 기존
`scripts/run_rag_eval.py`의 lexical 점수와 release gate는 변경하지 않았다.
Unicode NFC/casefold 단어, 점·콜론·슬래시·하이픈을 포함한 기술 식별자,
한글 음절 bigram을 사용한다. 단어와 bigram은 별도 namespace로 구분한다.
형태소 분석·번역·embedding·reranker·LLM 호출은 하지 않는다.

BM25는 양수 log-IDF, k1=1.2, b=0.75를 사용한다. 반복 query term은 한 번만 반영하며
동점은 chunk ID로 정렬한다. 빈 문서·빈 query는 안전하게 처리하고 중복 chunk ID는 거부한다.
수식 근거: [Robertson·Zaragoza의 BM25 연구](https://doi.org/10.1561/1500000019).
이번 질의에 맞춰 파라미터를 조정하지 않았다.

`scripts/run_bm25_eval.py`는 한글 15개·영어 15개 질문을 검사하고 두 검색기를 동일 corpus에 적용한다.
평가 입력은 retrieval JSONL과 `queries` 배열을 가진 JSON이다. 각 질문은 `query_id`, `language`,
`query`, `expected_refs`(source_type/source_id/page), `critical_tokens`를 가진다.
평가 세트의 `chunks_sha256`가 실제 JSONL과 달라지면 실행을 거부한다.

- Recall@5: 질문별 예상 원문 참조 중 top 5에서 찾은 비율의 평균. hit rate와 구분한다.
- MRR@5: 첫 정답 참조 순위의 역수 평균. 미검색은 0이다.
- Citation coverage@5: 정답 type/ID/page와 유효 bbox가 있는 참조의 비율.
  bbox의 시각적 정확도나 생성 답변의 근거 충실성을 평가하는 지표는 아니다.
- Critical token preservation@5: 정답 참조와 일치한 검색 chunk의 `text`에 보존된 중요 토큰 비율.
  무관한 chunk나 `embedding_text`에만 토큰이 있어도 통과시키지 않는다.
  숫자·식별자 경계도 확인해 `10h` 안의 `0h`처럼 다른 값의 일부를 정답으로 인정하지 않는다.

결과는 `ko`, `en`, 전체를 따로 기록한다. 품질 임계값은 아직 설정하지 않았으며,
`review_gate_passed`는 사람 검토 기록만 뜻한다. `review.status=human_reviewed`와 reviewer가 없으면
결과를 저장하되 종료 코드 2를 반환한다. 이는 잠정 평가를 release 승인으로 오인하지 않기 위한 구분이다.

## 로컬 질문 초안과 잠정 결과

원문과 실제 정답은 저장소 정책에 따라 `output/q158_validation/`에만 저장했다.
`QUERY_REVIEW.md`에 질문 쌍 15개, 원본/slice 페이지, requirement/table/figure 참조,
중요 토큰을 제시했다. 구성은 언어별 requirement 6개·table row 6개·figure 3개다.
원문 PDF의 페이지 텍스트에서 중요 토큰을 대조한 뒤 기존 sidecar ID에 연결했다.
사람의 정답 검토는 아직 완료되지 않았고, 자동 대조를 사람 검토로 표시하지 않았다.

2026-09-15 추가 원문 검토: Codex가 원본 696·698·699페이지를 렌더링하여 요구사항 6개,
표 행 6개, 그림 3개와 한·영 질문 쌍을 대조했다. 페이지·ID·질문 의미의 불일치는 없었다.
6번 답의 중요 토큰은 숫자 일부 매칭을 피하도록 인용된 값 전체로 강화했고,
13번은 그림 캡션 식별에 더해 실제 답인 인터페이스 구성 토큰도 확인하도록 보완했다.
로컬 세트는 `agent_reviewed`로 기록했으며 사람 승인으로 변경하지 않았다. 보완 후 지표는 동일했다.

```bash
.venv311/bin/python scripts/run_bm25_eval.py \
  --chunks output/q157_cpu_final/controller_tables/native/cold/retrieval_chunks_rag.jsonl \
  --eval-set output/q158_validation/queries.draft.json \
  --report output/q158_validation/bm25_report.json
```

| 언어 | 검색기 | Recall@5 | MRR@5 | Citation coverage@5 | 중요 토큰 보존@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| 한글 | Lexical | 0.9333 | 0.7667 | 0.9333 | 0.9333 |
| 한글 | BM25 | 0.8000 | 0.5778 | 0.8000 | 0.8000 |
| 영어 | Lexical | 0.8667 | 0.5000 | 0.8667 | 0.8667 |
| 영어 | BM25 | 0.9333 | 0.7889 | 0.9333 | 0.9333 |

이는 영어 기술 문서 한 사례를 대상으로 한 기술 식별자 포함 한글 질문 평가다.
15개 질문의 번역 쌍이므로 30개 독립 주제를 의미하지 않는다. 한글 원문 검색은 합성 회귀로 검증했고,
실제 한글 문서 전체의 품질까지 입증한 결과는 아니다. BM25의 영어 순위 개선과 한글 recall 감소를
그대로 기록하며 기존 검색기를 자동 교체하지 않는다.

## 회귀 및 release 검증

Mac Python 3.11 및 3.14에서 전체 unit/integration/CLI/golden **각 590개가 통과**했다.
BM25 전용 회귀 8개를 포함하며 Ruff 및 diff 공백 검사도 통과했다.
한글 조사 차이·Unicode 정규화·식별자·수식·빈 입력·결정적 동점·ID 중복·부분 recall·잘못된 page 및
bbox·무관한 토큰의 거짓 통과를 검사한다. 제품 변환 로직과 golden 산출물은 변경하지 않았다.

기본 release gate는 OCR, corpus, 10/50/100페이지 benchmark, schema, packaging의
8개 하위 명령이 모두 통과했다. `output/q158_release/release_gate_report.json`에 보관했다.
이번 benchmark는 실행 건강성 검사이며 회귀 비교 baseline을 지정하지 않았으므로 성능 회귀 없음의 증거는 아니다.

원문 품질과 내부 무결성은 별개다. Q157 출력의 원문 정답 검사는 세 사례 모두 통과했다.
Controller artifact integrity도 통과했지만 visual 계약 검사는 front matter 462건,
controller 22건 오류가 남아 있다. Q159에서 해소할 기존 오류이며 이번 작업에서 숨기거나 제외하지 않았다.

CI는 기존 Ubuntu Python 3.11/3.14를 유지하고 Windows Python 3.11 CPU 조합을 추가했다.
[PR #142](https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex/pull/142)에서 원격 검증을 진행한다.
최초 실행에서 Linux 두 조합은 통과했으나 Windows에서 4건이 실패했다.
두 경로 구분자 테스트는 플랫폼 표현을 정규화하고, 마이크로초 타임아웃 테스트는
실제 OS 시계 대신 주입 가능한 결정적 시계로 수정했다. GUI smoke는 JSON 도움말의
콜론 뒤 줄바꿈을 Windows 드라이브 경로로 오인한 문제였다. 실제 드라이브 문자와 경로
구분자를 검사하도록 수정하고, 실제 경로 검출을 유지하는 회귀 테스트를 추가했다.
최신 커밋의 원격 결과는 PR checks에서 확인한다.

## 남은 완료 조건

1. `output/q158_validation/QUERY_REVIEW.md`의 질문·정답 참조에 대한 사람 검토 및 수정 반영.
2. 검토한 평가 세트로 재실행하여 확정 기준선 기록.
3. PR에서 새 Windows 및 기존 Linux CI의 실제 통과 확인.

따라서 Q158은 구현·로컬 검증 단계이며 전체 완료나 release 승인 상태는 아니다.

[원문 없는 잠정 집계](evaluation/q158_provisional_2026-09-14.json)에 지표·입력 hash·검토 상태와
원문 품질/내부 무결성 결과를 분리하여 보관한다.
[2026-09-15 원문 대조 집계](evaluation/q158_review_2026-09-15.json)는 보강한 중요 토큰 기준으로
재실행한 결과다. 질문 원문과 실제 정답은 포함하지 않는다.
