# AI Server Architecture

## 1. 목적

이 문서는 `IMPLEMENTATION_SCOPE.md`의 책임 경계를 코드 구조로 유지하기 위한 AI Server 내부 아키텍처 원칙을 정의한다.

정확한 디렉터리명은 구현 과정에서 조정할 수 있으나, **의존 방향과 책임 분리**는 유지한다.

---

## 2. 외부 시스템 경계

```text
Backend
  │
  │ Internal REST / WebSocket
  ▼
FastAPI AI Server
  │
  ├─ MinIO
  ├─ Qdrant
  ├─ LLM Provider
  ├─ Embedding Provider
  └─ Backend Internal API(list_documents)
```

AI Server는 일반 사용자가 직접 호출하는 공개 서비스 계층이 아니다.

---

## 3. 책임 분리

### API Layer

담당:

- Internal REST Endpoint
- Internal WebSocket Endpoint
- Request/Response DTO 변환
- 입력 기본 Validation
- request_id 전달
- Application Service 호출
- 표준 Error Mapping

담당하지 않음:

- Parser 구현
- Qdrant Query 직접 작성
- LLM Prompt 조립
- Agent 판단 로직 구현

---

### Application / Service Layer

담당:

- 문서 처리 Orchestration
- Retrieval
- RAG
- Summary
- Query Rewrite
- Context Budget
- Agent 실행
- Usage 집계
- Event 생성

외부 SDK 구현 세부사항에 직접 종속되지 않도록 한다.

---

### Domain / Model Layer

담당:

- Normalized Document
- Chunk
- Citation
- Retrieval Result
- Usage
- Chat/Event
- Token Budget 관련 데이터 구조

가능하면 FastAPI/Pydantic 전용 표현과 핵심 내부 모델을 불필요하게 결합하지 않는다.

---

### Provider / Repository Adapter Layer

외부 시스템별 구현 세부사항을 담당한다.

```text
LLM Provider
Embedding Provider
Qdrant
MinIO
Backend Internal API
```

---

### Tool Layer

Agent가 호출할 실행 경계를 제공한다.

```text
search_documents
summarize_document
list_documents
```

Tool이 핵심 기능을 중복 구현하지 않는다.

```text
Tool
 ↓
Application Service
```

---

### Prompt Layer

다음 Prompt를 코드 전체에 분산시키지 않는다.

```text
Agent Prompt
RAG Answer Prompt
Summary Prompt
Query Rewrite Prompt
Conversation Summary Prompt
```

Prompt 변경이 Service 코드 변경과 가능한 한 독립적이어야 한다.

---

## 4. 현재 코드 구조와 확장 경계

Phase 15까지의 실제 구조다. Phase 16 이후 디렉터리는 해당 Phase에서 추가한다.

```text
app/
├─ main.py
├─ composition.py
├─ infrastructure.py
│
├─ api/
│  ├─ health.py
│  ├─ documents.py
│  └─ router.py
│
├─ core/
│  ├─ config.py
│  ├─ logging.py
│  ├─ exceptions.py
│  └─ request_context.py
│
├─ schemas/
│  ├─ documents.py
│  └─ health.py
│
├─ models/
│  ├─ document.py
│  ├─ ingestion.py
│  ├─ embedding.py
│  ├─ llm.py
│  ├─ retrieval.py
│  ├─ rag.py
│  ├─ summary.py
│  ├─ query_rewrite.py
│  ├─ context.py
│  ├─ tools.py
│  └─ agent.py
│
├─ services/
│  ├─ ingestion.py
│  ├─ ingestion_preparation.py
│  ├─ ingestion_components.py
│  ├─ document_management.py
│  ├─ vector_collection.py
│  ├─ retrieval.py
│  ├─ rag.py
│  ├─ summary.py
│  ├─ query_rewrite.py
│  ├─ conversation_compaction.py
│  ├─ context.py
│  ├─ citations.py
│  └─ agent.py
│
├─ parsers/
│  ├─ base.py
│  ├─ registry.py
│  ├─ pdf.py
│  ├─ text.py
│  └─ markdown.py
│
├─ chunking/
│  └─ recursive.py
│
├─ tools/
│  ├─ contracts.py              # 명시적 계약과 LangChain StructuredTool 변환
│  ├─ execution.py              # 검증 Context에 바인딩된 세 실행 함수
│  └─ schemas.py                # LLM-visible Input과 구조화 Output
│
├─ prompts/
│  └─ agent.py                  # No Tool/세 Tool 선택과 응답 근거 규칙
│
├─ ports/                        # Protocol 중심의 외부/Application 경계
│  └─ agent.py                  # 향후 실시간 실행 상태 Observer 경계
├─ adapters/
│  └─ agent_model.py            # LangChain OpenAI/Ollama/Gemini Tool Calling Model
└─ factories/
   └─ agent.py                  # 설정/Context-bound Tool/Model Agent 조립
```

`ApplicationContainer`는 현재 Service와 Infrastructure Resource를 조립하고, 자신이 생성한 객체만
lifespan 종료 시 닫는다. 테스트나 수동 실행에서 주입한 객체는 호출자가 소유한다. Phase 14 Tool은
기존 Service/Backend Client를 주입받고, Phase 15 Agent는 요청별 `ToolExecutionContext`에 바인딩된
Tool Registry와 설정된 LangChain Chat Model을 Factory에서 조립한다. Phase 18 WebSocket Service도
같은 조립 경계에 추가하고 `main.py`나 API 모듈에서 직접 Provider를 생성하지 않는다.

---

## 5. 의존 방향

권장:

```text
API
 ↓
Service
 ↓
Interface / Port
 ↓
Adapter
```

허용 예:

```text
WebSocket Endpoint
 → AgentService
 → RetrievalService
 → VectorRepository Interface
 → Qdrant Adapter
```

피해야 할 예:

```text
WebSocket Endpoint
 → QdrantClient 직접 호출

Tool
 → MinIO SDK 직접 호출

RAG Service
 → OpenAI SDK 타입 직접 의존
```

---

# 6. 문서 Pipeline

```text
storage_key
    ↓
MinIO Adapter
    ↓
Original File
    ↓
Parser Registry
    ↓
Normalized Document
    ↓
Document Statistics
    ↓
Recursive Chunker
    ↓
Chunks
    ↓
Embedding Service
    ↓
Vectors
    ↓
Qdrant Adapter
```

## Normalized Document의 목적

파일 포맷별 차이를 이후 단계에서 최소화한다.

예상 정보:

```text
document_id
filename
file_type
page_count
content units
metadata
```

PDF는 Page 정보, MD는 가능한 경우 Section 정보를 유지한다.

---

# 7. Retrieval Architecture

```text
Current Question
      ↓
Query Rewrite (필요 시)
      ↓
Embedding
      ↓
Qdrant Search
      ↓
Metadata Filter
      ↓
Top-K / Score Threshold
      ↓
Retrieval Results
```

Filter 최소 조건:

```text
user_id
document_id/document_ids
```

Retrieval Result는 Answer 생성뿐 아니라 Citation 생성의 근거가 된다.

---

# 8. RAG Architecture

```text
Retrieval Result
      ↓
Context Builder
      ↓
Token Budget Check
      ↓
RAG Prompt
      ↓
LLM
      ↓
Answer
      +
Citation
```

문서 근거가 충분하지 않을 경우 근거 부족을 명시하는 방향으로 Prompt를 분리한다.

Phase 10에서는 Phase 13의 전체 Context Budget Manager를 선행 구현하지 않는다. 대신
`MAX_CONTEXT_TOKENS`로 RAG Context 자체에 명시적 상한을 두고, 검색 순서대로 완전한 Chunk를 우선
포함한다. 첫 번째 Chunk 하나도 상한에 들어가지 않으면 해당 Chunk 본문만 상한까지 축약한다.

Context는 JSON의 `metadata`와 `content`를 별도 필드로 구성하며 Prompt는 `content`만 사실 근거로
사용하도록 지시한다. Citation은 LLM 출력에서 파싱하지 않고 Context에 실제 포함된 Retrieval Result를
Application Service가 변환한다. 검색 결과가 없으면 LLM을 호출하지 않는다.

---

# 9. Summary Architecture

## Direct

```text
Document
 ↓
Token Check
 ↓
Summary Prompt
 ↓
LLM
```

## Hierarchical

```text
Chunks
 ↓
Map Summary
 ↓
Intermediate Summaries
 ↓
Reduce/Final Summary
```

Direct/Hierarchical 전략 선택은 Python Service 규칙이다.

---

# 10. Multi-turn Context Architecture

```text
Backend Conversation Context
        │
        ├─ summary
        └─ recent_messages
                ↓
Current Message
        ↓
Context Manager
        │
        ├─ Query Rewrite
        ├─ Token Measurement
        ├─ Sliding Window
        ├─ RAG Context Budget
        └─ Output Reservation
                ↓
LLM Input Context
```

AI Server는 Backend가 제공한 원본 Context를 LLM 입력에 적합하게 구성한다.

원본 대화 데이터의 Source of Truth는 Backend다.

---

# 11. Agent Architecture

```text
Current Message
      ↓
Agent Prompt + LangChain Chat Model.bind_tools
      │
      ├─ No Tool
      │    ↓
      │   LLM Final Answer
      │
      ├─ search_documents
      │    ↓
      │   Retrieval/RAG Service
      │
      ├─ summarize_document
      │    ↓
      │   Summary Service
      │
      └─ list_documents
           ↓
          Backend Client
```

LLM이 반환한 `AIMessage.tool_calls`만 애플리케이션이 실행하고, Tool 결과는 `ToolMessage`로 다음
LLM Step에 전달한다. 질문 문자열에 대한 별도 Python Keyword Router는 두지 않는다.

Scope는 Prompt 지시가 아니라 요청별 `ToolExecutionContext`에서 강제한다. Agent가 `user_id`를
Tool argument에 포함하면 Input Schema에서 거부하며, 정상 Tool 실행도 Context의 `user_id`와 허용
문서 Scope만 기존 Service/Backend Client에 전달한다. Backend가 단일 문서를 선택한 경우 검증된
`document_id`는 파일명 요약을 직접 `summarize_document`로 연결하기 위한 Prompt 힌트로도 전달하지만,
권한 판정은 여전히 Tool 실행 Context가 담당한다.

`search_documents` 결과 Citation은 LLM이 만들지 않는다. 실제 Tool Output의 Retrieval metadata를
공통 Citation Builder가 변환하고 완전 중복을 최초 검색 순서 기준으로 제거한다.

반복 제한:

```text
MAX_AGENT_STEPS
MAX_TOOL_CALLS
```

각 Model 호출 전에 `MAX_AGENT_STEPS`, 각 Tool 실행 전에 `MAX_TOOL_CALLS`를 확인해 상한을 넘는
호출 자체를 실행하지 않는다. `AgentExecutionObserver`는 `agent/model/tool/limit` 단계와
시작/완료/실패 상태만 전달하며 Prompt, Chain-of-Thought, Tool 원문, Stack Trace는 전달하지 않는다.

---

# 12. Usage Architecture

각 LLM 호출:

```text
LLM Call
 ↓
LLMCallUsage
```

Agent Run:

```text
LLMCallUsage[]
+
retrieved_chunk_count
+
total latency
+
run status
 ↓
AgentRunUsage
```

Provider별 특수 Usage 필드는 공통 필드로 변환하고 없는 값은 Optional로 처리한다.

---

# 13. Event / Streaming Architecture

```text
Agent / RAG / Tool / Retrieval
          ↓
Observable Event
          ↓
WebSocket
          ↓
Backend
          ↓
Frontend
```

Event는 내부 사고 과정을 설명하는 것이 아니라 **실제 실행 상태**를 나타낸다.

예:

```text
질문을 분석하고 있습니다.
관련 문서를 검색하고 있습니다.
관련 Chunk 5개를 찾았습니다.
답변을 생성하고 있습니다.
```

노출 금지:

```text
Chain-of-Thought
System Prompt
API Key
Stack Trace
보안 내부 Metadata
```

---

# 14. Health / Readiness

## `/health`

Process Liveness 중심.

예:

```text
FastAPI Process
```

## `/ready`

실제 요청 처리 준비 상태 중심.

확인 후보:

```text
필수 설정
Qdrant
MinIO
현재 노출된 문서 처리 Service 조립
문서 처리에 필요한 Embedding 설정
```

기본값 `READINESS_REQUIRE_DOCUMENT_PROCESSING=true`에서는 문서 처리 Service 또는 필수 설정이 빠지면
Qdrant/MinIO가 정상이어도 503을 반환한다. 외부 LLM/Embedding API에 유료 probe를 보내지는 않으며,
각 요청 시 Adapter의 표준 예외로 가용성 실패를 처리한다. 문서 처리 기능을 의도적으로 비활성화한 배포만
`READINESS_REQUIRE_DOCUMENT_PROCESSING=false`를 사용한다.

---

# 15. Transaction Boundary

다음은 하나의 ACID Transaction이 아니다.

```text
Backend PostgreSQL
MinIO
Qdrant
External LLM/Embedding
```

따라서 상태 기반 처리를 전제로 한다.

문서 처리:

```text
PROCESSING
↓
성공 → COMPLETED
실패 → FAILED
```

AI Server는 성공/실패/실패 사유를 Backend가 상태 갱신할 수 있는 형태로 반환해야 한다.

---

# 16. 향후 확장을 위한 경계만 유지할 항목

초기에는 구현하지 않는다.

```text
Queue Worker
Reranker
Hybrid Search
Semantic Chunking
Parent-Child Retrieval
External Tool
Multi-Agent
```

현재 코드가 이 기능을 구현하지 않더라도 Service/Adapter 경계가 확장을 불필요하게 막지 않는 정도만 고려한다.
