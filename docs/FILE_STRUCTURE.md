# AI Server File Structure

이 문서는 Phase 15.5까지 실제 구현된 파일의 책임과 의존 방향을 명시한다. 아직 구현하지 않은 Phase의
디렉터리는 선행해서 만들지 않는다.

```text
service-ai/
├─ app/
│  ├─ api/
│  │  ├─ dependencies.py          # Container의 설정/Application Service 조회
│  │  ├─ error_handlers.py        # Application Error의 FastAPI HTTP 매핑
│  │  ├─ documents.py             # 문서 처리/삭제/상태 Internal REST 계약
│  │  ├─ health.py                # /health, /ready
│  │  ├─ router.py                # API Router 조립
│  │  └─ schemas/
│  │     ├─ documents.py          # Internal Document HTTP DTO
│  │     └─ health.py             # Health/Readiness HTTP DTO
│  │
│  ├─ agent/
│  │  ├─ service.py               # bounded LangChain Tool Calling Loop
│  │  └─ tools/
│  │     ├─ contracts.py          # Tool 계약과 LangChain StructuredTool 변환
│  │     ├─ execution.py          # Context-bound Retrieval/Summary/Backend 호출
│  │     └─ schemas.py            # LLM-visible Tool Input/Output
│  │
│  ├─ composition/
│  │  ├─ container.py             # Service/Resource 생성 소유권과 lifecycle
│  │  ├─ resources.py             # Qdrant/MinIO Resource 조립 및 종료
│  │  └─ factories/
│  │     ├─ agent.py              # Chat Model/Tool 기반 Agent 조립
│  │     ├─ backend.py            # Backend Internal API Client 조립
│  │     ├─ chunking.py           # TokenCounter/Chunker 조립
│  │     ├─ document_management.py
│  │     ├─ embedding.py          # Embedding Provider/Service 조립
│  │     ├─ ingestion.py
│  │     ├─ llm.py                # LLM Provider/Service 조립
│  │     ├─ rag.py
│  │     ├─ retrieval.py
│  │     └─ summary.py
│  │
│  ├─ services/
│  │  ├─ documents/
│  │  │  ├─ ingestion.py          # Ingestion 오케스트레이션과 재처리 정책
│  │  │  ├─ preparation.py        # Storage Read/Parsing/Chunking
│  │  │  ├─ vectorization.py      # 측정/Embedding Batch/Vector Point 조립
│  │  │  ├─ management.py         # Scoped 삭제/상태 Registry/작업 Lock
│  │  │  └─ collection.py         # Qdrant Collection/Dimension 정책
│  │  ├─ retrieval/
│  │  │  ├─ service.py            # Query Embedding과 scoped Dense Retrieval
│  │  │  └─ query_rewrite.py      # 대화 기반 Retrieval Query 재작성
│  │  ├─ rag/
│  │  │  ├─ service.py            # Retrieval → Context → LLM → Citation
│  │  │  ├─ context_builder.py    # Metadata/Text 분리와 Token 상한
│  │  │  └─ citations.py          # Citation 생성/중복 제거
│  │  ├─ summary/
│  │  │  ├─ service.py            # Scoped 원문 로딩과 요약 진입점
│  │  │  └─ execution.py          # Direct/Hierarchical 실행과 Budget 정책
│  │  ├─ context/
│  │  │  ├─ budget.py             # RAG/Conversation Token Budget 조립
│  │  │  └─ compaction.py         # 대화 압축과 최근 Message 보존
│  │  ├─ embedding.py             # 단일/Batch Embedding 검증
│  │  └─ llm.py                   # Provider 중립 LLM Application Service
│  │
│  ├─ adapters/
│  │  ├─ agent/langchain_models.py # LangChain OpenAI/Ollama/Gemini Chat Model
│  │  ├─ backend/http.py           # Backend 문서 목록 HTTP Client
│  │  ├─ embedding/
│  │  │  ├─ huggingface.py
│  │  │  └─ openai_compatible.py  # OpenAI/DeepInfra 호환 Embedding
│  │  ├─ llm/
│  │  │  ├─ openai.py
│  │  │  ├─ ollama.py
│  │  │  └─ gemini.py
│  │  ├─ storage/minio.py
│  │  └─ vector/qdrant.py
│  │
│  ├─ models/
│  │  ├─ agent.py
│  │  ├─ context.py
│  │  ├─ document.py
│  │  ├─ embedding.py
│  │  ├─ ingestion.py
│  │  ├─ llm.py
│  │  ├─ query_rewrite.py
│  │  ├─ rag.py
│  │  ├─ retrieval.py
│  │  ├─ summary.py
│  │  └─ tools.py
│  │
│  ├─ ports/
│  │  ├─ agent.py                 # 안전한 Agent 실행 상태 Observer
│  │  ├─ backend.py               # Backend Source-of-Truth 문서 목록
│  │  ├─ documents.py             # 문서 처리/관리 Application Protocol
│  │  ├─ embedding.py
│  │  ├─ llm.py
│  │  ├─ qdrant.py                # Runtime/Admin Qdrant Protocol/DTO
│  │  └─ storage.py               # Runtime/Admin Object Storage Protocol/DTO
│  │
│  ├─ parsers/                    # PDF/TXT/MD Parser와 Registry
│  ├─ chunking/                   # TokenCounter와 Recursive Chunking
│  ├─ prompts/                    # Agent/RAG/Summary/Rewrite/Context Prompt
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ exceptions.py           # Transport Framework 독립 Application 오류
│  │  ├─ logging.py
│  │  └─ request_context.py
│  └─ main.py                     # FastAPI Factory와 lifespan 연결
│
├─ scripts/                       # 비용/Infrastructure 수동 검증 진입점
├─ tests/
│  ├─ fixtures/documents/
│  ├─ unit/
│  │  ├─ adapters/
│  │  ├─ chunking/
│  │  ├─ parsers/
│  │  └─ test_package_boundaries.py # 계층/Transport 독립성 회귀
│  ├─ component/
│  ├─ contract/
│  ├─ integration/
│  └─ smoke/
├─ docs/
├─ compose.yaml
├─ .env.example
└─ pyproject.toml
```

## Dependency Direction

```text
FastAPI API
    ↓
Document Application Port / Agent
    ↓
Application Service → Provider-neutral Model
    ↓
QdrantRepository / ObjectStorage / LLMProvider / EmbeddingProvider
    ↓
Concrete Adapter
    ↓
External SDK / Qdrant / MinIO / Provider API
```

```text
LangChain Chat Model + Agent Prompt
    ↓ AIMessage.tool_calls
Agent Tool
    ↓
ToolExecutionContext + Retrieval/Summary Service 또는 BackendDocumentsClient
    ↓ ToolMessage
LangChain Chat Model → Final Answer
```

## Structure Rules

- `main.py`는 FastAPI/lifespan만 연결하고 생성·소유권·종료는 `composition/`이 담당한다.
- `composition/`만 Concrete Adapter와 Service 구현을 함께 알 수 있다.
- Factory는 전체 Infrastructure 묶음이 아니라 실제 필요한 Port를 입력으로 받는다.
- API는 `dependencies.py`를 통해 Container의 Service를 조회한다.
- 내부 Application/Test/Script import는 심볼을 정의한 구체 모듈 경로를 사용한다.
- `__init__.py`는 기본적으로 패키지 설명만 유지한다. 외부에서 사용하는 안정적인 Python API가 명시된
  경우에만 re-export를 허용하며, 현재는 해당 공개 API가 없다.
- `core/exceptions.py`는 FastAPI/Starlette에 의존하지 않고 HTTP 매핑은 `api/error_handlers.py`가 담당한다.
- Agent는 Retrieval/Summary보다 상위 오케스트레이션이며 `agent → services → ports → adapters` 방향을 유지한다.
- Service는 `agent`, `api`, `composition`, Concrete Adapter에 의존하지 않는다.
- Tool은 기능을 중복 구현하지 않고 기존 Service 또는 Backend Port를 호출한다.
- Provider 중립 Request/Result/Usage는 `models/`에 두고 `ports/`는 Protocol에 집중한다.
- 외부에서 주입된 Resource/Service는 호출자 소유이며 Container가 닫지 않는다.

## Data and Security Rules

- MinIO는 원본 문서 Object만 저장한다.
- Qdrant는 Chunk/Vector/Retrieval Metadata만 저장하며 원본 파일 저장소로 사용하지 않는다.
- Qdrant Retrieval은 문서 범위 유무와 무관하게 `user_id` Filter를 항상 사용한다.
- 문서 교체·삭제·상태 조회는 `user_id + document_id` Filter를 모두 사용한다.
- Tool Input Schema는 `user_id`를 노출하지 않고 `ToolExecutionContext`에서 Scope를 주입한다.
- `list_documents`는 Qdrant가 아니라 Backend Internal API를 Source of Truth로 사용한다.
- Prompt, Chain-of-Thought, Tool 원문, Stack Trace, Secret을 Agent 관찰 상태에 포함하지 않는다.
- LLM/Embedding Service와 상위 계층은 Provider SDK 타입을 받거나 반환하지 않는다.
- Provider Credential은 환경 설정으로만 주입하며 저장소나 로그에 기록하지 않는다.

## Document and RAG Rules

- Parser 선택은 `ParserRegistry`가 담당하고 이후 단계에는 `NormalizedDocument`를 전달한다.
- Chunk와 Overlap은 PDF Page/Markdown Section Citation 경계를 넘지 않는다.
- 빈 문서는 빈 Chunk를 만들지 않으며 Ingestion에서는 `DOCUMENT_EMPTY`로 실패시킨다.
- 모든 Embedding Batch가 완료되기 전에는 Qdrant를 변경하지 않는다.
- 같은 문서의 Ingestion 교체와 삭제는 동일한 작업 Lock을 사용한다.
- 기존 Qdrant Collection의 Dimension이 다르면 자동 삭제/재생성하지 않는다.
- RAG Context는 Token 상한 내에서 Metadata와 본문을 분리해 구성한다.
- Citation은 실제 Retrieval Result에서만 생성하고 검색 순서를 유지해 중복 제거한다.
- 근거가 없으면 LLM을 호출하지 않고 근거 부족 응답과 빈 Citation을 반환한다.
- `MAX_AGENT_STEPS`와 `MAX_TOOL_CALLS`는 Model/Tool 호출 전에 강제한다.
