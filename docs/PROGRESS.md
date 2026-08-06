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
Phase: 13
Status: VERIFIED
```

---

## 구현 완료

- Backend가 전달한 `Conversation Summary`와 `Recent Messages`만 가공하는 `ContextBudgetManager` 구현
- `LLM_CONTEXT_WINDOW - LLM_MAX_OUTPUT_TOKENS`로 Output 공간을 먼저 예약하고 실제 입력 상한 확정
- `MAX_RECENT_MESSAGES`와 Token Budget을 함께 적용해 가장 오래된 Message부터 제거하는 Sliding Window 구현
- 잘리는 History를 bounded batch로 갱신하는 별도 Conversation Summary Prompt 구현
- Summary Prompt에 입력 외 사실·수치·결론 추가 금지와 대화 내 지시 실행 금지 규칙 적용
- Query Rewrite와 최종 RAG Answer가 동일한 압축 Conversation Context를 사용하도록 통합
- Conversation Summary, Recent Messages, RAG Context, Current Question, Prompt, Output Reservation별 Token 계측 모델 구현
- 최종 완성 Prompt 전체 Token을 다시 측정하고 Context Window 초과 시 LLM 호출 전 명시적 오류 처리
- 남은 실제 Prompt 예산과 `MAX_CONTEXT_TOKENS`에 따라 RAG Chunk 수/첫 Chunk 길이를 제한
- 생성·가공한 Summary와 실제 Recent Messages를 응답 내부 모델에 반환해 Backend가 원본/요약을 관리할 경계 유지
- Conversation 원본 DB, Agent/Tool, WebSocket/API Contract 등 Phase 14 이후 기능은 구현하지 않음

---

## 검증

- Phase 12 사전 상태 확인
  - `docs/PROGRESS.md`: Phase 12 `VERIFIED`, Blocker 없음 확인
- Context Budget Unit 및 RAG 경계 Integration
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_context.py tests\unit\test_rag.py tests\unit\test_config.py tests\integration\rag\test_rag_pipeline.py -q`
  - Result: PASS (`35 passed`)
  - 2/20개 Message, 매우 긴 Message, 매우 큰 RAG, Summary 유/무, Window 근접,
    Output Reservation, 최종 Prompt Token 재계산, overflow 사전 실패 검증
- 전체 회귀
  - Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`253 passed, 16 skipped`)
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

- 실제 외부 LLM Provider를 사용한 Conversation Summary 생성은 Credential/비용이 필요한 조건부 검증으로 실행하지 않음.
- Context 계산, 호출별 상한, RAG 통합은 결정적 Fake Provider로 검증 완료.

---

## 변경 파일

- `.env.example`
- `app/core/config.py`, `app/core/exceptions.py`
- `app/models/context.py`, `app/models/rag.py`
- `app/prompts/conversation_summary.py`, `app/prompts/rag.py`
- `app/services/context.py`, `app/services/rag.py`, `app/services/rag_context.py`, `app/rag.py`
- `tests/unit/test_context.py`, `tests/unit/test_config.py`, `tests/unit/test_rag.py`
- `tests/integration/rag/test_rag_pipeline.py`
- `docs/TESTING.md`, `docs/PROGRESS.md`

---

## 다음 작업

- Phase 13 필수 범위와 비용 없는 전체 회귀 검증이 완료되어 Phase 14 진행 가능.
- 다음 Phase에서는 검증된 Service를 중복 구현하지 않고 Tool 경계로 노출한다.

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
