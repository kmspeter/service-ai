# AI Server Contracts

## 1. 목적

이 문서는 AI Server에서 변경 영향이 큰 계약을 한 곳에서 관리한다.

대상:

- Internal REST
- WebSocket Message
- Observable Event
- Document/Chunk/Citation Model
- Tool Input/Output
- Usage Model

최종 요구사항은 `IMPLEMENTATION_SCOPE.md`가 우선한다.

---

# 2. 공통 식별자

가능한 모든 요청/이벤트에서 다음을 유지한다.

```text
request_id
```

주요 식별자:

```text
user_id
conversation_id
message_id
document_id
chunk_id
call_id
```

Frontend에서 전달된 `user_id`를 신뢰 정보로 사용하지 않는 것이 전체 시스템 원칙이다.

AI Server는 Backend가 전달한 검증된 실행 Context를 사용한다.

---

# 3. Internal REST Endpoints

기본 범위:

```text
POST   /internal/documents
DELETE /internal/documents/{document_id}
GET    /internal/documents/{document_id}/status
WS     /internal/ws/chat

GET    /health
GET    /ready
```

필요 시 API Versioning:

```text
/internal/v1/...
```

초기 적용 여부는 구현 시 결정하되 DTO와 내부 Model을 직접 결합하지 않는다.

---

# 4. Document Processing Request

`IMPLEMENTATION_SCOPE.md`는 Backend가 AI Server에 `document_id / storage_key`를 전달하는 흐름을 정의한다.

AI-only 개발 시 사용할 최소 Internal DTO는 다음 개념을 포함한다.

```json
{
  "request_id": "req-001",
  "user_id": "user-123",
  "document_id": "doc-001",
  "storage_key": "documents/doc-001/source.pdf"
}
```

주의:

- 이 DTO는 Backend 인증을 대체하지 않는다.
- 실제 Backend 구현 시 Contract를 최종 동결한다.
- Backend가 전달한 검증된 `user_id`/문서 Scope를 기준으로 처리한다.

---

# 5. Document Processing Result

문서 처리 상태 개념:

```text
UPLOADED
PROCESSING
COMPLETED
FAILED
```

AI Server 처리 결과에서 최소한 다음을 표현할 수 있어야 한다.

```json
{
  "request_id": "req-001",
  "document_id": "doc-001",
  "status": "COMPLETED",
  "file_type": "pdf",
  "page_count": 12,
  "character_count": 53210,
  "token_count": 15420,
  "chunk_count": 31,
  "embedding_token_count": 18300,
  "parsing_time_ms": 340,
  "embedding_time_ms": 910,
  "failure_reason": null
}
```

Provider가 제공하지 않는 계측값은 Optional로 처리한다.

---

## 5.1 Document Delete & Status

`DELETE`와 `GET`은 body가 없는 Internal API이므로 Backend 실행 Context를 query로 전달한다.

```text
DELETE /internal/documents/{document_id}?request_id=req-001&user_id=user-123
GET    /internal/documents/{document_id}/status?request_id=req-002&user_id=user-123
```

`user_id`는 Backend가 인증·소유권을 검증한 뒤 전달한 Scope다. AI Server는 소유권을 새로 판정하지
않지만 Qdrant 접근에는 Defense in Depth로 `user_id + document_id` Filter를 모두 적용한다.

삭제 성공:

```json
{
  "request_id": "req-001",
  "document_id": "doc-001",
  "status": "DELETED",
  "deleted_point_count": 3,
  "failure_reason": null,
  "retryable": false
}
```

삭제 대상이 없으면 HTTP 404와 `NOT_FOUND`, Qdrant 실패는 HTTP 502와
`FAILED / QDRANT_DELETE_FAILED / retryable=true`를 반환한다. 삭제 Endpoint는 Qdrant Vector만
삭제하며 Backend Metadata와 MinIO 원본을 변경하지 않는다.

상태 응답은 기존 `UPLOADED / PROCESSING / COMPLETED / FAILED` 개념을 지원한다. AI Server는
Ingestion 중인 상태와 최근 결과만 process-local 메모리에 보관하고, `COMPLETED`는 Qdrant의 기존
Chunk payload에서도 복원한다. 별도 문서 DB나 Backend Entity 복제본을 만들지 않는다. `UPLOADED`는
Backend 책임 상태이므로 AI Server가 임의로 생성하지 않는다. AI Server가 아는 상태가 없거나 다른
user Scope이면 HTTP 404를 반환한다.

---

# 6. Normalized Document

Parser 간 공통 출력을 위한 내부 개념.

예시:

```json
{
  "document_id": "doc-001",
  "filename": "guide.pdf",
  "file_type": "pdf",
  "page_count": 12,
  "character_count": 53210,
  "content_units": [
    {
      "text": "...",
      "page": 1,
      "section": null
    }
  ]
}
```

`page`, `section`은 포맷별 Optional이다.

---

# 7. Chunk

Qdrant 저장과 Citation 추적을 위한 내부 Chunk 개념.

```json
{
  "chunk_id": "chunk-001",
  "user_id": "user-123",
  "document_id": "doc-001",
  "filename": "guide.pdf",
  "file_type": "pdf",
  "page": 12,
  "section": null,
  "chunk_text": "..."
}
```

---

# 8. Qdrant Point

```text
id = chunk_id
vector = embedding_vector
```

Payload 최소 필드:

```json
{
  "chunk_text": "...",
  "user_id": "user-123",
  "document_id": "doc-001",
  "filename": "guide.pdf",
  "page": 12,
  "chunk_id": "chunk-001"
}
```

추가 가능:

```json
{
  "file_type": "pdf",
  "section": null,
  "title": null,
  "source": null,
  "created_at": null
}
```

---

# 9. Retrieval Request

내부 Service/테스트 기준 개념:

```json
{
  "request_id": "req-001",
  "user_id": "user-123",
  "query": "Qdrant의 장점은 무엇인가?",
  "document_ids": ["doc-001"],
  "top_k": 5
}
```

실제 `top_k`와 `score_threshold`는 기본적으로 환경설정을 사용하며 필요 시 명시적으로 Override 가능한지 구현 정책에서 정한다.

Phase 09 구현 정책:

- 기본값은 설정 계층의 `TOP_K`, `SCORE_THRESHOLD`를 사용한다.
- 내부 Service/개발 검증에서는 요청별 `top_k`, `score_threshold` Override를 허용한다.
- 문서 범위는 `document_id` 또는 `document_ids` 중 하나만 지정한다. 둘 다 없으면 사용자의 전체 문서 범위다.
- `user_id`는 문서 범위 지정 여부와 무관하게 모든 Qdrant 검색에 필수 Filter로 적용한다.
- `document_ids`의 중복 값은 검색 전에 제거한다.

---

# 10. Retrieval Result

```json
{
  "chunk_id": "chunk-001",
  "document_id": "doc-001",
  "filename": "guide.pdf",
  "page": 12,
  "section": null,
  "score": 0.87,
  "content": "..."
}
```

Retrieval Result는 Citation의 실제 근거다.

---

# 11. Citation

기본 구조:

```json
{
  "document_id": "doc-001",
  "filename": "guide.pdf",
  "chunk_id": "chunk-001",
  "page": 12,
  "section": null
}
```

정책:

- PDF: 가능한 경우 `page`
- TXT: `chunk_id`가 기본 위치 식별자
- MD: `chunk_id` + 가능한 경우 `section`
- 실제 Retrieval Result에 없는 Citation 생성 금지

---

# 12. Backend → AI Server WebSocket Message

기본 계약:

```json
{
  "type": "message",
  "request_id": "req-001",
  "user_id": "user-123",
  "conversation_id": "conv-001",
  "message": "업로드 문서에서 Qdrant의 장점을 찾아줘",
  "conversation_context": {
    "summary": "...",
    "recent_messages": []
  }
}
```

필요 시:

```json
{
  "document_ids": ["doc-001"],
  "metadata_filter": {},
  "locale": "ko-KR"
}
```

---

# 13. Cancel Message

향후/안정성 범위에서 취소 Protocol:

```json
{
  "type": "cancel",
  "request_id": "req-001"
}
```

취소 가능한 범위에서 실행을 중단하고:

```text
cancelled
```

Event를 반환한다.

---

# 14. AI Server Event Base

가능한 모든 Event:

```json
{
  "type": "event_type",
  "request_id": "req-001"
}
```

---

# 15. `start`

```json
{
  "type": "start",
  "request_id": "req-001"
}
```

---

# 16. `status`

```json
{
  "type": "status",
  "request_id": "req-001",
  "stage": "retrieval",
  "message": "관련 문서를 검색하고 있습니다."
}
```

`message`는 Observable Execution Trace이며 Chain-of-Thought가 아니다.

---

# 17. `tool_start`

```json
{
  "type": "tool_start",
  "request_id": "req-001",
  "tool_name": "search_documents"
}
```

---

# 18. `tool_end`

```json
{
  "type": "tool_end",
  "request_id": "req-001",
  "tool_name": "search_documents",
  "status": "success"
}
```

---

# 19. `retrieval_start`

```json
{
  "type": "retrieval_start",
  "request_id": "req-001"
}
```

---

# 20. `retrieval_result`

구현범위에서 의미는 "검색 결과 Metadata"다.

예시:

```json
{
  "type": "retrieval_result",
  "request_id": "req-001",
  "retrieved_chunk_count": 5
}
```

전체 Chunk Text를 Streaming Event로 불필요하게 노출하지 않는다.

---

# 21. `delta`

```json
{
  "type": "delta",
  "request_id": "req-001",
  "content": "Qdrant의 주요 장점은"
}
```

---

# 22. `citation`

```json
{
  "type": "citation",
  "request_id": "req-001",
  "document_id": "doc-001",
  "filename": "guide.pdf",
  "chunk_id": "chunk-001",
  "page": 12,
  "section": null
}
```

---

# 23. `usage`

최종 Streaming 예:

```json
{
  "type": "usage",
  "request_id": "req-001",
  "input_tokens": 1200,
  "output_tokens": 240,
  "total_tokens": 1440,
  "llm_call_count": 3,
  "latency_ms": 2100
}
```

내부 Usage Model은 더 상세할 수 있다.

---

# 24. `done`

```json
{
  "type": "done",
  "request_id": "req-001"
}
```

---

# 25. `error`

AI 내부 오류를 그대로 노출하지 않는다.

예시 계약:

```json
{
  "type": "error",
  "request_id": "req-001",
  "code": "AI_PROCESSING_FAILED",
  "message": "AI 요청 처리 중 오류가 발생했습니다."
}
```

Stack Trace, API Key, System Prompt 등의 정보는 포함하지 않는다.

---

# 26. `cancelled`

```json
{
  "type": "cancelled",
  "request_id": "req-001"
}
```

---

# 27. Agent Run Usage

```json
{
  "request_id": "req-001",
  "user_id": "user-123",
  "conversation_id": "conv-001",
  "total_input_tokens": 1200,
  "total_output_tokens": 240,
  "total_tokens": 1440,
  "llm_call_count": 3,
  "retrieved_chunk_count": 5,
  "latency_ms": 2100,
  "status": "COMPLETED",
  "created_at": "..."
}
```

---

# 28. LLM Call Usage

```json
{
  "request_id": "req-001",
  "call_id": "call-001",
  "call_type": "query_rewrite",
  "provider": "openai",
  "model": "...",
  "input_tokens": 300,
  "output_tokens": 50,
  "total_tokens": 350,
  "context_token_count": 300,
  "cached_input_tokens": null,
  "reasoning_tokens": null,
  "latency_ms": 450,
  "status": "COMPLETED",
  "created_at": "..."
}
```

---

# 29. Tool Contract — 공통

각 Tool은 다음 개념을 갖는다.

```text
Tool Name
Description
Input Schema
Output Schema
Execution Function
```

Tool 입력의 사용자/문서 Scope는 Backend가 전달한 검증된 실행 Context를 기준으로 제한한다.

---

# 30. Tool — `search_documents`

## 역할

업로드 문서 RAG 검색.

## 실행 위치

```text
AI Server → Qdrant
```

## Input 개념

```json
{
  "query": "Qdrant의 장점은?",
  "user_id": "user-123",
  "document_ids": ["doc-001"]
}
```

`user_id`는 Agent가 임의 생성하는 값이 아니라 실행 Context에서 주입/제한되어야 한다.

## Output 개념

```json
{
  "results": [
    {
      "chunk_id": "chunk-001",
      "document_id": "doc-001",
      "filename": "guide.pdf",
      "page": 12,
      "section": null,
      "score": 0.87,
      "content": "..."
    }
  ]
}
```

---

# 31. Tool — `summarize_document`

## 역할

특정 문서 요약.

## 실행 위치

```text
AI Server → MinIO/Qdrant/LLM
```

## Input 개념

```json
{
  "document_id": "doc-001",
  "user_id": "user-123"
}
```

## Output 개념

```json
{
  "document_id": "doc-001",
  "summary": "...",
  "strategy": "direct"
}
```

`strategy`는 구현 내부 진단/결과 표현용으로 `direct` 또는 hierarchical 계열을 사용할 수 있으며 최종 명칭은 코드 구현 시 고정한다.

---

# 32. Tool — `list_documents`

## 역할

등록 문서 조회.

## 실행 위치

```text
AI Server
 ↓
Backend Internal API
 ↓
PostgreSQL
```

AI Server가 Qdrant를 사용자 문서 목록의 Source of Truth로 사용하지 않는다.

## Input 개념

```json
{
  "user_id": "user-123"
}
```

실제 Backend 계약은 Backend 구현 시 최종 동결한다.

---

# 33. Contract 변경 규칙

다음 변경은 Backend/Frontend 영향이 크므로 임의 변경하지 않는다.

- WebSocket Event 이름
- Citation 필드
- request_id
- Backend → AI Message 구조
- Tool 이름
- Qdrant Payload의 격리 필드
- Usage 핵심 필드

변경이 필요하면:

1. 변경 이유
2. 기존 Contract 영향
3. Migration/호환성
4. Backend 영향

을 먼저 기록한다.
