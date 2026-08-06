# AI Server Testing Guide

## 1. 목적

AI Server를 Backend 없이도 최대한 독립적으로 검증하고, 각 Phase 완료 여부를 반복 가능하게 판단한다.

최종 테스트 명령은 실제 프로젝트 Skeleton과 의존성 관리 방식이 확정된 후 이 문서에 유지한다.

---

# 2. 테스트 계층

```text
Unit Test
    ↓
Component Test
    ↓
Contract Test
    ↓
Integration Test
    ↓
Smoke / Manual .py / curl
    ↓
WebSocket Client
    ↓
AI Server End-to-End
```

기능별로 모든 계층이 항상 필요한 것은 아니지만, 외부 시스템과 연결되는 기능은 Unit Test만으로 완료 처리하지 않는다.

---

# 3. 권장 테스트 디렉터리

```text
tests/
├─ unit/
│  ├─ parsers/
│  ├─ chunking/
│  └─ adapters/
│
├─ component/                    # Fake Port로 여러 Service를 조립한 흐름
├─ contract/                     # FastAPI HTTP/DTO/오류/header 계약
├─ smoke/                        # 수동 스크립트 import/직접 실행
│
├─ integration/
│  ├─ qdrant/
│  ├─ minio/
│  ├─ embedding/
│  ├─ llm/
│  ├─ rag/
│  ├─ query_rewrite/
│  └─ summary/
│
└─ fixtures/documents/
   ├─ sample.txt / sample.md / sample.pdf
   ├─ multi_page.pdf / encrypted.pdf / corrupted.pdf
   └─ empty.txt
```

Fixture에 실제 민감 문서를 넣지 않는다.

---

# 4. 기본 테스트 명령

프로젝트 초기 구성에서 `pytest` 사용을 기본으로 한다.

Windows PowerShell에서는 저장소의 Python 3.12 가상환경을 사용한다.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Unit:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit
```

Integration:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration
```

Component / Contract / Smoke:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/component tests/contract tests/smoke
```

Phase 02 실제 Infrastructure Integration Test:

```powershell
$env:RUN_INFRASTRUCTURE_TESTS="1"
$env:QDRANT_URL="http://localhost:6333"
$env:MINIO_URL="http://localhost:9000"
$env:MINIO_ACCESS_KEY="service-ai-local"
$env:MINIO_SECRET_KEY="service-ai-local-pw"
.\.venv\Scripts\python.exe -m pytest tests/integration/qdrant tests/integration/minio -q
```

이 테스트들은 고유한 test collection/bucket을 만들고 가능한 경우 `finally`에서 정리한다. 환경변수가
없거나 `RUN_INFRASTRUCTURE_TESTS=1`이 아니면 실제 Infrastructure Test는 명시적으로 skip된다.

특정 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/parsers
```

정적 검사와 커버리지 기준:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
```

Coverage는 branch coverage를 포함하며 `pyproject.toml`의 최소 80% 기준을 적용한다. `mypy`와
`pytest-cov`가 없다면 먼저 `pip install -e ".[dev]"`로 개발 의존성을 동기화한다.

## 4.1 수동 `.py` 실행

CLI 인자 대신 각 파일 상단의 대문자 변수만 수정한다. Credential과 Endpoint는 `.env`에서 읽는다.
저장소 루트에서 다음처럼 실행한다.

```powershell
.\.venv\Scripts\python.exe scripts\manual_chunking.py
.\.venv\Scripts\python.exe scripts\manual_ingestion.py
.\.venv\Scripts\python.exe scripts\manual_retrieval.py
.\.venv\Scripts\python.exe scripts\manual_rag.py
.\.venv\Scripts\python.exe scripts\manual_summary.py
.\.venv\Scripts\python.exe scripts\manual_llm.py
```

`manual_ingestion.py`는 `STORAGE_KEY`의 객체가 MinIO에 미리 있어야 한다. 외부 Provider를 사용하는
나머지 스크립트는 API 비용이 발생할 수 있다. `tests/smoke/test_manual_scripts.py`는 import 시 외부
호출이 발생하지 않는지와 비용 없는 chunking 스크립트의 직접 `.py` 실행을 검증한다.

---

# 5. Health Test

## `/health`

```bash
curl http://localhost:8000/health
```

검증:

- HTTP 200
- FastAPI Process 정상

## `/ready`

```bash
curl http://localhost:8000/ready
```

검증 대상:

- 필수 설정
- Qdrant
- MinIO bucket
- 현재 노출된 문서 처리 Service 조립
- 문서 처리에 필요한 Embedding 설정

`READINESS_REQUIRE_DOCUMENT_PROCESSING=true`가 기본이며, Qdrant/MinIO만 정상이고 문서 처리
서비스가 조립되지 않은 경우에도 HTTP 503이어야 한다. 외부 유료 Provider probe는 수행하지 않는다.

## request_id / 구조화 로그

```powershell
.\.venv\Scripts\python.exe -m pytest tests\contract tests\unit\test_logging.py -q
```

검증:

- POST body 또는 query `request_id`와 응답 body/header/log의 ID 일치
- 서로 다른 `X-Request-ID`와 body/query ID는 `REQUEST_ID_MISMATCH` 422
- allowlist extra 필드가 JSON 최상위에 보존됨
- API Key, Authorization/Bearer Token 등 민감값이 message/exception에서 마스킹됨

---

# 6. Qdrant Test

검증:

- 연결
- Collection
- Vector Dimension
- Insert
- Search
- Filter
- Delete

필수 보안/격리 시나리오:

```text
user-001 문서
→ user-001 검색: 검색됨

user-001 문서
→ user-002 검색: 검색 안 됨
```

문서 Filter:

```text
doc-001
→ document_id=doc-001: 검색됨

doc-001
→ document_id=doc-002: 검색 안 됨
```

Phase 08:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_document_management.py tests\unit\adapters\test_qdrant_adapter.py tests\integration\test_document_management_api.py -q
$env:RUN_INFRASTRUCTURE_TESTS="1"
.\.venv\Scripts\python.exe -m pytest tests\integration\qdrant -q
```

삭제 검증:

- `user_id + document_id`가 모두 일치하는 Point 전체 삭제
- 같은 사용자의 다른 문서 보존
- 같은 `document_id`를 가진 다른 사용자 Point 보존
- 없는 문서는 `NOT_FOUND`
- Qdrant 오류는 `FAILED / QDRANT_DELETE_FAILED / retryable=true`
- Backend Metadata와 MinIO Object는 변경하지 않음

상태 검증:

- `PROCESSING`, `COMPLETED`, `FAILED`
- Qdrant payload 기반 `COMPLETED` 복원
- 모르는 문서와 다른 user Scope는 HTTP 404
- 별도 Backend Document 복제 DB가 없음

---

# 7. MinIO Test

검증:

- 연결
- Bucket 접근
- Object 업로드
- Object 읽기
- 존재하지 않는 Object
- 삭제
- 잘못된 Credential

개발 테스트 Object는 테스트 종료 후 정리한다.

---

# 8. LLM Provider Test

최소 시나리오:

```text
입력:
"1+1을 짧게 답해줘."
```

검증:

- 응답 Content
- Provider
- Model
- Input Tokens
- Output Tokens
- Total Tokens
- Latency
- Status

오류:

- 잘못된 API Key
- Timeout
- 429/일시적 오류를 재현 가능한 경우
- Provider가 Optional Usage를 제공하지 않는 경우

실제 Provider 호출 테스트는 비용이 발생할 수 있으므로 Unit Test에서는 Mock을 사용하고 실제 Integration Test를 구분한다.

Phase 03 Unit Test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/adapters/test_openai_adapter.py tests/unit/adapters/test_ollama_adapter.py tests/unit/adapters/test_gemini_adapter.py tests/unit/test_llm.py -q
```

실제 Provider Integration Test는 다음 실행 Flag와 `.env` 또는 환경변수의 Provider 설정이 모두 있을 때 호출한다.

```text
RUN_LLM_INTEGRATION_TESTS=1
LLM_PROVIDER
LLM_API_KEY
LLM_MODEL
```

```powershell
$env:RUN_LLM_INTEGRATION_TESTS="1"
.\.venv\Scripts\python.exe -m pytest tests/integration/llm -q
```

Agent/RAG와 무관한 수동 LLM 실행:

```powershell
.\.venv\Scripts\python.exe scripts\manual_llm.py
```

실행 Flag나 실제 Credential이 없으면 Integration Test는 실패가 아니라 명시적으로 skip된다. 수동 스크립트는 필수 설정 누락을
보고한다. OpenAI Adapter는 SDK의 자동 Retry를 비활성화하며 Phase 03에서는 별도 Retry를 적용하지 않는다.
Ollama Adapter도 HTTP Client 기본 1회 호출만 수행하고 별도 Retry를 적용하지 않는다.

검증된 Ollama Cloud 설정 예:

```text
LLM_PROVIDER=ollama
LLM_API_KEY=<ollama-api-key>
LLM_MODEL=gpt-oss:20b
```

Ollama Cloud URL과 Bearer 인증 방식은 Adapter 내부 Provider 설정이므로 별도 환경변수가 필요하지 않다.

검증된 Google Gemini 설정 예:

```text
LLM_PROVIDER=gemini
LLM_API_KEY=<gemini-api-key>
LLM_MODEL=gemini-3.6-flash
```

Gemini Adapter는 Google Interactions API를 사용한다. Gemini 3.6의 deprecated sampling 정책에 따라
Temperature를 해당 모델의 요청에 전달하지 않는다.

---

# 9. Embedding Test

검증:

- 단일 Text
- Batch Text
- Dimension
- 빈 입력
- Provider 오류
- Timeout
- Provider Usage와 Latency

필수:

```text
Embedding Dimension
==
Qdrant Collection Vector Dimension
```

Phase 04 Unit Test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/adapters/test_huggingface_embedding_adapter.py tests/unit/adapters/test_openai_embedding_adapter.py tests/unit/test_embedding.py tests/unit/test_config.py -q
```

기본 Provider인 DeepInfra Embedding 호출은 다음 설정이 모두 있을 때만 실행한다.

```text
RUN_EMBEDDING_INTEGRATION_TESTS=1
EMBEDDING_PROVIDER=deepinfra
DEEPINFRA_API_KEY
DEEPINFRA_BASE_URL=https://api.deepinfra.com/v1/openai
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_TIMEOUT_SECONDS=30
```

```powershell
$env:RUN_EMBEDDING_INTEGRATION_TESTS="1"
.\.venv\Scripts\python.exe -m pytest tests/integration/embedding -q
```

`Qwen/Qwen3-Embedding-8B`의 기본 Vector Dimension은 4096다. DeepInfra Adapter는
OpenAI 호환 Endpoint를 Batch로 호출하고, 반환된 모든 Vector의 개수·Dimension·유한값과
입력 순서를 검증한다. Provider가 Token Usage를 제공하면 그대로 집계한다.

Hugging Face 회귀 경로는 `EMBEDDING_PROVIDER=huggingface`, `HF_TOKEN`,
`unsloth/Qwen3-Embedding-0.6B` 설정으로 별도 검증할 수 있다. 공용 API가 Token Usage를
제공하지 않으면 `embedding_token_count`를 추정하지 않고 `null`로 유지한다.

OpenAI 회귀 경로는 `EMBEDDING_PROVIDER=openai`, `EMBEDDING_API_KEY`, 지원 모델 설정으로
별도 검증할 수 있다.

Qdrant Collection은 명시적인 `EmbeddingService.ensure_qdrant_collection` 호출에서만 생성한다.
Collection이 없으면 Cosine/Provider Dimension으로 생성하고, 기존 Collection의 Dimension이 다르면 삭제하거나
재생성하지 않고 `QDRANT_VECTOR_DIMENSION_MISMATCH` 오류를 발생시킨다.
기존 1024/1536차원 Collection에서 전환할 때는 별도 4096차원 Collection 이름을 사용한다.

실제 Qdrant Dimension Integration Test:

```powershell
$env:RUN_INFRASTRUCTURE_TESTS="1"
$env:QDRANT_URL="http://127.0.0.1:6333"
.\.venv\Scripts\python.exe -m pytest tests/integration/qdrant -q
```

---

# 10. Parser Test

## TXT

- UTF-8 Text
- 빈 Text
- 긴 Text

## MD

- Heading
- Section
- 일반 Paragraph
- 빈 문서

## PDF

- 정상 PDF
- 여러 Page
- 손상 PDF
- 암호화 PDF

검증:

```text
filename
file_type
page_count
character_count
content
page
section
```

---

# 11. Chunking Test

환경값:

```text
CHUNK_SIZE
CHUNK_OVERLAP
```

검증:

- Chunk 생성
- Chunk 순서
- Overlap
- 매우 짧은 문서
- 매우 긴 문서
- Metadata 유지
- page/section 유지

필수:

```text
chunk_id
document_id
filename
page/section
chunk_text
```

Phase 06 Unit Test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/chunking tests/unit/test_config.py -q
```

개발용 Parser → Chunking 확인(`manual_chunking.py` 상단 변수 수정):

```powershell
.\.venv\Scripts\python.exe scripts\manual_chunking.py
```

정책:

- `CHUNK_SIZE`와 `CHUNK_OVERLAP`은 `TOKENIZER_MODEL` 또는 명시적인
  `TOKENIZER_ENCODING`의 token 단위다.
- PDF는 Page별로, MD는 Parser Section별로 독립 분할하여 Citation 위치 경계를 넘지 않는다.
- Overlap도 같은 Page/Section 안에서만 적용한다.
- TXT는 순서가 안정적인 `chunk_index`와 고유 `chunk_id`를 원본 위치 식별자로 사용한다.
- 빈 문서는 빈 Chunk를 생성하지 않고 `token_count=0`, `chunk_count=0`으로 계산한다.

---

# 12. Document Ingestion Test

요청 실행 예:

```powershell
curl.exe -X POST http://localhost:8000/internal/documents `
  -H "Content-Type: application/json" `
  -d '@request.json'
```

검증 흐름:

```text
MinIO Object
↓
Parser
↓
Chunking
↓
Embedding
↓
Qdrant
```

확인:

- Qdrant Point 수
- document_id
- user_id
- filename
- page
- chunk_id
- chunk_text
- Vector Dimension

실패:

- MinIO Object 없음
- 손상 PDF
- 암호화 PDF
- Embedding 실패
- Qdrant 실패

정책:

- MinIO Object를 읽은 뒤 `storage_key`의 filename으로 Parser Registry를 조회한다.
- 파싱 결과가 비어 있거나 공백뿐이면 `FAILED / DOCUMENT_EMPTY`이며 Embedding과 Qdrant 저장을 실행하지 않는다.
- 모든 Embedding Batch가 성공한 뒤에만 Qdrant 교체를 시작한다.
- 재처리의 Parsing/Embedding 실패 시에는 이전 완료 Point 집합을 그대로 유지한다.
- 새 Embedding 전체가 준비되면 `document_id` 범위 기존 Point를 제거하고 전체 신규 Point를 저장한다.
- Qdrant 신규 Point 저장이 실패하면 같은 `document_id`의 잔여 Point 정리를 시도하며 성공으로 응답하지 않는다.
- 같은 `document_id`의 동시 처리는 직렬화한다.

Unit/API Regression:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_ingestion.py `
  tests\unit\adapters\test_qdrant_adapter.py `
  tests\integration\test_document_ingestion_api.py -q
```

실제 MinIO/Qdrant + 비용 없는 결정적 Integration Embedding Provider:

```powershell
$env:RUN_INFRASTRUCTURE_TESTS='1'
.\.venv\Scripts\python.exe -m pytest `
  tests\integration\ingestion\test_local_infrastructure_pipeline.py -q
```

실제 외부 Embedding Provider까지 포함한 TXT/MD/PDF Endpoint 및 Qdrant Payload 검증:

```powershell
$env:RUN_INGESTION_INTEGRATION_TESTS='1'
.\.venv\Scripts\python.exe -m pytest `
  tests\integration\ingestion\test_ingestion_integration.py -q
```

마지막 테스트는 `QDRANT_*`, `MINIO_*`, 선택 Provider의 Credential, `EMBEDDING_MODEL` 설정과
실행 중인 Infrastructure가 필요하며 외부 API 비용이 발생할 수 있다.

---

# 13. Retrieval Test

질문 예:

```text
문서에 명확하게 존재하는 내용
문서와 일부 관련된 내용
문서에 존재하지 않는 내용
```

검증:

- Query Embedding
- Top-K
- Score Threshold
- user_id Filter
- document_id/document_ids Filter
- Result Metadata

Phase 09 Unit/Adapter Test:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_retrieval.py `
  tests\unit\adapters\test_qdrant_adapter.py `
  tests\unit\test_config.py -q
```

실제 Qdrant에서 비용 없는 결정적 Vector로 Scope/품질/Top-K/Threshold 검증:

```powershell
$env:RUN_INFRASTRUCTURE_TESTS='1'
$env:QDRANT_URL='http://127.0.0.1:6333'
.\.venv\Scripts\python.exe -m pytest `
  tests\integration\retrieval\test_retrieval_integration.py -q
```

실제 Embedding Provider와 Qdrant를 연결하는 선택형 품질 검증:

```powershell
$env:RUN_RETRIEVAL_INTEGRATION_TESTS='1'
$env:QDRANT_URL='http://127.0.0.1:6333'
.\.venv\Scripts\python.exe -m pytest `
  tests\integration\retrieval\test_retrieval_provider_integration.py -q
```

마지막 테스트는 선택 Provider Credential과 외부 네트워크를 사용하며 API 비용이 발생할 수 있다.

개발 Collection의 결과를 사람이 직접 확인(`manual_retrieval.py` 상단 변수 수정):

```powershell
.\.venv\Scripts\python.exe scripts\manual_retrieval.py
```

출력에는 각 Chunk의 `chunk_id`, `document_id`, `filename`, `page`, `section`, `score`, `content`가 포함된다.

---

# 14. RAG Test

## 근거 있음

입력:

```text
업로드 문서에서 명시적으로 답할 수 있는 질문
```

검증:

- Retrieval 수행
- Context 구성
- Answer
- Citation

## 근거 없음

입력:

```text
업로드 문서에 없는 정보
```

검증:

- 문서에 없는 정보를 근거인 것처럼 생성하지 않음
- 임의 Citation 생성하지 않음
- 근거 부족 표현

## 여러 출처 / Context 상한

- 다른 문서·Page·Chunk의 Citation이 실제 Context Result와 일치
- 동일 Citation은 최초 검색 순서를 유지하며 한 번만 반환
- LLM 답변 본문의 가짜 Citation 문자열을 Application Citation으로 채택하지 않음
- `MAX_CONTEXT_TOKENS`를 넘지 않으며 Context에 포함되지 않은 Chunk의 Citation을 반환하지 않음

Phase 10 Unit/Deterministic Integration:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_rag.py `
  tests\component\test_rag_pipeline.py `
  tests\unit\test_config.py -q
```

Agent 없는 개발용 RAG 진입점(`manual_rag.py` 상단 변수 수정):

```powershell
.\.venv\Scripts\python.exe scripts\manual_rag.py
```

실제 Embedding Provider → Qdrant → Retrieval → RAG Context → LLM → Citation E2E:

```powershell
$env:RUN_RAG_INTEGRATION_TESTS='1'
.\.venv\Scripts\python.exe -m pytest `
  tests\integration\rag\test_rag_provider_integration.py -q
```

이 테스트는 `QDRANT_*`, Embedding/LLM Provider Credential과 외부 네트워크를 사용하며 API 비용이
발생할 수 있다. 테스트 전용 Collection은 실행 후 삭제한다.

---

# 15. Citation Test

PDF:

```text
document_id
filename
chunk_id
page
```

TXT:

```text
document_id
filename
chunk_id
```

MD:

```text
document_id
filename
chunk_id
section (가능한 경우)
```

Citation은 Retrieval Result와 대조하여 실제 존재 여부를 확인한다.

---

# 16. Summary Test

## Direct

Context에 충분히 들어가는 작은 문서.

검증:

- Direct 전략
- 전체 문서 기반 Summary

## Hierarchical

Context를 초과하는 큰 문서.

검증:

- Chunk별 Summary
- 중간 Summary 결합
- 최종 Summary

전략 판단이 LLM Agent가 아니라 Python 규칙으로 이루어지는지 확인한다.

## 실제 Provider E2E

비민감 합성 Fixture만 사용하여 실제 MinIO, Qdrant, 외부 LLM 경계를 함께 검증한다.

```powershell
$env:RUN_SUMMARY_INTEGRATION_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests\integration\summary\test_summary_provider_integration.py -q
```

검증:

- MinIO 원본 저장/조회
- 사용자 Scope가 포함된 Qdrant 문서 위치 Metadata 조회
- 작은 문서 Direct Summary와 합성 Marker 보존
- 큰 문서 Hierarchical Map/Final Reduce와 처음/마지막 합성 Marker 보존
- 테스트 전용 MinIO Object/Bucket과 Qdrant Collection 정리

---

# 17. Query Rewrite Test

대화:

```text
User: Qdrant가 뭐야?
Assistant: Vector DB입니다.
User: 그럼 장점은?
```

검증:

- 현재 질문 원문 유지
- Retrieval Query만 독립 질문으로 재작성
- Rewrite 결과로 Retrieval 가능
- `그거`, `그럼`, `위 내용` 같은 문맥 의존 표현
- 독립 질문의 과도한 Rewrite 방지
- Conversation Context가 없을 때 LLM 호출 생략
- Rewrite LLM 호출/출력 실패 시 원문 Query fallback

호출 정책:

- Conversation Summary와 Recent Messages가 모두 비어 있으면 LLM을 호출하지 않고 원문을 Retrieval에 사용한다.
- 둘 중 하나라도 있으면 LLM이 Rewrite 필요 여부를 판단한다.
- 결과는 `original_query`, `rewritten_query`, `was_rewritten`, `status`로 분리한다.

Unit 및 RAG 경계 검증:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_query_rewrite.py `
  tests\unit\test_rag.py `
  tests\component\test_rag_pipeline.py -q
```

실제 LLM Provider Prompt E2E:

```powershell
$env:RUN_QUERY_REWRITE_INTEGRATION_TESTS='1'
.\.venv\Scripts\python.exe -m pytest `
  tests\integration\query_rewrite\test_query_rewrite_provider_integration.py -q
```

이 테스트는 외부 LLM Credential과 네트워크를 사용하며 API 비용이 발생할 수 있다.

---

# 18. Context Budget Test

테스트 케이스:

- 2개 Message
- 20개 Message와 Recent Message Sliding Window
- 매우 긴 과거 Message의 bounded summary 호출
- 매우 큰 RAG Context의 Chunk/길이 축소
- 기존 Conversation Summary 존재
- Conversation Summary 없음
- Context Window 근접
- Output Reservation 선반영
- Current Question 자체가 필수 Prompt 예산을 넘는 경우 LLM 호출 전 명시적 실패

검증:

```text
Conversation Summary
+
Recent Messages
+
RAG Context
+
Current Question
+
Reserved Output
<=
허용 Context Budget
```

정확한 Token 계산 방법은 선택한 모델/Tokenizer 구현에 맞춘다.

정책:

- `LLM_CONTEXT_WINDOW - LLM_MAX_OUTPUT_TOKENS`를 실제 입력 상한으로 먼저 확정한다.
- `MAX_RECENT_MESSAGES`를 넘거나 입력 상한에 맞지 않는 가장 오래된 Message부터 제거한다.
- 제거되는 History는 별도 Conversation Summary Prompt로 bounded batch 요약한다.
- Query Rewrite와 최종 Answer에는 압축된 동일 Conversation Context만 전달한다.
- RAG Context는 `MAX_CONTEXT_TOKENS`와 최종 Prompt의 실제 남은 예산 중 작은 값으로 제한한다.
- 최종 `input_tokens`는 완성된 Prompt 전체를 다시 Tokenizer로 측정한다.

Phase 13 Unit 및 RAG 경계 검증:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_context.py `
  tests\unit\test_rag.py `
  tests\unit\test_config.py `
  tests\component\test_rag_pipeline.py -q
```

---

# 19. Tool Test

## `search_documents`

- 올바른 검색
- user_id Scope
- document_id Scope
- 검색 결과 없음
- Qdrant 오류

## `summarize_document`

- 작은 문서
- 큰 문서
- 존재하지 않는 문서
- Parsing/Storage 오류

## `list_documents`

실제 Backend 전:

- Mock/Stub Backend
- 정상 목록
- 빈 목록
- Backend Timeout
- Backend 오류

실제 Backend 후:

- Internal API 계약 통합 테스트

Phase 14 Mock Backend 직접 호출 검증:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_tools.py -q
```

Tool Input Schema에는 LLM이 선택할 `user_id`를 노출하지 않고, 테스트가 주입한
`ToolExecutionContext`의 사용자/문서 Scope가 실제 Service 및 Backend Client 호출을 제한하는지
확인한다. Agent의 Tool 선택은 이 Phase에서 검증하지 않는다.

---

# 20. Agent Test

최소 분기:

| Input | Expected |
| --- | --- |
| 일반 질문 | No Tool |
| 문서 내용 질문 | `search_documents` |
| 특정 문서 요약 | `summarize_document` |
| 등록 문서 조회 | `list_documents` |

추가:

- Tool 1회 실패
- Tool 결과 없음
- `MAX_TOOL_CALLS`
- `MAX_AGENT_STEPS`
- Tool Loop 방지

Agent가 일반 질문에 불필요한 Qdrant Search를 수행하지 않는지 확인한다.

Phase 15 결정적 Agent/Adapter 검증:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_agent.py `
  tests\unit\adapters\test_agent_model.py -q
```

포함 범위:

- 일반 상식 3개와 문서/일반 경계가 애매한 질문 3개의 `tool_call_count = 0`
- `search_documents`, `summarize_document`, `list_documents` 선택과 Tool Result 왕복
- Agent가 만든 `user_id` 거부 및 Context의 실제 사용자/문서 Scope 유지
- 빈 검색 결과의 빈 Citation
- Tool Error 1회 후 최종 Answer 및 반복 시 `MAX_TOOL_CALLS` 차단
- `MAX_AGENT_STEPS` 도달 전 추가 Model 호출 차단
- `AgentExecutionObserver`에 안전한 단계/상태만 전달

실제 LLM 의미 분기 검증은 명시적으로 활성화한다.

```powershell
$env:RUN_AGENT_INTEGRATION_TESTS="1"
.\.venv\Scripts\python.exe -m pytest `
  tests\integration\agent\test_agent_provider_integration.py -q
```

실제 Provider 테스트는 비용/외부 Credential이 필요하므로 기본 전체 회귀에서는 skip한다.

---

# 21. Usage Test

한 요청에서 여러 LLM Call을 발생시킨다.

검증:

```text
LLMCallUsage 개수
==
실제 LLM 호출 횟수
```

합계:

```text
AgentRun.total_input_tokens
AgentRun.total_output_tokens
AgentRun.total_tokens
```

와 개별 Call Usage 합산이 정책에 맞는지 확인한다.

Provider가 반환하지 않는 Optional Usage는 오류가 아니라 `null`/미설정이어야 한다.

---

# 22. WebSocket Test

CLI WebSocket Client는 프로젝트 환경에서 사용할 도구를 하나 정해 문서화한다.

예시 흐름:

```text
Client Connect
↓
message
↓
start
↓
status
↓
tool/retrieval event
↓
delta...
↓
citation
↓
usage
↓
done
```

검증:

- `request_id`
- Event 순서의 논리적 일관성
- Text Delta
- Citation
- Usage
- Done
- Error
- Cancelled

---

# 23. Observable Execution Trace Test

허용:

```text
질문을 분석하고 있습니다.
관련 문서를 검색하고 있습니다.
관련 Chunk 5개를 찾았습니다.
답변을 생성하고 있습니다.
```

금지 정보가 Event/Log에 없는지 확인:

```text
Chain-of-Thought
System Prompt
API Key
Stack Trace
보안 Metadata
```

---

# 24. Timeout / Retry Test

대상:

- LLM
- Embedding
- Qdrant
- MinIO
- Backend Internal API

검증:

- Timeout 발생
- 표준 오류 변환
- 허용된 경우 제한적 Retry
- Validation/Auth 오류는 Retry하지 않음
- 중복 실행 위험 요청은 무조건 재시도하지 않음

---

# 25. WebSocket Stability Test

검증:

- Client Disconnect
- Server Disconnect
- 재연결을 고려한 상태
- Idle Timeout
- Message Size Limit
- 잘못된 Event
- 중복 request_id 처리 정책
- Cancel 요청

Frontend 자동 재연결 시 요청 자동 재실행 문제는 최종 E2E에서 Backend/Frontend와 함께 검증한다.

---

# 26. Logging / Secret Test

로그에 없어야 하는 것:

```text
API Key
Password
Access Token
Refresh Token
전체 민감 문서 내용
민감 Prompt
```

오류 Response/Event에 없어야 하는 것:

```text
Stack Trace
Provider Credential
System Prompt
```

---

# 27. Phase 완료 체크

Phase 완료 전:

```text
[ ] 구현 완료
[ ] Unit Test 통과
[ ] 필요한 Integration Test 통과
[ ] 필요한 CLI/curl 검증 완료
[ ] 오류 케이스 검증
[ ] Secret 로그 없음
[ ] PROGRESS.md 갱신
```

실제 Provider/Infrastructure가 없어 검증하지 못한 항목은 체크하지 않고 미검증 사유를 기록한다.
