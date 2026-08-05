# AI Server Progress

## 상태 규칙

상태 값:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
IMPLEMENTED
VERIFIED
```

의미:

- `NOT_STARTED`: 작업 시작 전
- `IN_PROGRESS`: 구현 중
- `BLOCKED`: 외부 의존/결정 문제로 진행 불가
- `IMPLEMENTED`: 코드 구현은 완료했으나 전체 검증 전
- `VERIFIED`: 해당 Phase의 요구 검증 완료

`IMPLEMENTED`를 `VERIFIED`와 동일하게 취급하지 않는다.

---

## 현재 진행상태

| Phase | 내용 | 상태 | 검증 |
| ---: | --- | --- | --- |
| 01 | Project Skeleton | VERIFIED | Unit/Integration 10 tests + curl 검증 통과 |
| 02 | Infrastructure Clients | VERIFIED | Docker Compose + 22 tests + `/ready` 검증 통과 |
| 03 | LLM Provider Abstraction | VERIFIED | OpenAI/Ollama/Gemini Unit·Regression + Ollama/Gemini 실제 검증 통과 |
| 04 | Embedding Provider | VERIFIED | OpenAI Embedding Unit·Regression + 실제 Qdrant Dimension 검증 통과 |
| 05 | Parser Layer | VERIFIED | TXT/MD/PDF fixture Unit 26 tests + 전체 Regression 통과 |
| 06 | Token Measurement & Recursive Chunking | VERIFIED | Token/Chunk/Metadata Unit 20 tests + 전체 Regression 통과 |
| 07 | Document Ingestion Pipeline | VERIFIED | 전체 187 tests 무-skip + 실제 HF/MinIO/Qdrant/curl Payload 검증 통과 |
| 08 | Document Delete & Status | VERIFIED | Unit/API 32 tests + 전체 192 tests + 실제 Qdrant 10 tests 통과 |
| 09 | Vector Retrieval | VERIFIED | Unit/Adapter 36 tests + 전체 212 tests + 실제 Qdrant Retrieval 검증 통과 |
| 10 | Agent 없는 RAG + Citation | VERIFIED | Unit 22 + 실제 Embedding/Qdrant/LLM E2E + 외부 포함 전체 234 tests 통과 |
| 11 | Document Summary | VERIFIED | Unit 26 + 실제 MinIO/Qdrant/Gemini E2E + 전체 Regression 통과 |
| 12 | Query Rewrite | NOT_STARTED | - |
| 13 | Context & Token Budget Manager | NOT_STARTED | - |
| 14 | Tool Layer | NOT_STARTED | - |
| 15 | Agent Tool Calling | NOT_STARTED | - |
| 16 | Usage Aggregation | NOT_STARTED | - |
| 17 | WebSocket Event Model | NOT_STARTED | - |
| 18 | WebSocket Streaming | NOT_STARTED | - |
| 19 | Stability | NOT_STARTED | - |
| 20 | Final AI Server Verification | NOT_STARTED | - |

---

## 현재 Phase

```text
Phase: 11
Status: VERIFIED
```

---

## 구현 완료

- `document_id`와 `user_id`로 Qdrant의 사용자 Scope 메타데이터를 조회하고 `source` 위치의 MinIO 원본을
  기존 Parser Registry로 다시 파싱하는 `DocumentSummaryService` 구현
- Qdrant Payload의 `chunk_text`를 원본 문서 Source로 사용하지 않고 저장 위치/파일명 메타데이터만 사용
- 렌더링된 Direct Prompt Token, Model Context Window, Reserved Output Token, Safety Margin을 합산하는
  Python 규칙 기반 `SummaryStrategySelector` 구현
- 작은 문서는 전체 원문과 전용 Prompt를 한 번 호출하는 Direct Summary 구현
- 큰 문서는 기존 Recursive Chunker를 현재 Map Prompt Budget에 맞춰 조정하고 Chunk별 Map Summary 수행
- 부분 Summary 전체가 한 번에 들어가지 않으면 Intermediate Reduce를 반복한 뒤 Final Reduce를 수행하는
  다단계 Hierarchical Summary 구현
- Direct, Chunk Map, Intermediate Reduce, Final Reduce Prompt를 `app/prompts/summary.py`에서 분리 관리
- `LLM_CONTEXT_WINDOW`, `SUMMARY_SAFETY_MARGIN_TOKENS` 설정과 Phase 11 설정 검증 추가
- 문서 없음, MinIO 원본 없음, Prompt Budget 부족, LLM 단계별 실패를 명시적으로 처리
- 비민감 합성 Fixture로 실제 MinIO/Qdrant/Gemini Direct·Hierarchical Summary E2E 추가
- Agent Tool, Summary API, Query Rewrite, Phase 13 전체 Context Manager는 구현하지 않음

---

## 검증

- Phase 10 사전 상태 확인
  - `docs/PROGRESS.md`: Phase 10 `VERIFIED`, Blocker 없음 확인
- Phase 11 Summary/Config Unit
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_summary.py tests\unit\test_config.py -q`
  - Result: PASS (`26 passed`)
  - Direct Summary, MinIO 원본 사용, Hierarchical Map/Final Reduce, 다단계 Intermediate Reduce,
    Direct 가능 최대/불가능 최소 경계, 문서 없음, Direct LLM 실패, 두 번째 Map 실패, LLM 종료,
    Context Window/Safety Margin 설정 검증
- 실제 MinIO/Qdrant/Gemini Summary Provider E2E
  - Command: `RUN_SUMMARY_INTEGRATION_TESTS=1` 적용 후
    `.\.venv\Scripts\python.exe -m pytest tests\integration\summary\test_summary_provider_integration.py -q -s`
  - Result: PASS (`1 passed in 67.49s`)
  - MinIO 원본 2개 저장/조회, 사용자 Scope Qdrant Metadata 조회, Direct 1회,
    Hierarchical Map 2회 + Final Reduce 1회, 처음/마지막 합성 Marker 보존, 임시 리소스 정리 확인
- 실제 Summary E2E 포함 전체 회귀
  - Command: `RUN_SUMMARY_INTEGRATION_TESTS=1` 적용 후 `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`232 passed, 14 skipped in 79.40s`)
  - 기존 비용 발생형 Embedding/RAG 조건부 E2E는 비활성, Summary Provider E2E만 활성
- 재검증 기록
  - Sandbox 실행은 외부 Gemini 연결 차단으로 실패했으나 MinIO/Qdrant 경계와 정리 동작은 성공
  - Gemini 출력 예약 160/512에서는 HTTP 200 응답이 미완료 상태여서 Adapter가 거부
  - 테스트 입력 Budget을 유지하고 출력 예약을 4096으로 늘린 최종 실행에서 전체 단계 통과
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pip check`
  - Result: PASS (`No broken requirements found`)
- Command: `git diff --check`
  - Result: PASS

---

## 현재 Blocker

- 없음.

---

## 미검증 항목

- 없음. 실제 MinIO/Qdrant/Gemini Summary E2E와 해당 E2E를 포함한 전체 회귀를 실행함.

---

## 변경 파일

- `.env.example`, `pyproject.toml`
- `app/core/config.py`, `app/core/exceptions.py`
- `app/models/summary.py`
- `app/prompts/summary.py`
- `app/services/summary.py`, `app/summary.py`
- `tests/unit/test_summary.py`, `tests/unit/test_config.py`
- `tests/integration/summary/__init__.py`, `tests/integration/summary/test_summary_provider_integration.py`
- `docs/TESTING.md`, `docs/PROGRESS.md`

---

## 다음 작업

- Phase 11 필수 범위와 회귀 검증이 완료되어 Phase 12 진행 가능.
- 운영 LLM Model을 변경하면 해당 Model의 실제 Context Window를 `LLM_CONTEXT_WINDOW`에 명시한다.

---

# Progress Update Template

Phase 완료/진행 시 아래 형식으로 갱신한다.

```markdown
## 현재 Phase

Phase: XX
Status: IN_PROGRESS | IMPLEMENTED | VERIFIED | BLOCKED

## 구현 완료

- ...
- ...

## 검증

- Command: `...`
  - Result: PASS
- Command: `...`
  - Result: PASS

## 실패/미검증

- ...

## 변경 파일

- `...`

## 다음 작업

- ...
```

검증하지 않은 항목을 임의로 `VERIFIED`로 표시하지 않는다.
