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
│  │  └─ llm.py                  # LLMProvider Protocol과 공통 Request/Result/Usage
│  ├─ services/
│  │  └─ llm.py                  # Provider 중립 LLM Application Service
│  ├─ schemas/
│  │  └─ health.py              # Health/Readiness response schema
│  ├─ infrastructure.py         # Adapter 조립 및 lifecycle container
│  ├─ llm.py                    # 설정 기반 LLM Provider 조립
│  └─ main.py                   # FastAPI application factory
├─ scripts/
│  └─ test_llm.py               # Agent/RAG와 무관한 실제 LLM 호출 CLI
├─ tests/
│  ├─ unit/adapters/            # SDK 오류 변환 Unit Test
│  ├─ integration/qdrant/       # 실제 Qdrant Integration Test
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
FastAPI API
    ↓
QdrantRepository / ObjectStorage / LLMProvider (Port)
    ↓
QdrantAdapter / MinioStorageAdapter / OpenAILLMAdapter / OllamaLLMAdapter / GeminiLLMAdapter
    ↓
External SDK / Qdrant / MinIO
```

- API와 향후 Application Service/Tool은 외부 SDK를 직접 호출하지 않는다.
- MinIO는 원본 문서 Object만 저장한다.
- Qdrant는 Chunk/Vector/Retrieval Metadata만 저장하며 원본 파일 저장소로 사용하지 않는다.
- Production Qdrant Collection의 vector dimension은 Phase 04 전에는 확정하지 않는다.
- LLM Service와 상위 Application 계층은 OpenAI SDK 타입을 받거나 반환하지 않는다.
- Phase 03은 Agent, Tool Calling, RAG, Prompt 조립과 연결하지 않는다.
