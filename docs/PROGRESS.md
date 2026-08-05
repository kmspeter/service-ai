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
| 03 | LLM Provider Abstraction | NOT_STARTED | - |
| 04 | Embedding Provider | NOT_STARTED | - |
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
Phase: 02
Status: VERIFIED
```

---

## 구현 완료

- Qdrant `1.18.2`, MinIO `RELEASE.2025-06-13T11-33-47Z` 로컬 Docker Compose 구성
- Qdrant/MinIO named volume과 localhost 전용 기본 포트 바인딩
- Application Service가 SDK를 직접 사용하지 않는 `QdrantRepository`/`ObjectStorage` Port
- Qdrant 연결, collection 존재/생성/정보/삭제 Adapter
- MinIO 연결, bucket 확인/개발환경 자동 생성, object 저장/읽기/삭제 Adapter
- Qdrant production collection vector dimension을 확정하지 않고 생성 호출자가 dimension을 명시하는 구조
- SDK 오류를 Connection/Timeout/Authentication/Not Found/External Service 오류로 변환
- Qdrant와 MinIO SDK client timeout 설정 및 lifecycle 종료 처리
- `/ready`의 application/Qdrant/MinIO 상태 확인과 실패 시 HTTP 503 처리
- 환경변수 기반 Credential 설정과 Secret 비노출
- 현재 파일과 계층 책임을 명시한 `docs/FILE_STRUCTURE.md`

---

## 검증

- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit -q`
  - Result: PASS (`12 passed`)
- Command: Infrastructure 환경변수 설정 후 `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`22 passed`)
- Command: `docker compose up -d`
  - Result: PASS (Qdrant/MinIO container 시작)
- Command: `docker compose ps`
  - Result: PASS (Qdrant `healthy`, MinIO `healthy`)
- Command: Qdrant/MinIO Integration Test
  - Result: PASS (`4 passed`; collection/bucket/object 정리 포함)
- Command: `curl.exe http://localhost:6333/healthz`
  - Result: PASS (`healthz check passed`)
- Command: `curl.exe http://localhost:9000/minio/health/live`
  - Result: PASS (`HTTP 200`)
- Command: 실제 Uvicorn 실행 후 `curl.exe --include http://localhost:8000/ready`
  - Result: PASS (`HTTP 200`, application/Qdrant/MinIO 모두 `ok`)
- Command: `git diff --check`
  - Result: PASS
- Command: tracked source Secret assignment scan
  - Result: PASS (하드코딩된 Secret 없음)

---

## 현재 Blocker

없음.

---

## 미검증 항목

- Phase 02 범위 내 미검증 항목 없음.
- Parser, Ingestion, Embedding, Retrieval, RAG, Agent, WebSocket Chat, Queue는 Phase 02 제외 범위로 구현/검증하지 않음.

---

## 변경 파일

- `.env.example`
- `compose.yaml`
- `pyproject.toml`
- `README.md`
- `app/main.py`
- `app/api/health.py`
- `app/core/config.py`
- `app/core/exceptions.py`
- `app/infrastructure.py`
- `app/adapters/__init__.py`
- `app/adapters/qdrant.py`
- `app/adapters/minio.py`
- `app/ports/__init__.py`
- `app/ports/qdrant.py`
- `app/ports/storage.py`
- `tests/conftest.py`
- `tests/fakes.py`
- `tests/unit/adapters/test_qdrant_adapter.py`
- `tests/unit/adapters/test_minio_adapter.py`
- `tests/integration/test_health.py`
- `tests/integration/qdrant/test_qdrant_integration.py`
- `tests/integration/minio/test_minio_integration.py`
- `docs/FILE_STRUCTURE.md`
- `docs/TESTING.md`
- `docs/PROGRESS.md`

---

## 다음 작업

- Phase 02 검증 완료. 사용자 요청 시 `Phase 03 — LLM Provider Abstraction` 진행 가능.

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
