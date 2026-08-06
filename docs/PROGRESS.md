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
| 12 | Query Rewrite | VERIFIED | Unit/RAG 19 + 실제 Gemini Prompt E2E + 전체 243 tests 통과 |
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
Phase: 12
Status: VERIFIED
```

---

## 구현 완료

- `Conversation Summary`, `Recent Messages`, `Current Message`를 분리 입력하는 `QueryRewriteService` 구현
- `original_query`, `rewritten_query`, `was_rewritten`, `status`를 분리한 불변 결과 모델 구현
- 대화 Context가 없으면 LLM을 호출하지 않고 원문 Query를 사용하는 명시적 호출 정책 구현
- Context가 있으면 LLM이 Rewrite 필요 여부를 판단하고, 독립 질문은 원문을 유지하는 정책 구현
- `SKIPPED_NO_CONTEXT`, `UNCHANGED`, `REWRITTEN`, `FALLBACK` 상태로 판단 결과를 식별 가능하게 구현
- 별도 `app/prompts/query_rewrite.py`에서 답변 생성 금지, 짧은 독립 Query, JSON 출력 규칙 관리
- Provider 오류, 비정상 JSON, 빈 Query, 500자 초과 Query는 원문 Retrieval Query로 fallback
- RAG Pipeline에서 재작성 Query는 Retrieval에만 사용하고 최종 답변 Prompt에는 원문 질문을 유지
- Query Rewrite와 RAG Answer가 하나의 LLM 경계를 공유하되 종료는 RAG Service가 한 번만 수행
- Agent Tool Calling, Phase 13 Context Token Budget Manager, WebSocket/API Contract는 구현하지 않음

---

## 검증

- Phase 11 사전 상태 확인
  - `docs/PROGRESS.md`: Phase 11 `VERIFIED`, Blocker 없음 확인
- Query Rewrite Unit 및 RAG 경계 Integration
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_query_rewrite.py tests\unit\test_rag.py tests\integration\rag\test_rag_pipeline.py -q`
  - Result: PASS (`19 passed`)
  - `그거`, `그럼`, `위 내용`, 독립 질문, Conversation 없음, Summary-only Context,
    Provider 실패, 비정상/과도한 출력, 빈 질문, 원문 보존, Retrieval-only Rewrite 검증
- 실제 Gemini Query Rewrite Prompt E2E
  - Command: `RUN_QUERY_REWRITE_INTEGRATION_TESTS=1` 적용 후
    `.\.venv\Scripts\python.exe -m pytest tests\integration\query_rewrite\test_query_rewrite_provider_integration.py -q -s`
  - Result: PASS (`1 passed`)
  - 실제 Provider가 `그럼 장점은?`을 Qdrant와 장점을 포함하는 독립 Query로 재작성하고 원문을 보존함
- 전체 회귀
  - Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`243 passed, 16 skipped`)
  - 비용/외부 Infrastructure가 필요한 조건부 E2E는 비활성
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

- 없음. 실제 Gemini Query Rewrite Prompt E2E와 전체 비용 없는 회귀를 실행함.

---

## 변경 파일

- `pyproject.toml`
- `app/models/query_rewrite.py`, `app/models/rag.py`
- `app/prompts/query_rewrite.py`
- `app/services/query_rewrite.py`, `app/services/rag.py`, `app/rag.py`
- `tests/unit/test_query_rewrite.py`, `tests/unit/test_rag.py`
- `tests/integration/rag/test_rag_pipeline.py`
- `tests/integration/query_rewrite/__init__.py`
- `tests/integration/query_rewrite/test_query_rewrite_provider_integration.py`
- `docs/TESTING.md`, `docs/PROGRESS.md`

---

## 다음 작업

- Phase 12 필수 범위와 회귀 검증이 완료되어 Phase 13 진행 가능.
- Phase 13에서는 이번 단계의 Rewrite 입력/결과 경계를 유지한 채 Context Token Budget만 구현한다.

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
