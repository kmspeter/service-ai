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
| 02 | Infrastructure Clients | NOT_STARTED | - |
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
Phase: 01
Status: VERIFIED
```

---

## 구현 완료

- Python 3.12 FastAPI 애플리케이션 팩토리 및 실행 진입점
- API Router와 `/health`, `/ready` 응답 Schema
- 환경변수 및 `.env` 기반 중앙 설정 계층과 테스트 설정 주입
- 향후 Phase별 필수 설정 검증 구조
- timestamp, level, logger, request_id, message를 포함하는 JSON Logging
- 요청 ID Middleware 및 응답 Header 전달
- Validation, External Service, Resource Not Found, AI Processing, Internal Error 공통 예외 구조
- Stack Trace와 내부 예외 상세를 노출하지 않는 표준 오류 응답
- Python 3.12 venv 기반 의존성/테스트/정적 검사 구성
- `.env.example` 및 Secret 제외 `.gitignore`

---

## 검증

- Command: `.\.venv\Scripts\python.exe --version`
  - Result: PASS (`Python 3.12.10`)
- Command: `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit -q`
  - Result: PASS (`5 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/integration -q`
  - Result: PASS (`5 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`10 passed`)
- Command: `curl.exe --include http://localhost:8000/health`
  - Result: PASS (`HTTP 200`, `{"status":"ok"}`)
- Command: `curl.exe --include http://localhost:8000/ready`
  - Result: PASS (`HTTP 200`, `{"status":"ready","checks":{"configuration":"ok"}}`)
- Command: `git diff --check`
  - Result: PASS
- Command: tracked source Secret assignment scan
  - Result: PASS (하드코딩된 Secret 없음)

---

## 현재 Blocker

없음.

---

## 미검증 항목

- Phase 01 범위 내 미검증 항목 없음.
- Qdrant, MinIO 및 외부 Provider 연결은 Phase 01 제외 범위이므로 검증하지 않음.

---

## 변경 파일

- `.env.example`
- `.gitignore`
- `pyproject.toml`
- `README.md`
- `app/__init__.py`
- `app/main.py`
- `app/api/__init__.py`
- `app/api/router.py`
- `app/api/health.py`
- `app/core/__init__.py`
- `app/core/config.py`
- `app/core/logging.py`
- `app/core/request_context.py`
- `app/core/exceptions.py`
- `app/schemas/__init__.py`
- `app/schemas/health.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/unit/test_application.py`
- `tests/unit/test_config.py`
- `tests/unit/test_logging.py`
- `tests/integration/test_health.py`
- `tests/integration/test_exceptions.py`
- `docs/TESTING.md`
- `docs/PROGRESS.md`

---

## 다음 작업

- Phase 01 검증 완료. 사용자 요청 시 `Phase 02 — Infrastructure Clients` 진행 가능.

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
