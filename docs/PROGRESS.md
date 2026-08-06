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
| 13 | Context & Token Budget Manager | VERIFIED | Unit/RAG 35 + 전체 253 tests 통과 |
| 14 | Tool Layer | VERIFIED | Tool Unit 15 + 전체 290 tests + branch coverage 87.93% 통과 |
| 15 | Agent Tool Calling | VERIFIED | Agent Unit/Adapter 17 + 실제 Gemini 분기/경계 + 전체 307 tests + branch coverage 87.70% 통과 |
| 16 | Usage Aggregation | NOT_STARTED | - |
| 17 | WebSocket Event Model | NOT_STARTED | - |
| 18 | WebSocket Streaming | NOT_STARTED | - |
| 19 | Stability | NOT_STARTED | - |
| 20 | Final AI Server Verification | NOT_STARTED | - |

---

## 현재 Phase

```text
Phase: 15
Status: VERIFIED
```

---

## 구현 완료

- Phase 14 사전 재검증: Agent 없이 세 Tool 직접 호출 `15 passed`
- LangChain Chat Model의 native `bind_tools`와 `AIMessage.tool_calls`를 사용하는 단일 Agent Loop 구현
- OpenAI/Ollama/Gemini 공식 LangChain Chat Model Adapter와 설정 기반 Factory 추가
- 일반 질문 및 문서 경계가 애매한 질문은 No Tool, 명시적 업로드 문서 검색만
  `search_documents`를 선택하도록 Agent Prompt와 Tool Description 분리/강화
- Backend가 단일 문서를 선택한 Context에서는 검증된 `document_id`를 Prompt 힌트로 제공해
  파일명 요약 요청이 불필요한 목록 조회 없이 `summarize_document`를 직접 호출
- `summarize_document`, `list_documents`를 포함한 네 기본 분기와 Tool Result → 최종 Answer 왕복 구현
- `MAX_AGENT_STEPS=6`, `MAX_TOOL_CALLS=3` 기본 설정과 실행 전 강제 제한으로 무한 Loop 차단
- Tool 오류를 Stack Trace나 내부 상세 없이 안전한 `ToolMessage(status=error)`로 반환하고 재판단 허용
- Agent가 생성한 `user_id`를 Tool Input Validation에서 거부하며, 실제 Service/Backend 호출은
  `ToolExecutionContext`의 `request_id`, `user_id`, 문서 Scope만 사용
- 검색 Citation을 LLM 출력에서 파싱하지 않고 실제 `SearchDocumentsOutput.results`에서 기존
  Retrieval Citation 정책으로 생성하도록 공통 Citation Builder 분리
- `agent/model/tool/limit`의 시작/완료/실패 상태를 `AgentExecutionObserver`로 실시간 관찰할 수 있게
  하되 Phase 17 WebSocket Event 계약은 선행 구현하지 않음
- Multi-Agent, Web Search, WebSocket, Usage Aggregation 등 Phase 16 이후 기능은 구현하지 않음

---

## 검증

- Phase 14 사전 확인
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_tools.py -q`
  - Result: PASS (`15 passed`)
- Agent 결정적 Unit 및 Provider Adapter
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_agent.py tests\unit\adapters\test_agent_model.py -q`
  - Result: PASS (`17 passed`)
  - No Tool 6개(일반 3 + Ambiguous 3), Search/Summary/List, 빈 검색, Scope 위조,
    Tool Error, `MAX_TOOL_CALLS`, `MAX_AGENT_STEPS`, Observable State 검증
- 실제 Gemini Agent 분기 통합
  - Command: `$env:RUN_AGENT_INTEGRATION_TESTS='1'; .\.venv\Scripts\python.exe -m pytest tests\integration\agent\test_agent_provider_integration.py -q`
  - Result: PASS (`1 passed`)
  - 일반 상식/애매한 Qdrant 질문 Tool 0회, Search/Summary/List 각각 정확한 Tool 선택 검증
- 전체 회귀 및 Branch Coverage
  - Command: `.\.venv\Scripts\python.exe -m pytest --cov=app --cov-branch --cov-report=term-missing -q`
  - Result: PASS (`307 passed, 17 skipped`, total coverage `87.70%`)
- 신규 Phase 15 모듈 타입 검사
  - Command: `.\.venv\Scripts\python.exe -m mypy app\services\agent.py app\models\agent.py app\ports\agent.py app\services\citations.py app\adapters\agent_model.py app\factories\agent.py app\services\rag.py app\tools\execution.py`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m compileall -q app scripts tests`
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

- 실제 Spring Backend가 아직 없어 `list_documents` 실제 Internal API 계약 통합 테스트는 미실행.
- Phase 15 Agent 분기는 실제 Gemini로 검증했지만 OpenAI/Ollama 실제 Tool Calling은 미실행.
- 실제 Qdrant/MinIO/LLM Credential이 필요한 기존 조건부 E2E와 기본 비활성 Agent E2E 17개는
  전체 회귀에서 skip.
- 저장소 전체 mypy는 이번 변경과 무관한 기존 21개 오류로 통과하지 않으며,
  Phase 15 신규/영향 모듈 범위의 mypy는 통과.

---

## 변경 파일

- `.env.example`, `pyproject.toml`
- `app/core/config.py`, `app/core/exceptions.py`
- `app/models/agent.py`, `app/ports/agent.py`, `app/prompts/agent.py`
- `app/adapters/agent_model.py`, `app/factories/agent.py`
- `app/services/agent.py`, `app/services/citations.py`, `app/services/rag.py`
- `app/tools/execution.py`
- `tests/unit/test_agent.py`, `tests/unit/adapters/test_agent_model.py`
- `tests/integration/agent/__init__.py`, `tests/integration/agent/test_agent_provider_integration.py`
- `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/FILE_STRUCTURE.md`, `docs/TESTING.md`,
  `docs/PROGRESS.md`

---

## 다음 작업

- Phase 15 필수 범위와 실제 Gemini Tool 선택 검증이 완료되어 Phase 16 진행 가능.
- 다음 Phase에서만 여러 Agent LLM Call의 Usage Aggregation을 구현한다.
- 실제 Spring Backend가 준비되면 `list_documents` Internal API 계약 통합 테스트를 추가한다.

---

## Configuration Update 13.5

```text
Branch: 13.5
Status: VERIFIED
```

### 구현 완료

- 기본 Embedding Provider를 DeepInfra OpenAI 호환 API로 전환
- `Qwen/Qwen3-Embedding-8B`와 4096 Vector Dimension 정책 등록
- `DEEPINFRA_API_KEY`, `DEEPINFRA_BASE_URL`을 기존 LLM/OpenAI/Hugging Face
  Credential과 분리
- `LLM_PROVIDER`/`EMBEDDING_PROVIDER`로 활성 Credential을 선택하고
  `LLM_MODEL`/`EMBEDDING_MODEL`로 실제 모델을 선택하도록 설정 경계 정리
- 기존 `LLM_API_KEY`, `EMBEDDING_API_KEY`, `HF_TOKEN` 설정은 하위 호환 경로로 유지
- Qdrant Collection을 4096차원 전용 이름으로 변경하고 기존 저차원 Collection 자동 재사용 방지
- 로컬 `.env`에 실제 DeepInfra/OpenAI Credential과 모델 정책 반영 (`.gitignore` 유지)

### 검증

- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit/adapters/test_huggingface_embedding_adapter.py tests/unit/adapters/test_openai_embedding_adapter.py tests/unit/test_embedding.py tests/unit/test_config.py tests/unit/test_llm.py -q`
  - Result: PASS (`72 passed`)
- Command: `$env:RUN_EMBEDDING_INTEGRATION_TESTS="1"; .\.venv\Scripts\python.exe -m pytest tests/integration/embedding -q`
  - Result: PASS (`1 passed`, 실제 DeepInfra 인증/4096차원/Usage 검증)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`258 passed, 16 skipped`)
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pip check`
  - Result: PASS (`No broken requirements found`)
- Command: `git diff --check`
  - Result: PASS

### 미검증/남은 문제

- 없음. 비용/Infrastructure가 필요한 기존 조건부 E2E 16개는 기본 전체 회귀에서 skip됨.

### 다음 Phase

- Phase 14 진행 가능.

---

## Phase 14 사전 구조 정비

```text
Status: VERIFIED
```

### 구현 완료

- Qdrant Point/Chunk ID를 길이 구분한 `user_id + document_id + chunk_index` UUID5로 생성해
  동일 `document_id`를 사용하는 사용자 사이의 Point ID 충돌 제거
- 로컬 MinIO Credential 예시와 테스트 문서를 `service-ai-local` /
  `service-ai-local-pw`로 통일
- 코드 기본 Embedding Provider를 문서 및 `.env.example`과 동일한 DeepInfra로 수정
- 조립 전용 모듈을 `app/factories/`로 이동하고 `MinIOStorageAdapter` 표기 통일
- Ingestion의 읽기/파싱/청킹 준비 단계와 임베딩 Batch/측정/Point 조립, Summary의 실행 전략,
  Context의 대화 압축 책임을 각각 별도 모듈로 분리
- Query Rewrite/Context/RAG/Summary의 LLM Fake와 Embedding/Ingestion의 Embedding Fake를
  `tests/fakes.py`로 통합
- `docs/FILE_STRUCTURE.md`를 Phase 13 실제 파일 구조와 기본 Provider 정책에 맞게 갱신
- Phase 14 이후 기능은 선행 구현하지 않음

### 검증

- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`260 passed, 16 skipped`)
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pip check`
  - Result: PASS (`No broken requirements found`)
- Command: `git diff --check`
  - Result: PASS

### 미검증/남은 문제

- 외부 Credential 또는 로컬 Qdrant/MinIO가 필요한 조건부 E2E 16개는 기본 전체 회귀에서 skip됨.
- Phase 14 Tool Layer는 아직 시작하지 않음.

### 다음 Phase

- Phase 14 진행 가능.

---

## Phase 14~20 사전 구조 보완 (2026-08-06)

```text
Status: IMPLEMENTED
```

### 구현 완료

- POST body/query의 `request_id`를 요청 Context, 구조화 로그, 응답 body와 `X-Request-ID`
  응답 헤더에 통일하고, 다른 요청 헤더 값은 `REQUEST_ID_MISMATCH` 422로 거부
- `/ready`에 문서 처리 Service 조립과 필수 Embedding 설정 확인을 추가해 Infrastructure만 정상인
  불완전 상태의 200 응답 방지
- JSON Formatter가 실제 호출부의 allowlist 구조화 필드를 보존하고 민감값을 마스킹하도록 보완
- `ApplicationContainer` Composition Root, Resource 소유권, FastAPI lifespan 경계 및 공유 문서 Runtime
  상태 도입
- Query Rewrite/Conversation Summary fallback을 예상된 `ApplicationError`로 제한하고 구조화 warning을
  남기며 예상 밖 오류는 전파
- Chunking을 `app/chunking/`, Provider 중립 LLM/Embedding DTO를 `app/models/`, Protocol을
  `app/ports/`로 분리하고 Runtime/Admin Port 책임 정리
- `InfrastructureClients` 계열 명칭을 `InfrastructureResources`로, ingestion 보조 모듈을
  `ingestion_components`로 통일
- 문서 상태 Registry에 설정 가능한 상한(`DOCUMENT_STATUS_MAX_ENTRIES`)을 적용하고 오래된 항목 제거
- `.env.example`에 readiness/상태 Registry 정책을 추가하고 tokenizer 기본값과 문서값 동기화
- Qdrant Collection 정책을 Embedding Service에서 `vector_collection` Service로 분리하고 구형
  모듈/수동 CLI/미사용 예외 제거
- 직접 import하는 `anyio`, `pydantic`, `starlette`, `urllib3`를 명시적 런타임 의존성으로 등록하고
  `mypy`, `pytest-cov`, `httpx2`를 개발 의존성으로 등록
- `scripts/manual_*.py` 6개를 파일 상단 변수 수정 후 직접 `.py` 실행하는 형식으로 제공
- 테스트를 `unit/component/contract/integration/smoke`로 재분류하고 Composition 소유권,
  request_id, readiness, logging, fallback, Registry 상한, 수동 실행 회귀 추가
- README와 `ARCHITECTURE.md`, `CONTRACTS.md`, `FILE_STRUCTURE.md`, `TESTING.md`,
  `DECISIONS.md`를 실제 코드 구조와 계약에 맞게 동기화
- Phase 14 Tool Layer 이후 기능은 선행 구현하지 않음

### 검증

- Command: `.\.venv\Scripts\python.exe -m pytest`
  - Result: PASS (`275 passed, 16 skipped`)
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe scripts\manual_chunking.py`
  - Result: PASS (파일 상단 변수 기반 Parser/Chunking JSON 출력)
- Command: `.\.venv\Scripts\python.exe -m compileall -q app scripts tests`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pip check`
  - Result: PASS (`No broken requirements found`)
- Command: `git diff --check`
  - Result: PASS

### 미검증/남은 문제

- 개발 의존성 동기화(`pip install -e ".[dev]"`)는 실행 환경의 승인 사용량 제한으로 완료하지 못함.
  따라서 새 `mypy`와 branch coverage 80% gate는 아직 실행하지 않았으며 이 항목 때문에 상태를
  `VERIFIED`로 올리지 않음.
- 현재 가상환경에 `httpx2`가 아직 설치되지 않아 테스트는 Starlette의 `httpx` deprecation warning
  1건을 출력한다. `pyproject.toml`에는 교체용 개발 의존성을 반영함.
- 외부 Credential 또는 로컬 Infrastructure가 필요한 기존 조건부 E2E 16개는 기본 회귀에서 skip됨.

### 다음 Phase

- 기능 구조와 비용 없는 회귀 기준으로 Phase 14 진행 가능.
- 개발 환경 의존성을 동기화한 뒤 `mypy`와 coverage 80%를 통과해야 본 구조 보완을 `VERIFIED`로
  변경할 수 있음.

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
