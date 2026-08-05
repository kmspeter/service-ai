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
Phase: 08
Status: VERIFIED
```

---

## 구현 완료

- Backend 전용 `DELETE /internal/documents/{document_id}`
- Backend 전용 `GET /internal/documents/{document_id}/status`
- query의 `request_id`, Backend 검증 `user_id`, path `document_id` 실행 Context Validation
- Qdrant 삭제·상태 조회 및 기존 재처리 교체에 `user_id + document_id` Scope Filter 적용
- 삭제된 전체 Point 수를 반환하고 다른 문서/다른 사용자 Scope를 보존
- 없는 Vector는 HTTP 404와 `NOT_FOUND`, Qdrant 실패는 HTTP 502와
  `FAILED / QDRANT_DELETE_FAILED / retryable=true`로 반환
- 삭제 범위를 Qdrant Vector로 한정하고 Backend Metadata 및 MinIO 원본은 변경하지 않음
- `UPLOADED / PROCESSING / COMPLETED / FAILED` 상태 응답 DTO
- Ingestion 시작 시 `PROCESSING`, 종료 시 `COMPLETED` 또는 `FAILED`를 process-local Registry에 기록
- Qdrant Chunk payload에서 `COMPLETED`와 처리 통계를 복원하여 재시작 후 완료 상태 조회 지원
- 별도 문서 DB나 Backend Document Entity 복제 없이 최소 상태 구현
- Ingestion과 삭제가 같은 scoped document 작업 Lock을 공유하여 동시 교체/삭제 충돌 방지
- 성공/없는 Vector 삭제 후 AI 상태 Registry 정리

---

## 검증

- Phase 07 사전 상태 확인
  - `docs/PROGRESS.md`: Phase 07 `VERIFIED`, Blocker/미검증 없음, Phase 08 진행 가능 확인
- Phase 08 Unit/API
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_document_management.py tests\unit\test_ingestion.py tests\unit\adapters\test_qdrant_adapter.py tests\integration\test_document_management_api.py -q`
  - Result: PASS (`32 passed`)
  - 전체 scoped Vector 삭제, 다른 문서/다른 사용자 보존, 없는 문서, Qdrant 오류 확인
  - `PROCESSING`, `COMPLETED`, `FAILED`, Qdrant 완료 상태 복원, 알 수 없는/다른 user 상태 404 확인
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`192 passed, 11 skipped`; 조건부 외부 Infrastructure/LLM/Embedding/Ingestion Test)
- 실제 Qdrant scoped delete 단일 검증
  - Command: `RUN_INFRASTRUCTURE_TESTS=1` 적용 후
    `.\.venv\Scripts\python.exe -m pytest tests\integration\qdrant\test_qdrant_integration.py -k scoped_document_delete -q`
  - Result: PASS (`1 passed, 4 deselected`)
  - 일치하는 2개 Vector 전체 삭제, 같은 user의 다른 document와 같은 document의 다른 user Vector 보존,
    없는 document 0건 확인
- 실제 Qdrant 전체 및 Phase 08 API Integration
  - Command: `RUN_INFRASTRUCTURE_TESTS=1` 적용 후
    `.\.venv\Scripts\python.exe -m pytest tests\integration\qdrant tests\integration\test_document_management_api.py -q`
  - Result: PASS (`10 passed`)
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

- 없음.

---

## 변경 파일

- `README.md`
- `app/api/documents.py`, `app/core/exceptions.py`, `app/core/request_context.py`, `app/main.py`
- `app/documents.py`, `app/ingestion.py`
- `app/models/ingestion.py`, `app/schemas/documents.py`
- `app/ports/qdrant.py`, `app/adapters/qdrant.py`
- `app/services/document_management.py`, `app/services/ingestion.py`
- `tests/fakes.py`, `tests/unit/test_document_management.py`, `tests/unit/test_ingestion.py`
- `tests/unit/adapters/test_qdrant_adapter.py`
- `tests/integration/test_document_management_api.py`
- `tests/integration/qdrant/test_qdrant_integration.py`
- `docs/CONTRACTS.md`, `docs/FILE_STRUCTURE.md`, `docs/PROGRESS.md`, `docs/TESTING.md`

---

## 다음 작업

- Blocker와 미검증 항목이 없어 Phase 09 진행 가능.

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
