# 구현범위-AI

# 최종 구현범위

## 프로젝트 목표

`Frontend ↔︎ Backend ↔︎ AI Server` 3계층 구조의 멀티턴 Agentic RAG 서비스를 구현

사용자는 웹 화면에서 로그인한 뒤 문서를 업로드하고, 업로드한 문서를 기반으로 AI와 멀티턴 대화를 수행

AI는 문서 검색, 문서 요약, 일반 질의를 Agent Tool Calling으로 분기하고, 답변 생성 과정에서 발생하는 Agent/Tool/RAG 실행 상태와 최종 답변을 WebSocket으로 실시간 전달

```
React + Vite + MUI Frontend
          │
          │ REST / WebSocket
          ▼
Java + Spring Boot Backend
Spring Security
          │
          │ Internal REST / WebSocket
          ▼
Python + FastAPI AI Server
          │
          ├─ Agent / Tool Calling
          ├─ RAG / Query Rewrite
          ├─ Document Pipeline
          ├─ Context Management
          ├─ Usage Measurement
          ├─ Qdrant
          └─ External LLM / Embedding API
```

핵심 원칙

- Frontend는 AI Server에 직접 접근하지 않음
- 모든 사용자 요청은 Backend를 경유
- 인증/인가 및 사용자 기능은 Backend가 담당
- AI Server는 AI 처리에 집중
- 사용자/권한/대화/문서 소유권의 Source of Truth는 Backend
- Qdrant는 Vector Search 전용 저장소로 사용
- WebSocket은 Chat 및 AI 실행 상태 Streaming에 사용
- REST는 문서 업로드/조회 등 단발성 요청에 사용
- 내부 Chain-of-Thought는 노출하지 않고 실제 실행 상태인 Observable Execution Trace만 제공

# 1. 확정 기술 스택

## Frontend

| 영역 | 기술 |
| --- | --- |
| OS 개발환경 | Windows 11 |
| Language | TypeScript |
| UI Framework | React 19.2 (NVM 사용) |
| Build Tool | Vite |
| UI Component | MUI(Material UI) |
| REST Client | `fetch` 또는 Axios |
| Streaming | WebSocket |
| node, npm | 24.18.0, 11.16.0 |

## Backend

| 영역 | 기술 |
| --- | --- |
| OS 개발환경 | Windows 11 |
| Language | Java MS OpenJDK 21.0.11 |
| java bulid | Maven 3.9.16 |
| Framework | Spring Boot 3.5.4 |
| Security | Spring Security |
| ORM | Spring Data JPA |
| Database | Docker Desktop + PostgreSQL |
| Validation | Jakarta Validation |
| REST | Spring MVC |
| WebSocket | Spring WebSocket |
| Monitoring | Spring Boot Actuator |
| AI 연동 | Internal REST / WebSocket Client |
| API 협업 | swagger |

## AI Server

| 영역 | 기술 |
| --- | --- |
| OS 개발환경 | Windows 11 |
| Python | 3.12.10 (`venv`) |
| API Server | FastAPI |
| Agent | LangChain Tool Calling |
| PDF Parsing | PyMuPDF |
| Chunking | Recursive Chunking |
| Vector DB | Qdrant |
| LLM | OpenAI API / Ollama Cloud 등 API Key 기반 외부 LLM API |
| Embedding | 외부 Embedding API |
| Streaming | WebSocket |

# 2. AI Server 책임

AI Server는 AI/RAG 처리에 집중

구현 범위

- 문서 Parsing
- 문서 Metadata 추출
- Recursive Chunking
- Embedding
- Qdrant Vector 저장
- Vector Search
- Metadata Filtering
- Agent Tool Calling
- Query Rewrite
- RAG
- Document Summary
- Multi-turn Context 처리
- Context Token Budget 관리
- Conversation Summary 생성
- Prompt 관리
- LLM 호출
- Citation 생성
- Usage 측정
- Agent/Tool/Retrieval 실행 Event 생성
- WebSocket Streaming
- 오류 Event 생성

AI Server는 다음 기능의 Source of Truth가 아님

- 회원정보
- 로그인정보
- 사용자 Role
- 서비스 권한
- Billing
- 사용자 대화 원본 데이터
- 문서 소유권

# 3. 전체 통신 구조

## REST 경로

REST는 단발성 요청에 사용

```
Frontend
   │ REST
   ▼
Backend
   │ Internal REST
   ▼
AI Server
```

대표 기능

- 문서 업로드
- 문서 목록
- 문서 삭제
- 문서 처리상태
- 대화 목록
- 사용자 정보
- Usage 조회

## WebSocket 경로

Chat과 Streaming은 WebSocket으로 처리

```
Frontend
   ↕ WebSocket
Backend
   ↕ WebSocket
AI Server
```

Backend는 WebSocket Gateway/Relay 역할을 함

AI Server가 만든 Event

```
AI Server
   │ status / tool_start / delta / citation / usage
   ▼
Backend
   │ 인증 세션 및 요청 매핑
   ▼
Frontend
```

Frontend가 AI Server WebSocket에 직접 연결하지 않음

# 4. 파일 저장 책임

Qdrant는 원본 파일 저장소로 사용하지 않음

구조

```
MinIO
        │
        └─ 원본 문서

PostgreSQL
        │
        └─ 문서 Metadata / 소유권 / 상태

Qdrant
        │
        └─ Chunk / Vector / Retrieval Metadata
```

개발환경에서는 MinIO를 Docker Compose로 구성하여 원본 문서 저장소로 사용

Storage Interface를 분리하여 향후 다음으로 교체 가능하도록 함

- S3 compatible storage
- Cloud Object Storage

# 5. 문서 지원 형식

## 현재 필수

```
PDF
TXT
MD
```

## 추후 확장

```
DOCX
PPTX
XLSX
CSV
HTML
HWP
HWPX
```

문서 포맷별 Parser 로직이 Service 전체에 분산되지 않도록 함

```
File
  ↓
Parser Registry
  ├─ PdfParser
  ├─ TxtParser
  ├─ MarkdownParser
  └─ Future Parser
  ↓
Normalized Document
  ↓
Chunking
  ↓
Embedding
  ↓
Qdrant
```

# 6. 문서 Validation

## Backend Validation

업로드 요청 및 서비스 정책 검증

- 지원 확장자
- MIME Type
- 빈 파일
- 최대 File Size
- 중복 파일 정책
- 사용자별 업로드 권한
- 사용자별 Quota

## AI Server Validation

실제 문서 처리 가능 여부 검증

- Parsing 가능 여부
- 손상 PDF
- 암호화 PDF

Document 처리 상태

```
UPLOADED
PROCESSING
COMPLETED
FAILED
```

실패 시 실패 사유를 저장/반환

# 7. 문서 업로드 처리 흐름

```
Frontend
   │ 파일 업로드
   ▼
Backend
   │
   ├─ 사용자 인증
   ├─ Backend Validation
   ├─ 소유권 Metadata 생성
   └─ MinIO 원본 저장
   │
   │ document_id / storage_key 전달
   ▼
AI Server
   │
   ├─ MinIO 원본 조회
   ├─ Parser 선택
   ├─ AI Server Validation
   ├─ Parsing
   ├─ Chunking
   ├─ Embedding
   └─ Qdrant 저장
   │
   ▼
Backend
   │ 처리 결과 / Metadata 갱신
   ▼
Frontend
```

대용량 문서 처리에 대비하여 내부 구조는 동기 처리에 고정하지 않고
추후 Background Job/Queue 방식으로 확장 가능하게 만듬

# 8. 문서 저장 정책

RAG 대상 문서는 기본적으로 Embedding

문서 크기에 따라 달라지는 것

- Chunk 개수
- Embedding Token 사용량
- Summary 방식
- Context 구성 방식

Qdrant Point 기본 구조

```
id = chunk_id
vector = embedding_vector

payload
├─ chunk_text
├─ user_id
├─ document_id
├─ filename
├─ page
└─ chunk_id
```

추가 가능 Metadata

```
file_type
section
title
source
created_at
```

# 9. 문서 크기 판단

페이지 수만으로 판단하지 않음

Parsing 이후 Python Service가 계산

```
page_count
character_count
token_count
chunk_count
```

처리 전략 판단 기준

```
token_count
llm_context_window
reserved_output_tokens
history_tokens
rag_context_tokens
```

이 판단은 LLM이 아니라 Python Service의 규칙으로 처리

# 10. Chunking

기본 Chunking은 Recursive 방식으로 확정

기본 설정값은 환경설정으로 분리

```
CHUNK_SIZE
CHUNK_OVERLAP
```

초기에는 범용적인 Recursive Chunking을 사용하고,
검색 품질 평가 이후 다음을 검토

- Structure-aware Chunking
- Semantic Chunking
- Parent-Child Retrieval

# 11. Embedding

모든 Chunk에 대해 Embedding을 생성

Embedding Model Name은 설정값으로 관리

```
EMBEDDING_MODEL
```

Qdrant Collection Vector Dimension은 선택한 Embedding Model과 일치시킴

Embedding 실패 시

- 전체 문서 상태 실패 여부
- Chunk 단위 재시도
- 부분 성공 허용 여부

를 구현 정책으로 명확히 관리

초기 구현에서는 문서 단위 성공/실패를 명확히 처리하는 것을 우선

# 12. 문서 Summary

## 작은 문서

전체 문서가 Context에 충분히 들어가는 경우

```
전체 문서
+
Summary Prompt
↓
LLM
```

## 큰 문서

Context를 초과하는 경우

```
Chunk별 Summary
↓
부분 Summary 결합
↓
최종 Summary Prompt
↓
LLM
```

필수 구현

- Direct Summary
- Map-Reduce / Hierarchical Summary

Python Service가 Token 기준으로 전략을 선택

# 13. Agent Tool

초기 Tool은 3개로 제한

| Tool | 역할 | 실행 위치 |
| --- | --- | --- |
| `search_documents` | 업로드 문서 RAG 검색 | AI Server → Qdrant |
| `summarize_document` | 특정 문서 요약 | AI Server → MinIO/Qdrant/LLM |
| `list_documents` | 등록 문서 조회 | AI Server → Backend Internal API → PostgreSQL |

문서와 무관한 일반 질문은 Tool을 호출하지 않고 LLM이 최종 답변을 생성

Agent는 LLM Tool Calling으로 질문의 의미를 판단해 필요한 Tool을 선택

Tool 실행 경계

```
AI Local Tool
├─ search_documents
└─ summarize_document

Backend Tool
└─ list_documents

External Tool
└─ 추후 Web Search / GitHub / Email / Calendar / 사내 API 등
```

- AI Server 소유 기능과 데이터는 AI Server에서 직접 실행
- Backend가 Source of Truth인 서비스 데이터는 Backend Internal API를 통해 조회
- 외부 Tool은 해당 외부 API/MCP 등 명시된 연결 경계를 통해 실행
- Tool 입력의 사용자/문서 Scope는 Backend가 전달한 검증된 실행 Context를 기준으로 제한

Agent 반복 실행 제한

```
MAX_AGENT_STEPS
MAX_TOOL_CALLS
```

Agent Run은 설정된 최대 Step 및 Tool 호출 횟수를 초과하지 않도록 제한

# 14. Agent와 Python 판단 분리

| 판단 | 담당 |
| --- | --- |
| Token 계산 | Python |
| Chunk 계산 | Python |
| Context 초과 여부 | Python |
| Summary 전략 | Python |
| Vector Search 실행 | Python |
| Metadata Filter | Python |
| Parser 선택 | Python |
| 업로드/서비스 정책 Validation | Spring Backend |
| Parsing 가능 여부/문서 처리 Validation | Python |
| 사용자 인증/권한 | Spring Backend |
| 문서 소유권 | Spring Backend |
| 질문 의미 이해 | LLM |
| 문서검색 필요 여부 | LLM Agent |
| Tool 선택 | LLM Agent |
| Query Rewrite | LLM |
| Summary 생성 | LLM |
| 최종 답변 | LLM |

# 15. Multi-turn 대화

대화 원본은 Backend DB에서 관리

기본 식별자

```
conversation_id
message_id
role
content
created_at
```

예

```
User      : Qdrant가 뭐야?
Assistant : Vector DB입니다.
User      : 그럼 장점은?
Assistant : ...
```

Backend는 AI 요청 시 필요한 Conversation Context를 AI Server에 전달

AI Server는 Backend가 제공한 Context를 사용해 Query Rewrite 및 최종 답변을 생성

# 16. Query Rewrite

RAG 검색에서 후속 질문은 독립 Query로 재작성

예

```
이전:
Qdrant가 뭐야?

현재:
그럼 장점은?
```

검색 Query

```
Qdrant를 RAG에서 사용할 때의 장점은 무엇인가?
```

Query Rewrite 결과는 Retrieval용으로만 사용하며
사용자가 입력한 원문 Message를 덮어쓰지 않음

# 17. Context 초과 처리

전체 History를 매번 LLM에 전달하지 않음

기본 구조

```
Conversation Summary
+
최근 N개 Message
+
RAG Context
+
현재 질문
```

필수

- Token 계산
- 최근 Message Sliding Window
- 오래된 History Summary
- RAG Context Token 계산
- 최종 Token Budget 검증
- Output Token Reservation

Backend는 원본 Message를 보관하고,
AI Server는 LLM 입력용 Context를 구성

필요 시 AI Server가 생성한 Conversation Summary를 Backend에 반환하여 저장

# 18. WebSocket Chat

## Frontend ↔︎ Backend

Frontend는 Backend의 Chat WebSocket에 연결한다.

예

```
wss://service.example.com/ws/chat
```

역할

- 인증된 WebSocket 연결
- 사용자 Message 전송
- Streaming Event 수신
- 연결 종료/재연결
- 오류 표시

## Backend ↔︎ AI Server

Backend는 AI Server Internal WebSocket에 연결

예

```
ws://ai-server/internal/ws/chat
```

역할

- 신뢰 가능한 사용자/대화 Context 전달
- AI Event 수신
- Frontend로 Event 중계

# 19. WebSocket 인증

Frontend WebSocket은 익명 연결을 허용하지 않는 것을 기본 원칙으로 함

Backend가 연결 시 인증 상태를 검증

검증 대상

- Access Token
- 사용자 상태
- 권한
- 차단 계정 여부

연결 후 각 Message에 대해서도 `conversation_id` 소유권을 검증

AI Server의 Internal WebSocket은 외부 공개 Endpoint로 사용하지 않음

Backend ↔︎ AI Server 간 인증은 내부 Network 및 Service 인증 방식으로 분리할 수 있도록 함

# 20. WebSocket Event 계약

AI Server → Backend → Frontend Event

| Event | 의미 |
| --- | --- |
| `start` | 요청 시작 |
| `status` | 현재 처리 단계 |
| `tool_start` | Tool 실행 시작 |
| `tool_end` | Tool 실행 완료 |
| `retrieval_start` | RAG 검색 시작 |
| `retrieval_result` | 검색 결과 Metadata |
| `delta` | 답변 Text 조각 |
| `citation` | 출처 |
| `usage` | 사용량 |
| `done` | 정상 완료 |
| `error` | 오류 |
| `cancelled` | 취소 완료 |

추후

```
heartbeat
summary_progress
document_processing
```

# 21. Observable Execution Trace

GPT류 UI처럼 현재 실행 상태를 실시간 표시

표시 가능 예

```
질문을 분석하고 있습니다.
Query Rewrite를 수행하고 있습니다.
관련 문서를 검색하고 있습니다.
관련 Chunk 5개를 찾았습니다.
문서를 요약하고 있습니다.
답변을 생성하고 있습니다.
```

노출 가능

- Agent 시작/완료
- Tool 시작/완료
- Query Rewrite 여부
- Retrieval 상태
- 검색 결과 수
- Summary 상태
- 답변 생성 상태

노출하지 않음

- LLM 내부 Chain-of-Thought
- 시스템 Prompt
- API Key
- 내부 Stack Trace
- 보안 관련 내부 Metadata

# 22. WebSocket Message Schema

## Frontend → Backend

예

```json
{
  "type": "message",
  "request_id": "req-001",
  "conversation_id": "conv-001",
  "message": "업로드 문서에서 Qdrant의 장점을 찾아줘"
}
```

Frontend는 `user_id`를 신뢰 정보로 전달하지 않음

Backend가 인증 Principal에서 실제 `user_id`를 결정

## Backend → AI Server

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

필요 시

```
document_ids
metadata_filter
locale
```

## AI Server → Backend

```json
{
  "type": "status",
  "request_id": "req-001",
  "stage": "retrieval",
  "message": "관련 문서를 검색하고 있습니다."
}
```

```json
{
  "type": "delta",
  "request_id": "req-001",
  "content": "Qdrant의 주요 장점은"
}
```

```json
{
  "type": "citation",
  "request_id": "req-001",
  "document_id": "doc-001",
  "filename": "guide.pdf",
  "page": 12
}
```

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

```json
{
  "type": "done",
  "request_id": "req-001"
}
```

모든 Event에 가능한 한 `request_id`를 포함

# 23. Citation

RAG 답변에는 가능한 경우 Citation을 제공

기본 구조

```
document_id
filename
chunk_id
page        # PDF에서 사용, Optional
section     # MD 등 구조 정보가 있는 문서에서 사용, Optional
```

- PDF는 가능한 경우 `page`를 제공
- TXT는 `chunk_id`를 기본 위치 식별자로 사용
- MD는 `chunk_id`를 기본으로 사용하고 가능한 경우 `section`을 함께 제공

Backend는 Citation에 포함된 `document_id`가 해당 사용자에게 노출 가능한 문서인지 검증할 수 있어야 함

Frontend는 문서 형식에 따라 Citation의 문서/페이지/Section 정보를 표시

# 24. Usage Tracking

AI Server가 OpenAI API, Ollama Cloud 등 실제 LLM Provider가 반환한 사용량을 공통 Usage Model로 수집하고 Backend가 서비스 데이터로 저장

사용자 요청 1회에서 Agent 판단, Query Rewrite, 최종 답변, Conversation Summary 등 여러 LLM 호출이 발생할 수 있으므로 Agent Run 단위 Usage와 개별 LLM Call Usage를 구분

## Agent Run Usage

```
request_id
user_id
conversation_id
total_input_tokens
total_output_tokens
total_tokens
llm_call_count
retrieved_chunk_count
latency_ms
status
created_at
```

## LLM Call Usage

```
request_id
call_id
call_type
provider
model
input_tokens
output_tokens
total_tokens
context_token_count
latency_ms
status
created_at
```

Provider별 Usage 응답은 AI Server 내부에서 공통 필드로 정규화

예

```
OpenAI API
→ input_tokens / output_tokens / cached_input_tokens / reasoning_tokens 등

Ollama Cloud
→ Provider 응답에서 확인 가능한 입력/출력 Token 및 처리시간 정보
```

Provider별로 제공되지 않는 Optional 필드는 `null` 또는 미설정으로 처리

Optional

```
cached_input_tokens
reasoning_tokens
```

## 문서 처리

```
document_id
file_type
file_size
page_count
character_count
token_count
chunk_count
embedding_token_count
parsing_time_ms
embedding_time_ms
status
```

활용

- 사용자별 Usage
- 모델별 Usage
- Quota
- 비용 계산
- 일/월 통계
- 운영 분석

# 25. API Key / Secret 관리

다음 값은 코드에 하드코딩하지 않음

Backend

```
DB_URL
DB_USERNAME
DB_PASSWORD
JWT_SECRET 또는 Signing Key
REFRESH_TOKEN 설정
AI_SERVER_URL
AI_SERVER_INTERNAL_KEY
```

AI Server

```
LLM_PROVIDER
LLM_API_KEY
LLM_MODEL
EMBEDDING_MODEL
QDRANT_URL
QDRANT_API_KEY
QDRANT_COLLECTION
MINIO_URL
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
MINIO_BUCKET
CHUNK_SIZE
CHUNK_OVERLAP
TOP_K
MAX_CONTEXT_TOKENS
MAX_AGENT_STEPS
MAX_TOOL_CALLS
```

환경변수 또는 설정 계층으로 관리하고
개발/테스트/운영 환경을 분리

# 26. Prompt 관리

Prompt는 코드 전체에 산재시키지 않음

분리 대상

```
Agent Prompt
RAG Answer Prompt
Summary Prompt
Query Rewrite Prompt
Conversation Summary Prompt
```

Prompt 변경이 Service 코드 변경과 독립적으로 이루어질 수 있는 구조를 지향

# 27. 오류 처리 표준화

## Frontend

- 사용자 친화적 오류 메시지
- 재로그인 필요 상태
- 네트워크 오류
- 업로드 실패
- WebSocket 연결 실패
- AI 처리 실패
- 재시도 버튼

## Backend

공통 Error Response Schema를 사용

예

```json
{
  "code": "DOCUMENT_NOT_FOUND",
  "message": "문서를 찾을 수 없습니다.",
  "request_id": "req-001"
}
```

분류

- Authentication Error
- Authorization Error
- Validation Error
- Resource Not Found
- Conflict
- Rate Limit
- AI Server Error
- Internal Server Error

## AI Server

AI 내부 오류를 그대로 외부에 노출하지 않음

표준화된 Error Event를 Backend에 전달

# 28. Timeout / Retry

시스템 안정성을 위해 외부 의존 호출에 Timeout을 둠

대상

- LLM API
- Embedding API
- Qdrant
- Backend → AI Server
- AI Server → 외부 API

Retry는 무조건 적용하지 않음

권장

- 네트워크 일시 오류: 제한적 Retry
- Validation 오류: Retry 안 함
- 인증 오류: Retry 안 함
- LLM 429/일시적 5xx: Backoff 정책 검토
- 중복 실행 위험이 있는 요청: Idempotency 고려

Agent 반복 실행은 `MAX_AGENT_STEPS`, `MAX_TOOL_CALLS`로 제한하여 무한 Tool Loop를 방지

# 29. WebSocket 안정성

필수 고려

- 연결 인증
- 연결 종료 감지
- Client Disconnect
- Server Disconnect
- 재연결
- Heartbeat/Ping-Pong
- Idle Timeout
- 동일 사용자 과도한 연결 제한
- Message Size 제한
- 비정상 Event 처리
- 요청별 `request_id` 매핑

Frontend 재연결 시 중복 요청이 자동 재실행되지 않도록 주의

# 30. 요청 취소

추후 또는 안정성 범위에서 Chat 취소 기능을 지원할 수 있도록 Protocol을 설계

예

```json
{
  "type": "cancel",
  "request_id": "req-001"
}
```

흐름

```
Frontend
  ↓ cancel
Backend
  ↓ cancel
AI Server
  ↓
LLM/Agent 취소 가능한 범위에서 중단
  ↓
cancelled
```

# 31. Logging

Frontend

- 운영환경에서 민감정보 로그 금지

Backend

- HTTP Request
- 인증 실패
- 사용자/문서 주요 행위
- AI Request
- AI Response 상태
- WebSocket 연결/종료
- 오류

AI Server

- `request_id`
- Tool 실행
- Retrieval
- LLM 호출 상태
- Usage
- 처리시간
- 오류

다음은 로그에 남기지 않음

- 비밀번호
- Access/Refresh Token 원문
- API Key
- 불필요한 문서 전체 내용
- 민감 Prompt

# 32. Request ID / Trace

Frontend → Backend → AI Server 전 구간에서 동일 요청을 추적할 수 있도록 함

```
request_id
```

가능하면 HTTP Header와 WebSocket Event 모두에 포함

향후

- OpenTelemetry
- Distributed Tracing
- Trace ID / Span ID

로 확장 가능하게 구성

# 33. Health Check

## Backend

Spring Boot Actuator 사용

예

```
/actuator/health
```

확인 대상

- Application
- PostgreSQL
- AI Server 연결 상태

## AI Server

별도 Health Endpoint 제공

예

```
/health
/ready
```

확인 대상

- FastAPI
- Qdrant
- 필수 설정
- 외부 API 연동 가능성

Liveness와 Readiness를 구분할 수 있도록 함

# 34. 보안

필수

- Spring Security
- Password Hash
- 인증/인가
- 사용자별 Resource Ownership 검사
- CORS 제한
- CSRF 정책 검토
- 입력 Validation
- File Validation
- 업로드 Size 제한
- API Key Secret 분리
- 내부 AI Server 외부 노출 제한
- Stack Trace 외부 노출 금지
- SQL Injection 방지(JPA/Parameter Binding)
- XSS 방지
- 민감 로그 차단

AI Server Tool이 향후 외부 시스템을 호출하게 될 경우
Tool별 권한/Allowlist 정책을 추가

# 35. 데이터 무결성

Backend DB에서 다음 관계를 보장

```
User
 ├─ Documents
 └─ Conversations
      └─ Messages
```

사용자 A가 사용자 B의 다음 Resource에 접근할 수 없어야 함

- Document
- Conversation
- Message
- Citation Source
- Usage Record

삭제 정책도 정의

예

사용자 문서 삭제 시

```
Backend Metadata 삭제/상태변경
+
Original File 삭제
+
AI Server Qdrant Vector 삭제
```

부분 실패 시 재처리 가능한 상태를 남김

# 36. Qdrant Filtering

RAG 검색은 최소한 다음 Metadata Filter를 적용

```
user_id
document_id
```

필요 시

```
document_ids
file_type
```

Backend에서 접근 권한 검증을 했더라도
AI Server Vector Search에서도 `user_id` 기반 Filtering을 적용하여 Defense in Depth를 구성

# 37. 검색 품질

초기

```
Vector Search Top-K
```

검색 품질을 확인하며 다음 값을 설정으로 분리

```
TOP_K
SCORE_THRESHOLD
```

추후

- Reranking
- Hybrid Search
- Semantic Chunking
- Multi Query RAG
- HyDE

# 38. Citation과 Hallucination 완화

RAG 답변은 검색 Context에 근거해 답하도록 Prompt를 분리

검색 근거가 충분하지 않은 경우

- 근거 부족을 명시
- 문서에 없는 내용을 문서 근거인 것처럼 생성하지 않음
- Citation을 임의 생성하지 않음

Citation은 실제 Retrieval 결과에서 생성

# 39. AI Server Internal API 범위

외부 사용자에게 직접 공개하지 않음

예

```
POST   /internal/documents
DELETE /internal/documents/{document_id}
GET    /internal/documents/{document_id}/status
WS     /internal/ws/chat
GET    /health
GET    /ready
```

필요 시 문서 Summary 등을 별도 REST로 노출할 수 있으나
일반 사용자 Client는 Backend를 통해서만 접근

# 40. Internal API 보안

Backend ↔︎ AI Server 통신은 일반 사용자 인증과 분리

가능한 방식

- Private Network
- Internal API Key
- mTLS
- Gateway 정책

초기에는 구현 복잡도에 맞는 방식을 사용하되
AI Server Internal Endpoint가 인터넷에 무제한 노출되는 구조는 피함

# 41. Transaction 경계

Backend DB Transaction과 AI Server/Qdrant 작업은 하나의 DB Transaction으로 묶을 수 없음

따라서 상태 기반 처리로 설계

예: 문서 업로드

```
Backend document = PROCESSING
↓
AI 처리 요청
↓
성공
→ COMPLETED

실패
→ FAILED
```

삭제도 동일하게 부분 실패를 고려

필요 시 Retry/Compensation이 가능하도록 상태를 남김

# 42. 비동기 작업 확장

초기 구현은 단순화를 위해 동기 문서 처리로 시작할 수 있음

다만 대용량 문서에서 요청 Timeout을 피할 수 있도록 추후

```
Backend
  ↓
Queue
  ↓
AI Worker
```

형태로 확장 가능한 Service 경계를 유지

후보

- RabbitMQ
- Kafka
- Redis Queue 계열

Queue 자체는 초기 필수 구현에는 포함하지 않음

# 43. 테스트 범위

## Frontend

- 주요 Component
- 로그인 Flow
- 문서 업로드 Flow
- WebSocket Streaming UI
- 오류 상태

## Backend Unit Test

- Auth
- Authorization
- Document Ownership
- Conversation Ownership
- Service
- Validation

## Backend Integration Test

- PostgreSQL 연동
- Security Filter
- REST API
- WebSocket
- AI Server Mock 연동

## AI Unit Test

- Parser
- Chunker
- Token Budget
- Summary Strategy
- Metadata Filter
- Tool

## AI Integration Test

- Qdrant
- Embedding
- Agent
- Retrieval
- WebSocket Event

## E2E

```
React
↓
Spring Boot
↓
FastAPI
↓
Qdrant / LLM
```

전체 시나리오를 확인

# 44. 개발 환경

권장 로컬 구성

```
Frontend        localhost:5173
Backend         localhost:8080
AI Server       localhost:8000
PostgreSQL      localhost:5432
Qdrant          localhost:6333
MinIO API       localhost:9000
MinIO Console   localhost:9001
```

환경별 URL은 설정으로 분리

# 45. 배포 구조 고려

초기 로컬 개발 후 다음처럼 독립 배포 가능하게 구성

```
Frontend
Backend
AI Server
PostgreSQL
Qdrant
MinIO
```

각 서비스는 환경변수 기반으로 연결

개발환경의 PostgreSQL/Qdrant/MinIO 등 인프라 컴포넌트는 Docker Compose로 구성

운영에서는 HTTPS/WSS 사용을 기본으로 함

# 46. API Versioning

외부 Backend API는 변경 가능성을 고려해 Versioning을 사용할 수 있음

예

```
/api/v1/...
```

AI Internal API도 필요 시

```
/internal/v1/...
```

로 구분할 수 있음

초기부터 URL Versioning을 적용할지는 구현 시 결정하되
DTO와 내부 Model을 직접 결합하지 않음

# 47. DTO / Contract 관리

Frontend ↔︎ Backend와 Backend ↔︎ AI Server의 Contract를 분리

예

```
Frontend DTO
≠
Backend Entity
≠
AI Internal DTO
```

Backend Entity를 그대로 JSON Response로 노출하지 않음

AI Server Event Schema는 명시적으로 관리

필요 시 OpenAPI/JSON Schema 기반으로 Contract를 문서화

# 48. 검색/RAG 고도화

필수 구현 완료 후 추가

## Reranking

```
Vector Search Top-K
↓
Reranker
↓
최종 Context
```

## Hybrid Search

```
Dense Vector
+
Sparse/Keyword
```

## 추가

- Semantic Chunking
- Parent-Child Retrieval
- Multi Query RAG
- HyDE
- 장기 Memory Vector Search

# 49. Agent Tool 확장

현재

```
search_documents
summarize_document
list_documents
```

문서와 무관한 일반 질문은 Tool 호출 없이 LLM이 직접 최종 답변을 생성

추후

## 문서

- `compare_documents`
- `get_document_info`
- `search_specific_document`

## 데이터

- SQL 조회
- 통계 분석
- 사용자 데이터 조회

## 외부

- Web Search
- GitHub
- Email
- Calendar
- 사내 API

## AI

- 번역
- 문서 작성
- 문서 비교
- 데이터 분석

Tool 공통 계약

```
Tool Name
Description
Input Schema
Output Schema
Execution Function
```

# 50. 초기 구현 제외/추후 확장

초기 필수 범위에서 제외하지만 구조적으로 고려

- DOCX/PPTX/XLSX/HWP Parser
- OCR
- Queue 기반 비동기 문서처리
- Reranker
- Hybrid Search
- Multi-Agent
- Web Search Tool
- SQL Agent
- Email/Calendar Tool
- 조직/테넌트 기능
- Billing
- 관리자 Dashboard 고도화
- SSO/OAuth2
- Kubernetes
- Auto Scaling

# 51. 최종 아키텍처

```
┌──────────────────────────────────────────┐
│ React + Vite + MUI Frontend              │
│                                          │
│ Login / Documents / Chat / Citation      │
│ Streaming Status / Usage                 │
└───────────────────┬──────────────────────┘
                    │
             REST / WebSocket
                    │
┌───────────────────▼──────────────────────┐
│ Java + Spring Boot Backend               │
│                                          │
│ Spring Security                          │
│ Auth / User / Role                       │
│ Document Ownership                      │
│ Conversation / Message                   │
│ Usage / Audit                            │
│ REST API / WebSocket Gateway             │
│ Validation / Rate Limit / Resilience     │
└───────────┬───────────────────┬──────────┘
            │                   │
       PostgreSQL        Internal REST /
                         WebSocket
                                │
┌───────────────────────────────▼──────────┐
│ Python + FastAPI AI Server               │
│                                          │
│ Agent / Tool Calling                     │
│ Query Rewrite                            │
│ Context Management                       │
│ Document Pipeline                        │
│ RAG / Citation                           │
│ WebSocket Events                         │
│ Usage Measurement                       │
└─────────────┬─────────────────┬──────────┘
              │                 │
           Qdrant         LLM / Embedding API
```

원본 문서는 Docker Compose로 구성한 MinIO에 저장하며 Backend가 저장하고 AI Server가 문서 처리 시 조회

# 52. 구현 완료 기준

## 인증

1. 회원가입
2. 로그인
3. 인증된 API 호출
4. Refresh
5. 로그아웃
6. 다른 사용자의 Resource 접근 차단

## 문서

1. React에서 PDF/TXT/MD 업로드
2. Backend 인증/검증
3. MinIO 원본 저장 / Backend Metadata 저장
4. AI Server Parsing
5. Recursive Chunking
6. Embedding
7. Qdrant 저장
8. Backend 상태 `COMPLETED`
9. 문서 목록 표시
10. 문서 삭제 시 Vector까지 정리

## RAG

1. 사용자 질문
2. Backend WebSocket 수신
3. 소유권/대화 검증
4. AI Server 전달
5. Agent 판단
6. 필요 시 Query Rewrite
7. `search_documents`
8. Qdrant Filter/Search
9. Context 구성
10. Citation 포함 답변
11. Backend 중계
12. Frontend Streaming 표시

## 문서 Summary

1. 특정 문서 Summary 요청
2. 문서 소유권 확인
3. Token 계산
4. Direct/Hierarchical 결정
5. 최종 Summary
6. Streaming 또는 결과 전달

## Multi-turn

1. Backend가 Conversation/Message 저장
2. 후속 질문 입력
3. Conversation Context 전달
4. Query Rewrite
5. Context Budget 관리
6. 연결된 답변 생성
7. Assistant Message 저장

## Streaming

1. Frontend ↔︎ Backend WebSocket 인증 연결
2. Backend ↔︎ AI Server WebSocket 연결
3. `start`
4. `status`
5. `tool_start`
6. `retrieval_start`
7. `retrieval_result`
8. `tool_end`
9. `delta`
10. `citation`
11. `usage`
12. `done`
13. Frontend 실시간 표시
14. 실패 시 `error`

## 일반 질의

문서와 무관한 질문에서는 Tool을 호출하지 않고 LLM이 직접 최종 답변을 생성하며
불필요한 Qdrant Search를 수행하지 않음

## 안정성

다음을 확인

- 잘못된 Token 접근 차단
- 다른 사용자 문서 접근 차단
- AI Server Timeout 처리
- Qdrant 오류 처리
- LLM 오류 처리
- WebSocket Disconnect 처리
- 재연결 처리
- 문서 Parsing 실패 처리
- Upload Size 제한
- Rate Limit 기본 동작
- Request ID 추적
- Health Check
- 민감정보 로그 미노출

## 검증

- Frontend 전체 Flow
- Backend OpenAPI/Swagger
- Backend Unit/Integration Test
- AI Server Swagger/Internal API
- WebSocket Client Test
- Qdrant Retrieval 확인
- 사용자별 Metadata Filter 확인
- E2E Flow 확인

# 53. 최종 범위 요약

이번 프로젝트의 필수 완성 범위

```
React + Vite + MUI
        ↕
Spring Boot + Spring Security
        ↕
FastAPI Agentic RAG AI Server
        ↕
Qdrant / LLM / Embedding
```

포함

- 회원가입/로그인/로그아웃
- 사용자/권한
- Spring Security
- 문서 업로드/목록/삭제
- PDF/TXT/MD
- Parsing
- Recursive Chunking
- Embedding
- Qdrant
- MinIO 원본 문서 저장
- Agent Tool Calling
- RAG
- Citation
- Document Summary
- Query Rewrite
- Multi-turn
- Conversation Context
- WebSocket Streaming
- Agent/Tool/Retrieval 실행 상태
- Usage Tracking
- Backend Message 저장
- 오류 처리
- Validation
- Timeout/Retry
- WebSocket 안정성
- Rate Limit/Quota 확장 구조
- Logging/Request ID/Audit
- Health Check
- Frontend 상태/오류 UI
- Backend/AI 분리
- 사용자별 Data Isolation
- 테스트/E2E 검증

완료 후 추가 고도화

```
추가 문서 포맷
OCR
Queue
Reranking
Hybrid Search
Semantic Chunking
Multi-Agent
외부 Tool
SSO
Billing
대규모 배포/확장
```