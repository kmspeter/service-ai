# AI Server File Structure

이 문서는 현재 구현된 파일의 책임과 의존 방향을 명시한다. 아직 구현하지 않은 Phase의 디렉터리는 선행해서 만들지 않는다.

```text
service-ai/
├─ app/
│  ├─ api/
│  │  ├─ documents.py           # 문서 처리/삭제/상태 Internal REST 계약과 HTTP 매핑
│  │  ├─ health.py              # /health, /ready
│  │  └─ router.py              # API router 조립
│  ├─ adapters/
│  │  ├─ qdrant.py              # Qdrant SDK Adapter 및 오류 변환
│  │  ├─ minio.py               # MinIO SDK Adapter 및 오류 변환
│  │  ├─ huggingface_embedding.py # Hugging Face Feature Extraction Adapter
│  │  ├─ openai.py              # OpenAI Responses API Adapter 및 Usage/오류 변환
│  │  ├─ openai_embedding.py    # OpenAI-compatible Embeddings Adapter 및 Vector/Usage 검증
│  │  ├─ ollama.py              # Ollama Cloud API Adapter 및 Usage/오류 변환
│  │  └─ gemini.py              # Google Gemini Interactions API Adapter
│  ├─ core/
│  │  ├─ config.py              # 환경설정과 Phase별 필수값 검증
│  │  ├─ exceptions.py          # 외부 노출용 표준 오류 계약
│  │  ├─ logging.py             # JSON logging
│  │  └─ request_context.py      # request_id middleware/context
│  ├─ ports/
│  │  ├─ qdrant.py              # QdrantRepository Protocol/DTO
│  │  ├─ storage.py              # ObjectStorage Protocol/DTO
│  │  ├─ llm.py                  # LLMProvider Protocol과 공통 Request/Result/Usage
│  │  └─ embedding.py            # EmbeddingProvider Protocol과 공통 Result/Usage
│  ├─ models/
│  │  ├─ document.py             # Parser/Chunk/DocumentStatistics 내부 모델
│  │  ├─ context.py              # Conversation/RAG Context 예산 결과 내부 모델
│  │  ├─ ingestion.py            # 처리 Context/Result/표준 실패 사유 내부 모델
│  │  ├─ query_rewrite.py         # 대화 기반 검색 질의 재작성 내부 모델
│  │  ├─ retrieval.py            # Retrieval Request와 Citation-ready Result 내부 모델
│  │  ├─ rag.py                   # Pure RAG Request/Response와 Citation 내부 모델
│  │  └─ summary.py               # 문서 요약 요청/결과/전략 내부 모델
│  ├─ prompts/
│  │  ├─ conversation_summary.py # 대화 압축 Prompt
│  │  ├─ query_rewrite.py        # 검색 질의 재작성 Prompt
│  │  ├─ rag.py                  # 전용 RAG Answer Prompt와 근거 부족 응답
│  │  └─ summary.py              # 직접/계층형 문서 요약 Prompt
│  ├─ parsers/
│  │  ├─ base.py                 # 문서 Parser Protocol
│  │  ├─ encoding.py             # TXT/MD 공통 Unicode Encoding 정책
│  │  ├─ text.py                 # TXT 원문 Parser
│  │  ├─ markdown.py             # MD 원문 및 Heading Section Parser
│  │  ├─ pdf.py                  # PyMuPDF Page Text Parser
│  │  └─ registry.py             # 확장자별 Parser 선택의 단일 진입점
│  ├─ services/
│  │  ├─ chunking.py             # Token 측정과 위치 경계 보존 Recursive Chunking
│  │  ├─ context.py              # RAG Context 예산 조립
│  │  ├─ conversation_compaction.py # 대화 압축과 최근 메시지 보존 정책
│  │  ├─ document_management.py  # Scoped Vector 삭제, 상태 Registry/조회, 문서 작업 Lock
│  │  ├─ ingestion.py            # 문서 Ingestion 오케스트레이션과 재처리 정책
│  │  ├─ ingestion_preparation.py # 저장소 읽기/Parsing/Chunking 준비 단계
│  │  ├─ ingestion_support.py     # Ingestion 측정/임베딩 Batch/Vector Point 조립
│  │  ├─ query_rewrite.py         # 대화 기반 Retrieval Query 재작성
│  │  ├─ retrieval.py            # Query Embedding과 scoped Dense Vector Retrieval
│  │  ├─ rag_context.py          # Metadata/Text 분리 및 token 상한 Context Builder
│  │  ├─ rag.py                  # Retrieval → Context → LLM → Citation 오케스트레이션
│  │  ├─ summary.py              # scoped 원문 로딩과 문서 요약 진입점
│  │  ├─ summary_execution.py    # 직접/계층형 요약 실행과 Token Budget 정책
│  │  ├─ llm.py                  # Provider 중립 LLM Application Service
│  │  └─ embedding.py            # 단일/Batch Embedding과 Qdrant Dimension 정책
│  ├─ factories/
│  │  ├─ chunking.py             # 설정 기반 TokenCounter/Chunker 조립
│  │  ├─ document_management.py  # Document Management Service 조립
│  │  ├─ embedding.py            # Embedding Provider/Service 조립
│  │  ├─ ingestion.py            # Ingestion Service 조립
│  │  ├─ llm.py                  # LLM Provider/Service 조립
│  │  ├─ rag.py                  # Pure RAG Service 조립
│  │  ├─ retrieval.py            # Retrieval Service 조립
│  │  └─ summary.py              # Document Summary Service 조립
│  ├─ schemas/
│  │  ├─ documents.py           # Internal Document 처리/삭제/상태 DTO
│  │  └─ health.py              # Health/Readiness response schema
│  ├─ infrastructure.py         # Adapter 조립 및 lifecycle container
│  └─ main.py                   # FastAPI application factory
├─ scripts/
│  ├─ inspect_chunking.py        # Parser → Chunking 개발 확인 CLI
│  ├─ inspect_retrieval.py       # 사용자/문서 범위 Retrieval 결과 확인 CLI
│  ├─ inspect_rag.py             # Agent 없는 Pure RAG 전체 흐름 확인 CLI
│  └─ test_llm.py               # Agent/RAG와 무관한 실제 LLM 호출 CLI
├─ tests/
│  ├─ fixtures/documents/        # 비민감 TXT/MD/PDF Parser Fixture
│  ├─ unit/parsers/              # Parser/Registry/Normalized Document Unit Test
│  ├─ unit/chunking/             # Token/Recursive Chunking/Metadata Unit Test
│  ├─ unit/adapters/            # SDK 오류 변환 Unit Test
│  ├─ integration/qdrant/       # 실제 Qdrant 및 Embedding Dimension Integration Test
│  ├─ integration/embedding/    # 실제 Embedding Provider Integration Test
│  ├─ integration/ingestion/    # 실제 MinIO/Qdrant/Embedding Pipeline Test
│  ├─ integration/retrieval/    # 실제 Qdrant 및 선택형 Embedding Retrieval Test
│  ├─ integration/minio/        # 실제 MinIO Integration Test
│  ├─ integration/              # FastAPI endpoint/error Integration Test
│  ├─ unit/                     # application/config/logging Unit Test
│  ├─ conftest.py               # 공통 설정과 Adapter fake 주입
│  └─ fakes.py                  # SDK에 의존하지 않는 test doubles
├─ docs/                        # 범위/설계/계약/테스트/진행 문서
├─ compose.yaml                 # 로컬 Qdrant/MinIO와 persistent volumes
├─ .env.example                 # Secret을 제외한 환경설정 예시
└─ pyproject.toml               # Python dependency/test/lint configuration
```

## Dependency Direction

```text
Document File / ParserInput
    ↓
ParserRegistry / DocumentParser
    ↓
NormalizedDocument / ContentUnit

FastAPI API
    ↓
QdrantRepository / ObjectStorage / LLMProvider / EmbeddingProvider (Port)
    ↓
QdrantAdapter / MinIOStorageAdapter / LLM Adapters / Embedding Adapters
    ↓
External SDK / Qdrant / MinIO
```

- API와 향후 Application Service/Tool은 외부 SDK를 직접 호출하지 않는다.
- MinIO는 원본 문서 Object만 저장한다.
- Qdrant는 Chunk/Vector/Retrieval Metadata만 저장하며 원본 파일 저장소로 사용하지 않는다.
- 기본 Embedding은 DeepInfra `Qwen/Qwen3-Embedding-8B`이고 Qdrant Vector Dimension은 4096다.
- Provider Credential은 선택한 Provider 전용 환경값으로만 주입하며 저장소나 로그에 기록하지 않는다.
- 기존 Qdrant Collection의 dimension이 다르면 자동 삭제/재생성하지 않고 명시적인 오류를 반환한다.
- LLM Service와 상위 Application 계층은 OpenAI SDK 타입을 받거나 반환하지 않는다.
- Embedding Service와 상위 Application 계층은 OpenAI SDK 타입을 받거나 반환하지 않는다.
- Parser 선택은 `ParserRegistry`에만 두고 이후 단계에는 `NormalizedDocument`를 전달한다.
- `CHUNK_SIZE`와 `CHUNK_OVERLAP`은 tokenizer token 단위이며 문자 수가 아니다.
- PDF Page와 Markdown Section은 Citation 경계다. Chunk 및 Overlap은 이 경계를 넘지 않는다.
- 빈 문서는 Token/Chunk 수를 0으로 유지하며 빈 Chunk를 만들지 않는다.
- Ingestion에서는 파싱 결과가 비어 있으면 `DOCUMENT_EMPTY`로 실패시키고 Vector를 만들지 않는다.
- 모든 Embedding Batch 완료 전에는 Qdrant를 변경하지 않는다.
- 같은 `document_id` 재처리는 기존 Point를 교체하며 저장 실패 시 잔여 신규 Point 정리를 시도한다.
- Qdrant Point ID는 `user_id + document_id + chunk_index`를 길이 구분한 UUID5로 생성해 사용자 간 ID 충돌을 방지한다.
- Ingestion 교체와 삭제는 같은 `user_id + document_id` 작업 Lock을 공유한다.
- Qdrant 문서 교체·삭제·상태 조회는 `user_id + document_id` Filter를 모두 사용한다.
- Qdrant Retrieval은 문서 범위 유무와 무관하게 `user_id` Filter를 항상 사용한다.
- 문서 범위가 있으면 단일 `document_id` 또는 복수 `document_ids` Filter를 추가한다.
- Retrieval Result는 Phase 10 Citation에 필요한 Chunk 본문과 위치 Metadata를 보존한다.
- RAG Prompt는 `app/prompts/rag.py`에서 단일 관리하며 Service에 Prompt 문자열을 분산하지 않는다.
- RAG Context는 `MAX_CONTEXT_TOKENS` 상한 내에서 Metadata와 본문을 분리해 구성한다.
- Citation은 Context에 포함된 실제 Retrieval Result에서만 생성하고 완전 중복은 검색 순서를 유지해 제거한다.
- 근거가 없으면 LLM을 호출하지 않고 근거 부족 응답과 빈 Citation을 반환한다.
- 처리 중/최근 실패 상태는 process-local Registry에만 두고 완료 상태는 Qdrant payload에서 복원한다.
- 문서 삭제는 Qdrant Vector만 대상으로 하며 Backend Metadata와 MinIO 원본을 변경하지 않는다.
