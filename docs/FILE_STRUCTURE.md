# AI Server File Structure

이 문서는 현재 구현된 파일의 책임과 의존 방향을 명시한다. 아직 구현하지 않은 Phase의 디렉터리는 선행해서 만들지 않는다.

```text
service-ai/
├─ app/
│  ├─ api/
│  │  ├─ health.py              # /health, /ready
│  │  └─ router.py              # API router 조립
│  ├─ adapters/
│  │  ├─ qdrant.py              # Qdrant SDK Adapter 및 오류 변환
│  │  ├─ minio.py               # MinIO SDK Adapter 및 오류 변환
│  │  ├─ openai.py              # OpenAI Responses API Adapter 및 Usage/오류 변환
│  │  ├─ openai_embedding.py    # OpenAI Embeddings API Adapter 및 Vector/Usage 검증
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
│  │  └─ document.py             # Parser/Chunk/DocumentStatistics 내부 모델
│  ├─ parsers/
│  │  ├─ base.py                 # 문서 Parser Protocol
│  │  ├─ encoding.py             # TXT/MD 공통 Unicode Encoding 정책
│  │  ├─ text.py                 # TXT 원문 Parser
│  │  ├─ markdown.py             # MD 원문 및 Heading Section Parser
│  │  ├─ pdf.py                  # PyMuPDF Page Text Parser
│  │  └─ registry.py             # 확장자별 Parser 선택의 단일 진입점
│  ├─ services/
│  │  ├─ chunking.py             # Token 측정과 위치 경계 보존 Recursive Chunking
│  │  ├─ llm.py                  # Provider 중립 LLM Application Service
│  │  └─ embedding.py            # 단일/Batch Embedding과 Qdrant Dimension 정책
│  ├─ schemas/
│  │  └─ health.py              # Health/Readiness response schema
│  ├─ infrastructure.py         # Adapter 조립 및 lifecycle container
│  ├─ chunking.py               # 설정 기반 TokenCounter/Chunker 조립
│  ├─ llm.py                    # 설정 기반 LLM Provider 조립
│  ├─ embedding.py              # 설정 기반 Embedding Provider 조립
│  └─ main.py                   # FastAPI application factory
├─ scripts/
│  ├─ inspect_chunking.py        # Parser → Chunking 개발 확인 CLI
│  └─ test_llm.py               # Agent/RAG와 무관한 실제 LLM 호출 CLI
├─ tests/
│  ├─ fixtures/documents/        # 비민감 TXT/MD/PDF Parser Fixture
│  ├─ unit/parsers/              # Parser/Registry/Normalized Document Unit Test
│  ├─ unit/chunking/             # Token/Recursive Chunking/Metadata Unit Test
│  ├─ unit/adapters/            # SDK 오류 변환 Unit Test
│  ├─ integration/qdrant/       # 실제 Qdrant 및 Embedding Dimension Integration Test
│  ├─ integration/embedding/    # 실제 Embedding Provider Integration Test
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
QdrantAdapter / MinioStorageAdapter / LLM Adapters / OpenAIEmbeddingAdapter
    ↓
External SDK / Qdrant / MinIO
```

- API와 향후 Application Service/Tool은 외부 SDK를 직접 호출하지 않는다.
- MinIO는 원본 문서 Object만 저장한다.
- Qdrant는 Chunk/Vector/Retrieval Metadata만 저장하며 원본 파일 저장소로 사용하지 않는다.
- 기본 Embedding 모델 `text-embedding-3-small`과 Production Qdrant Collection의 vector dimension은 1536으로 일치시킨다.
- 기존 Qdrant Collection의 dimension이 다르면 자동 삭제/재생성하지 않고 명시적인 오류를 반환한다.
- LLM Service와 상위 Application 계층은 OpenAI SDK 타입을 받거나 반환하지 않는다.
- Embedding Service와 상위 Application 계층은 OpenAI SDK 타입을 받거나 반환하지 않는다.
- Parser 선택은 `ParserRegistry`에만 두고 이후 단계에는 `NormalizedDocument`를 전달한다.
- Phase 05는 OCR, Chunking, Embedding, Qdrant Point 저장, Retrieval과 연결하지 않는다.
- `CHUNK_SIZE`와 `CHUNK_OVERLAP`은 tokenizer token 단위이며 문자 수가 아니다.
- PDF Page와 Markdown Section은 Citation 경계다. Chunk 및 Overlap은 이 경계를 넘지 않는다.
- 빈 문서는 Token/Chunk 수를 0으로 유지하며 빈 Chunk를 만들지 않는다.
