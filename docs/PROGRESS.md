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
Phase: 10
Status: VERIFIED
```

---

## 구현 완료

- Agent 없이 `Question → Retrieval → Retrieved Chunks → RAG Context → RAG Prompt → LLM → Answer + Citation` 흐름 구현
- 기존 `RetrievalService`와 Provider 중립 `LLMService` 경계를 조합하는 `RAGService` 구현
- RAG Answer Prompt와 근거 부족 문구를 `app/prompts/rag.py`에서 단일 관리
- JSON Context의 `metadata`와 `content`를 분리하고 Prompt에서 본문만 사실 근거로 사용하도록 제한
- `MAX_CONTEXT_TOKENS=12000` 기본 상한과 설정 검증 추가
- 완전한 Chunk를 검색 순서대로 우선 포함하고 첫 Chunk가 상한보다 클 때만 본문을 상한까지 축약
- Citation을 LLM 출력과 무관하게 실제 Context Result의 `document_id`, `filename`, `chunk_id`,
  `page`, `section`에서 Application이 생성
- 동일 5개 Citation 필드의 완전 중복은 최초 검색 순서를 유지하며 제거
- 검색 결과 없음/Threshold 미통과 시 LLM을 호출하지 않고 `제공된 문서에서 확인할 수 없습니다.`와 빈 Citation 반환
- 전체 Retrieval 결과와 실제 Context 포함 결과를 분리해 반환하여 Citation 대응 관계를 디버깅 가능하게 유지
- `scripts.inspect_rag` Agent 없는 개발 CLI 추가
- 실제 Embedding Provider → 임시 Qdrant Collection → Retrieval → RAG Context → 실제 LLM → Citation을
  검증하는 조건부 Provider E2E 추가
- Phase 13 전체 Context Budget Manager, Agent, Tool, Query Rewrite는 구현하지 않음

---

## 검증

- Phase 09 사전 상태 확인
  - `docs/PROGRESS.md`: Phase 09 `VERIFIED`, Blocker 없음, 실제 Qdrant Retrieval 검증 완료 확인
- Phase 10 Unit/Deterministic Integration/Config
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_rag.py tests\integration\rag\test_rag_pipeline.py tests\unit\test_config.py -q`
  - Result: PASS (`22 passed`)
  - 근거 있음, 근거 없음, Threshold 미통과, 여러 문서/Page/Chunk, Citation↔Context Result 일치,
    중복 Citation, LLM 가짜 Citation 격리, Context token 상한, 의존성 종료 확인
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`220 passed, 14 skipped`; 조건부 외부 Infrastructure/LLM/Embedding/Ingestion/Retrieval/RAG Test)
- 실제 외부 Embedding/Qdrant/LLM Pure RAG E2E
  - Command: `RUN_RAG_INTEGRATION_TESTS=1` 적용 후
    `.\.venv\Scripts\python.exe -m pytest tests\integration\rag\test_rag_provider_integration.py -q`
  - Result: PASS (`1 passed`)
  - 실제 Embedding Vector 저장/검색, 전용 RAG Prompt를 통한 실제 LLM 답변의 `COBALT-731` 확인,
    `document_id`, `filename`, `chunk_id`, `page`, `section` Citation 일치, 테스트 Collection 삭제 확인
- 모든 조건부 외부/Infrastructure Test 전체 회귀
  - Command: `RUN_INFRASTRUCTURE_TESTS=1`, `RUN_LLM_INTEGRATION_TESTS=1`,
    `RUN_EMBEDDING_INTEGRATION_TESTS=1`, `RUN_INGESTION_INTEGRATION_TESTS=1`,
    `RUN_RETRIEVAL_INTEGRATION_TESTS=1`, `RUN_RAG_INTEGRATION_TESTS=1` 적용 후
    `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`234 passed`, skip 없음)
  - 실제 외부 LLM/Embedding, MinIO, Qdrant, Ingestion, Retrieval, Pure RAG 전체 조건부 테스트 통과
- 재검증 기록
  - 첫 전체 외부 실행은 `.env` 값을 프로세스 환경으로 내보내지 않아 Infrastructure 9 tests 실패;
    Secret 노출 없이 환경을 주입한 재실행에서 기존 전체 `233 passed`
  - Pure RAG E2E 첫 실행은 Hugging Face 요청이 30초를 초과해 timeout;
    테스트 전용 timeout만 120초로 조정한 재실행과 최종 전체 회귀 통과
- Command: `.\.venv\Scripts\python.exe -m scripts.inspect_rag --help`
  - Result: PASS (Agent 없이 사용자/단일·복수 문서/질문/Top-K/Threshold 인자 확인)
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

- 없음. 현재 설정된 실제 외부 Embedding/LLM Provider와 로컬 Qdrant·MinIO를 사용하는 모든 조건부
  테스트를 실행했으며 skip 없이 통과함.

---

## 변경 파일

- `.env.example`, `README.md`, `pyproject.toml`
- `app/core/config.py`
- `app/models/rag.py`
- `app/prompts/__init__.py`, `app/prompts/rag.py`
- `app/services/rag_context.py`, `app/services/rag.py`, `app/rag.py`
- `scripts/inspect_rag.py`
- `tests/unit/test_rag.py`, `tests/unit/test_config.py`
- `tests/integration/rag/__init__.py`, `tests/integration/rag/test_rag_pipeline.py`
- `tests/integration/rag/test_rag_provider_integration.py`
- `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/DECISIONS.md`
- `docs/FILE_STRUCTURE.md`, `docs/PROGRESS.md`, `docs/TESTING.md`

---

## 다음 작업

- Phase 10 필수 범위와 회귀 검증이 완료되어 Phase 11 진행 가능.
- 운영 Provider/Model을 변경하면 동일한 조건부 전체 회귀를 다시 실행한다.

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
