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
Phase: 09
Status: VERIFIED
```

---

## 구현 완료

- Agent 없이 `Query → Embedding → Qdrant Dense Search → Filter → Top-K → Score Threshold` 흐름 구현
- 설정 계층에 `TOP_K=5`, `SCORE_THRESHOLD=0.5` 기본값과 범위 검증 추가
- 내부 요청별 `top_k`, `score_threshold` Override 지원
- 모든 검색에 `user_id` Qdrant Filter를 강제하고 문서 범위가 있으면
  단일 `document_id` 또는 복수 `document_ids` Filter 추가
- 단일/복수 문서 범위 상호 배타 Validation과 중복 `document_ids` 정규화
- Qdrant SDK 검색 결과를 Port DTO로 격리하고 외부 오류 변환 경계 유지
- Phase 10 Citation Source로 직접 사용할 수 있는 `chunk_id`, `document_id`, `filename`,
  `page`, `section`, `score`, `content` Retrieval Result 구현
- Citation 필수 Metadata가 누락되거나 타입이 잘못된 Qdrant 결과는 명시적 오류로 차단
- `user_id`, `document_id(s)`, Query, Top-K, Threshold를 입력해 결과를 확인하는
  `scripts.inspect_retrieval` 개발 CLI 추가
- Reranker, Hybrid Search, Multi Query, HyDE, Agent는 구현하지 않음

---

## 검증

- Phase 08 사전 상태 확인
  - `docs/PROGRESS.md`: Phase 08 `VERIFIED`, Blocker/미검증 없음, Phase 09 진행 가능 확인
- Phase 09 Unit/Adapter/Config
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_retrieval.py tests\unit\adapters\test_qdrant_adapter.py tests\unit\test_config.py -q`
  - Result: PASS (`36 passed`)
  - Query Embedding, 기본/Override Top-K·Threshold, 단일/복수 문서 Scope, 요청 Validation,
    Citation-ready Metadata 변환, Qdrant Filter 형태 확인
- 실제 Qdrant Retrieval
  - Command: `RUN_INFRASTRUCTURE_TESTS=1`, `QDRANT_URL=http://127.0.0.1:6333` 적용 후
    `.\.venv\Scripts\python.exe -m pytest tests\integration\retrieval\test_retrieval_integration.py -q`
  - Result: PASS (`1 passed`)
  - 동일 Query Vector에서 `user-001`/`user-002` 완전 격리, `document_ids=[doc-001]`의
    `doc-002` 제외, 관련/부분 관련/무관 점수 순서, Top-K와 Threshold 변화 확인
- 실제 Qdrant 전체 Regression + Retrieval
  - Command: `RUN_INFRASTRUCTURE_TESTS=1`, `QDRANT_URL=http://127.0.0.1:6333` 적용 후
    `.\.venv\Scripts\python.exe -m pytest tests\integration\qdrant tests\integration\retrieval\test_retrieval_integration.py -q`
  - Result: PASS (`6 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`212 passed, 13 skipped`; 조건부 외부 Infrastructure/LLM/Embedding/Ingestion/Retrieval Test)
- Command: `.\.venv\Scripts\python.exe -m scripts.inspect_retrieval --help`
  - Result: PASS (사용자/단일·복수 문서/Query/Top-K/Threshold 인자 확인)
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

- 실제 Hugging Face Embedding Provider와 Qdrant를 함께 사용하는 선택형 품질 E2E는
  테스트 문장의 외부 API 전송 승인이 없어 실행하지 않음.
- Provider 자체 Embedding 호출/Dimension은 Phase 04에서 실제 검증 완료했고, Phase 09 필수 흐름은
  결정적 Query Embedding과 실제 Qdrant로 검증했으므로 Phase 완료를 막지 않음.

---

## 변경 파일

- `.env.example`, `README.md`, `pyproject.toml`
- `app/core/config.py`, `app/core/exceptions.py`
- `app/models/retrieval.py`, `app/ports/qdrant.py`, `app/adapters/qdrant.py`
- `app/services/retrieval.py`, `app/retrieval.py`
- `scripts/inspect_retrieval.py`
- `tests/unit/test_retrieval.py`, `tests/unit/test_config.py`
- `tests/unit/adapters/test_qdrant_adapter.py`
- `tests/integration/retrieval/__init__.py`
- `tests/integration/retrieval/test_retrieval_integration.py`
- `tests/integration/retrieval/test_retrieval_provider_integration.py`
- `docs/CONTRACTS.md`, `docs/DECISIONS.md`, `docs/FILE_STRUCTURE.md`
- `docs/PROGRESS.md`, `docs/TESTING.md`

---

## 다음 작업

- Phase 09 필수 범위와 실제 Qdrant 검증이 완료되어 Phase 10 진행 가능.
- 운영 Embedding Model의 의미 검색 품질 기준을 별도로 확정할 경우 선택형 Provider E2E를 실행한다.

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
