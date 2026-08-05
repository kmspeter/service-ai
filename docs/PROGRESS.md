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
Phase: 07
Status: VERIFIED
```

---

## 구현 완료

- Backend 전용 `POST /internal/documents`와 Contract DTO
- `request_id`, `user_id`, `document_id`, `storage_key` 실행 Context Validation
- MinIO 원본 조회 → Parser Registry → AI Validation → 통계 → Recursive Chunking → Batch Embedding → Qdrant 저장 Pipeline
- TXT/MD/PDF Parser 통합과 손상/암호화 PDF 표준 실패 결과
- 파싱 결과가 비어 있거나 공백뿐인 문서는 `FAILED / DOCUMENT_EMPTY`로 처리하고 빈 Vector를 만들지 않는 정책
- `file_size`, `page_count`, `character_count`, `token_count`, `chunk_count`, `embedding_token_count`, Parsing/Embedding 시간 결과
- Qdrant `id=chunk_id`, `vector=embedding`, 필수 Citation Payload와 추가 처리 통계
- 전 Embedding Batch 성공 후에만 Qdrant 저장을 시작하여 Embedding 부분 성공을 문서 성공으로 오인하지 않는 정책
- 동일 `document_id` 처리 직렬화, 기존 Point 교체, Qdrant 저장 실패 시 잔여 신규 Point 보상 삭제
- Storage/Parser/Empty/Embedding/Qdrant 단계별 표준 `failure_reason`과 HTTP 상태
- 공백 전용 Chunk를 제외하여 빈 Embedding 입력을 만들지 않도록 Chunker 보강
- Hugging Face `hf-inference` 기반 `unsloth/Qwen3-Embedding-0.6B` Batch Adapter와 1024차원 정책
- Hugging Face 인증/권한/Rate Limit/Timeout/Connection/Provider/응답 오류 표준화
- `EMBEDDING_PROVIDER=huggingface`, `HF_TOKEN`, Provider별 Credential Validation
- 기존 1536차원 Collection을 자동 변경하지 않고 Qwen용 1024차원 Collection 분리

---

## 검증

- Phase 01~06 사전 검증
  - Git: `main`에 Phase 01~06 완료 커밋 `c90e03a` → `95c91e9` 포함 확인
  - Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`142 passed, 8 skipped`)
  - Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
  - Command: `.\.venv\Scripts\python.exe -m pip check`
  - Result: PASS (`No broken requirements found`)
- Phase 07 Unit/API Regression
  - TXT/MD/PDF 전체 Pipeline, Batch Embedding, 필수 Qdrant Payload, Object 없음, 지원 Parser 없음,
    빈 문서, 손상/암호화 PDF, 두 번째 Embedding Batch 실패, Qdrant 실패, 교체/보상 호출 검증
- Hugging Face Embedding Adapter Unit
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\adapters\test_huggingface_embedding_adapter.py tests\unit\test_embedding.py tests\unit\test_config.py -q`
  - Result: PASS (`39 passed`)
  - 1024차원 Qwen 모델 선택, Batch 요청, 정규화/Truncation, 응답 검증과 표준 오류 매핑 확인
- 실제 Infrastructure CLI 검증
  - 임시 MinIO `127.0.0.1:19000`, Qdrant `127.0.0.1:16333` 사용 후 제거
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\integration\ingestion\test_local_infrastructure_pipeline.py -q`
  - Result: PASS (`1 passed`)
  - TXT/MD/PDF HTTP 처리, Parser/Chunk/Embedding 생성, 실제 Qdrant Point 생성 확인
  - Qdrant Scroll로 `document_id`, `user_id`, `filename`, `page`, `chunk_id`, `chunk_text`, Vector dimension 직접 확인
  - 존재하지 않는 `storage_key`, 손상 PDF, 암호화 PDF의 `FAILED` 결과 확인
  - 동일 `document_id` 재처리 후 이전 Point가 남지 않고 새 1개 Point만 존재함을 확인
- Command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_ingestion.py tests\unit\adapters\test_qdrant_adapter.py tests\integration\test_document_ingestion_api.py -q`
  - Result: PASS (`20 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`177 passed, 10 skipped`; 조건부 외부 Infrastructure/LLM/Embedding/Ingestion Test)
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pip check`
  - Result: PASS (`No broken requirements found`)
- Command: `git diff --check`
  - Result: PASS
- `.env` 동기화 및 실제 설정 검증
  - `.env.example`의 섹션/키 순서에 맞춰 `.env`를 재구성하고 기존 Secret과 실행 중인 로컬 Infrastructure 값을 반영
  - Secret 값을 출력하지 않고 Hugging Face/LLM Credential 존재 여부, Qdrant/MinIO 필수 설정, 1024차원 Collection 분리를 확인
  - Qdrant `http://127.0.0.1:6333`, MinIO `http://127.0.0.1:9000` Health PASS
- 실제 Infrastructure 및 외부 LLM 검증
  - Command: 모든 `.env` 설정과 `RUN_INFRASTRUCTURE_TESTS=1`, `RUN_LLM_INTEGRATION_TESTS=1`을 적용한 Infrastructure/LLM/결정적 Ingestion Integration Test
  - Result: PASS (`8 passed`)
- 전체 조건부 Test를 모두 활성화한 무-skip 검증
  - Command: `RUN_INFRASTRUCTURE_TESTS=1`, `RUN_LLM_INTEGRATION_TESTS=1`, `RUN_EMBEDDING_INTEGRATION_TESTS=1`, `RUN_INGESTION_INTEGRATION_TESTS=1` 적용 후 `pytest -q`
  - 최초 Result: FAIL (`183 passed, 4 failed, 0 skipped`)
  - 환경변수 미존재 Unit Test 2건은 테스트 격리 결함으로 확인하여 `monkeypatch.delenv`를 적용했고, 환경값 주입 상태에서 `10 passed` 및 Ruff PASS
  - 수정 후 Result: FAIL (`185 passed, 2 failed, 0 skipped`)
  - 남은 실패 2건은 실제 Embedding 호출과 해당 Embedding을 사용하는 실제 Ingestion 호출이며 둘 다 같은 Provider HTTP 404가 원인
- Hugging Face 실제 제공 상태 진단
  - Hub Model API: `Qwen/Qwen3-Embedding-0.6B`, provider=`hf-inference`, task=`feature-extraction`, status=`error`, inference=`None`
  - 공식 Router의 모델 경로와 feature-extraction 경로 모두 실제 인증 요청에서 HTTP 404 확인
  - 사용자가 제시한 `unsloth/Qwen3-Embedding-0.6B` 확인 결과 provider=`hf-inference`, task=`feature-extraction`, status=`live`, inference=`warm`
  - 실제 단일 한국어 입력 호출에서 정상 `(1, 1024)` Vector 반환 확인
- 최종 전체 무-skip 검증
  - Command: 모든 실제 통합 플래그를 `1`로 적용한 `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`187 passed, 0 skipped`)
  - 실제 Hugging Face Embedding, 실제 LLM, 실제 MinIO/Qdrant, TXT/MD/PDF Ingestion 포함
- 실제 Uvicorn + curl E2E
  - MinIO에 TXT/MD/PDF Fixture 3개를 올리고 `curl POST /internal/documents` 실행
  - Result: TXT `COMPLETED` 1 chunk, MD `COMPLETED` 3 chunks, PDF `COMPLETED` 1 chunk
  - Qdrant REST Scroll을 curl로 직접 호출해 Point 5개와 1024차원 Vector 확인
  - 모든 Point에서 `chunk_text`, `user_id`, `document_id`, `filename`, `page`, `chunk_id` 확인
  - 임시 MinIO Object, Qdrant Collection, 서버 로그 제거 완료
- 최종 품질/보안 검사
  - Ruff PASS, `pip check` PASS, `git diff --check` PASS
  - Hugging Face Token 패턴이 `.env` 밖에 없음을 확인

---

## 현재 Blocker

- 없음.

---

## 미검증 항목

- 없음.

---

## 변경 파일

- `.env.example`, `README.md`, `pyproject.toml`
- `app/api/documents.py`, `app/api/router.py`
- `app/core/config.py`, `app/main.py`, `app/ingestion.py`
- `app/models/ingestion.py`, `app/schemas/documents.py`
- `app/ports/qdrant.py`, `app/adapters/qdrant.py`
- `app/adapters/huggingface_embedding.py`, `app/embedding.py`
- `app/services/ingestion.py`, `app/services/chunking.py`
- `tests/unit/test_ingestion.py`, `tests/unit/test_config.py`
- `tests/unit/adapters/test_qdrant_adapter.py`
- `tests/unit/adapters/test_huggingface_embedding_adapter.py`
- `tests/integration/test_document_ingestion_api.py`
- `tests/integration/ingestion/test_local_infrastructure_pipeline.py`
- `tests/integration/ingestion/test_ingestion_integration.py`
- `docs/FILE_STRUCTURE.md`, `docs/PROGRESS.md`, `docs/TESTING.md`

---

## 다음 작업

- Phase 08 진행 가능.

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
