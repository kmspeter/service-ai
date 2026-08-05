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

## 4. 권장 코드 구조

다음은 책임 경계를 코드에 반영하기 위한 권장 구조다.

```text
app/
├─ main.py
│
├─ api/
│  ├─ health.py
│  ├─ documents.py
│  └─ websocket.py
│
├─ core/
│  ├─ config.py
│  ├─ logging.py
│  ├─ exceptions.py
│  └─ request_context.py
│
├─ schemas/
│  ├─ document.py
│  ├─ chat.py
│  ├─ events.py
│  ├─ citation.py
│  └─ usage.py
│
├─ models/
│  ├─ document.py
│  ├─ chunk.py
│  ├─ retrieval.py
│  ├─ citation.py
│  └─ usage.py
│
├─ services/
│  ├─ document_service.py
│  ├─ ingestion_service.py
│  ├─ retrieval_service.py
│  ├─ rag_service.py
│  ├─ summary_service.py
│  ├─ query_rewrite_service.py
│  ├─ context_service.py
│  ├─ agent_service.py
│  ├─ usage_service.py
│  └─ event_service.py
│
├─ parsers/
│  ├─ base.py
│  ├─ registry.py
│  ├─ pdf.py
│  ├─ text.py
│  └─ markdown.py
│
├─ chunking/
│  ├─ base.py
│  └─ recursive.py
│
├─ providers/
│  ├─ llm/
│  │  ├─ base.py
│  │  ├─ openai.py
│  │  └─ ollama.py
│  │
│  └─ embedding/
│     ├─ base.py
│     └─ provider.py
│
├─ repositories/
│  ├─ vector/
│  │  ├─ base.py
│  │  └─ qdrant.py
│  └─ storage/
│     ├─ base.py
│     └─ minio.py
│
├─ clients/
│  └─ backend.py
│
├─ tools/
│  ├─ search_documents.py
│  ├─ summarize_document.py
│  └─ list_documents.py
│
└─ prompts/
   ├─ agent.*
   ├─ rag.*
   ├─ summary.*
   ├─ query_rewrite.*
   └─ conversation_summary.*
```

`*`의 실제 파일 형식은 구현 시 선택할 수 있다.

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
Agent
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

반복 제한:

```text
MAX_AGENT_STEPS
MAX_TOOL_CALLS
```

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
```

외부 LLM/Embedding Provider 상태를 Readiness 실패의 절대 조건으로 둘지는 구현 시 운영 정책으로 결정한다. `IMPLEMENTATION_SCOPE.md`는 외부 API 연동 가능성을 확인 대상으로 두고 있으므로 해당 범위 안에서 정책을 명시적으로 구현한다.

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
