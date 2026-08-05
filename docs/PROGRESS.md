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
Phase: 03
Status: VERIFIED
```

---

## 구현 완료

- SDK 독립 `LLMRequest`, `LLMResult`, `LLMUsage`, `LLMProvider` Port
- Provider 중립 `LLMService`와 설정 기반 Provider Factory
- OpenAI Responses API Adapter와 Adapter 외부 SDK 타입 비노출
- Ollama Cloud Native Chat API Adapter와 `glm-5.2` 설정 지원
- Google Gemini Interactions API Adapter와 `gemini-3.6-flash` 지원
- `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` 설정 및 Timeout/Max Output Tokens/Temperature 설정
- Provider 응답의 input/output/total/cached input/reasoning token을 공통 Usage로 직접 매핑
- Provider가 반환하지 않는 Usage 값은 추정하지 않고 `None`으로 유지
- `perf_counter` 기반 LLM Call latency 측정
- Authentication, Authorization, Rate Limit, Timeout, Connection, Provider 5xx, Invalid Response, Unknown Provider 오류 표준화
- OpenAI SDK 자동 Retry 비활성화 및 Phase 03 별도 Retry 미적용
- Ollama HTTP 호출 별도 Retry 미적용
- Gemini HTTP 호출 별도 Retry 미적용
- Agent/RAG와 무관한 `python -m scripts.test_llm` 개발용 CLI
- Credential이 있을 때만 실제 호출하는 독립 LLM Integration Test

---

## 검증

- Phase 01~02 문서 상태 확인: 두 Phase 모두 `VERIFIED`
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit -q`
  - Result: PASS (`66 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/integration/llm -q`
  - Result: SKIP (`1 skipped`; `RUN_LLM_INTEGRATION_TESTS` 미설정 시 비용 방지)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`72 passed, 5 skipped`; 실제 Infrastructure/LLM Test만 조건부 skip)
- Command: Ollama Credential로 `GET https://ollama.com/api/tags`
  - Result: PASS (`HTTP 200`, `glm-5.2` 모델 확인, API Key 인증 확인)
- Command: `RUN_LLM_INTEGRATION_TESTS=1`로 Ollama `glm-5.2` 실제 생성 호출
  - Result: BLOCKED (`HTTP 403`; 해당 모델은 Ollama 구독 권한 필요)
- Command: Ollama CLI 모델명 `qwen3.5:397b-cloud`를 직접 Cloud API 모델명으로 확인
  - Result: PASS (`/api/tags`에서 `qwen3.5:397b` 식별자 확인)
- Command: `RUN_LLM_INTEGRATION_TESTS=1`로 Ollama `qwen3.5:397b` 실제 생성 호출
  - Result: BLOCKED (`HTTP 403`; 해당 모델도 Ollama 구독 권한 필요)
- Command: Ollama CLI 모델명 `gpt-oss:20b-cloud`를 직접 Cloud API 모델명으로 확인
  - Result: PASS (`/api/tags`에서 `gpt-oss:20b` 식별자 확인)
- Command: `RUN_LLM_INTEGRATION_TESTS=1`로 Ollama `gpt-oss:20b` 실제 생성 호출
  - Result: PASS (`1 passed`; Content/Provider/Model/Usage/Latency/Status 확인)
- Command: `.\.venv\Scripts\python.exe -m scripts.test_llm`
  - Result: PASS (`input_tokens=80`, `output_tokens=107`, `latency_ms=1794`, `status=COMPLETED`)
- Command: Gemini Credential로 `GET /v1beta/models`
  - Result: PASS (`HTTP 200`, `gemini-3.6-flash` 사용 가능 확인)
- Command: `RUN_LLM_INTEGRATION_TESTS=1`로 Gemini `gemini-3.6-flash` 실제 생성 호출
  - Result: PASS (`1 passed`; Content/Provider/Model/Usage/Latency/Status 확인)
- Command: Gemini 설정으로 `.\.venv\Scripts\python.exe -m scripts.test_llm`
  - Result: PASS (`input=14`, `output=8`, `total=256`, `reasoning=234`, `latency_ms=4367`)
- Command: `git diff --check`
  - Result: PASS

---

## 현재 Blocker

없음.

---

## 미검증 항목

- 실제 OpenAI Provider 호출은 Credential 미제공으로 미검증이며 Mock 검증만 완료.
- Ollama `glm-5.2`와 `qwen3.5:397b`는 구독 권한 부족으로 생성 미검증.
- Ollama `gpt-oss:20b` 실제 Content, input/output Token Usage, Latency 검증 완료.
- Ollama가 반환하지 않는 total/cached/reasoning Token은 실제 응답에서도 `null`로 확인.
- Gemini `gemini-3.6-flash` 실제 Content와 전체 Token Usage, Latency 검증 완료.
- Agent, Tool Calling, RAG, Query Rewrite, Summary, Conversation Summary는 Phase 03 제외 범위로 구현하지 않음.

---

## 변경 파일

- `.env.example`
- `pyproject.toml`
- `app/core/config.py`
- `app/core/exceptions.py`
- `app/adapters/openai.py`
- `app/adapters/ollama.py`
- `app/adapters/gemini.py`
- `app/llm.py`
- `app/ports/llm.py`
- `app/services/__init__.py`
- `app/services/llm.py`
- `scripts/__init__.py`
- `scripts/test_llm.py`
- `tests/unit/test_config.py`
- `tests/unit/test_llm.py`
- `tests/unit/adapters/test_openai_adapter.py`
- `tests/unit/adapters/test_ollama_adapter.py`
- `tests/unit/adapters/test_gemini_adapter.py`
- `tests/integration/llm/__init__.py`
- `tests/integration/llm/test_llm_integration.py`
- `docs/FILE_STRUCTURE.md`
- `docs/TESTING.md`
- `docs/PROGRESS.md`

---

## 다음 작업

- Phase 03 실제 Provider 응답과 Token Usage 검증 완료.
- `Phase 04 — Embedding Provider` 진행 가능.

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
