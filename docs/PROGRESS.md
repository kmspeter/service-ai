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
| 05 | Parser Layer | NOT_STARTED | - |
| 06 | Token Measurement & Recursive Chunking | NOT_STARTED | - |
| 07 | Document Ingestion Pipeline | NOT_STARTED | - |
| 08 | Document Delete & Status | NOT_STARTED | - |
| 09 | Vector Retrieval | NOT_STARTED | - |
| 10 | Agent 없는 RAG + Citation | NOT_STARTED | - |
| 11 | Document Summary | NOT_STARTED | - |
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
Phase: 04
Status: VERIFIED
```

---

## 구현 완료

- SDK 독립 `EmbeddingProvider`, `EmbeddingResult`, `EmbeddingBatchResult`, `EmbeddingUsage` Port
- Provider 중립 `EmbeddingService`와 설정 기반 OpenAI Embedding Adapter 조립
- 단일 문자열 및 여러 문자열 Batch Embedding
- `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_TIMEOUT_SECONDS` 독립 설정
- LLM Client/Key와 Embedding Client/Key의 책임 및 lifecycle 분리
- 기본 모델 `text-embedding-3-small`의 실제 기본 Dimension 1536 적용
- 반환 Vector 개수, index, 유한 숫자, 모든 Vector의 1536 Dimension 검증
- OpenAI `prompt_tokens`, `total_tokens` Usage와 `perf_counter` 기반 latency 수집
- Authentication, Authorization, Rate Limit, Timeout, Connection, Provider 5xx, Invalid Response 오류 표준화
- OpenAI SDK 자동 Retry 비활성화 및 Phase 04 별도 Retry 미적용
- 빈 단일/Batch 입력을 Provider 호출 전에 명시적으로 거부
- Qdrant Collection이 없을 때 명시적 초기화 호출로 Cosine/1536 Collection 생성
- 기존 Qdrant Collection Dimension이 다르면 자동 삭제/재생성 없이 `QDRANT_VECTOR_DIMENSION_MISMATCH` 발생
- Credential이 있을 때만 실제 호출하는 독립 Embedding Integration Test
- Parsing/Chunking, Qdrant Point 저장, Retrieval과 연결하지 않음

---

## 검증

- Phase 03 문서 상태 확인: `VERIFIED`
- Command: Phase 03 핵심 Unit Test 재실행
  - Result: PASS (`53 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit/adapters/test_openai_embedding_adapter.py tests/unit/test_embedding.py tests/unit/test_config.py -q`
  - Result: PASS (`33 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit -q`
  - Result: PASS (`95 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`101 passed, 8 skipped`; 실제 Infrastructure/LLM/Embedding Test만 조건부 skip)
- Command: `RUN_INFRASTRUCTURE_TESTS=1`, `QDRANT_URL=http://127.0.0.1:6333`로 `.\.venv\Scripts\python.exe -m pytest tests/integration/qdrant -q`
  - Result: PASS (`4 passed`; 1536 Collection 생성 및 잘못된 4 Dimension Collection 거부/보존 확인)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/integration/embedding -q`
  - Result: SKIP (`1 skipped`; OpenAI Embedding Credential 미설정으로 비용 방지)
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `git diff --check`
  - Result: PASS

---

## 현재 Blocker

없음.

---

## 미검증 항목

- 실제 OpenAI Embedding 호출은 `EMBEDDING_API_KEY` 미제공으로 미검증이며 Mock 검증만 완료.
- 실제 Qdrant Collection Dimension 생성/불일치 정책은 로컬 Qdrant에서 검증 완료.
- Parsing/Chunking 연결, Qdrant Point 저장, Retrieval은 Phase 04 제외 범위로 구현하지 않음.

---

## 변경 파일

- `.env.example`
- `pyproject.toml`
- `app/core/config.py`
- `app/core/exceptions.py`
- `app/adapters/openai_embedding.py`
- `app/embedding.py`
- `app/ports/embedding.py`
- `app/services/embedding.py`
- `tests/unit/test_config.py`
- `tests/unit/test_embedding.py`
- `tests/unit/adapters/test_openai_embedding_adapter.py`
- `tests/integration/embedding/__init__.py`
- `tests/integration/embedding/test_embedding_integration.py`
- `tests/integration/qdrant/test_qdrant_integration.py`
- `docs/FILE_STRUCTURE.md`
- `docs/TESTING.md`
- `docs/PROGRESS.md`

---

## 다음 작업

- Phase 04 Embedding Provider와 Qdrant Dimension 검증 완료.
- `Phase 05 — Parser Layer` 진행 가능.

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
