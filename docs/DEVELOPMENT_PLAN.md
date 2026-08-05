# AI Server Development Plan

## 1. 목적

이 문서는 AI Server를 **작은 단위로 구현하고 각 단계에서 독립 검증한 뒤 다음 단계로 진행**하기 위한 실행 순서를 정의한다.

최종 요구사항은 `IMPLEMENTATION_SCOPE.md`가 우선한다.

원칙:

```text
외부 의존성이 적은 기능
        ↓
문서 Pipeline
        ↓
Retrieval / RAG
        ↓
Context / Summary
        ↓
Tool
        ↓
Agent
        ↓
Usage / Streaming
        ↓
안정성 / 통합 검증
```

각 Phase는 이전 Phase가 검증된 상태를 전제로 한다.

---

# Phase 01 — Project Skeleton

## 목표

FastAPI Server의 최소 실행 기반을 만든다.

## 구현

- Python 3.12 프로젝트 구성
- FastAPI App
- 설정 계층
- Logging 기본 구조
- 공통 Exception 기본 구조
- `/health`
- `/ready`
- 테스트 디렉터리 기본 구조
- `.env.example`

## 제외

- Qdrant 기능
- MinIO 기능
- LLM 호출
- Agent
- RAG

## 검증

- FastAPI 정상 기동
- `/health` 200
- `/ready` 기본 응답
- 기본 Unit Test 실행

## 완료 조건

- Secret 하드코딩 없음
- 설정 로딩 테스트 통과
- Health Endpoint 테스트 통과

---

# Phase 02 — Infrastructure Clients

## 목표

AI Server가 사용하는 저장/검색 인프라 연결 계층을 만든다.

## 구현

- Docker Compose의 Qdrant
- Docker Compose의 MinIO
- Qdrant Client Adapter
- MinIO Client Adapter
- 연결 Timeout
- 연결 오류 표준화
- Readiness에서 필수 인프라 상태 확인 가능

## 검증

- Qdrant 연결
- Collection 조회/생성 기반 확인
- MinIO Bucket 연결
- 테스트 Object 업로드/조회/삭제
- 잘못된 연결정보 오류 처리

## 완료 조건

- Qdrant/MinIO Adapter가 Service 코드와 분리됨
- 인프라 오류가 원시 SDK Exception 그대로 외부로 노출되지 않음

---

# Phase 03 — LLM Provider Abstraction

## 목표

특정 Provider에 종속되지 않는 LLM 호출 계층을 만든다.

## 구현

- 공통 LLM Interface
- Provider Adapter 구조
- OpenAI API Adapter
- Ollama Cloud 등 추가 Provider를 붙일 수 있는 구조
- Provider/Model 설정 분리
- Timeout
- Provider Usage → 공통 Usage Model 정규화
- latency 측정

## 공통 결과

가능한 범위에서:

```text
content
provider
model
input_tokens
output_tokens
total_tokens
cached_input_tokens     # Optional
reasoning_tokens        # Optional
latency_ms
status
```

## 검증

- 단순 일반 질문 1회 호출
- Provider 응답 Content 확인
- Usage 확인
- 인증 오류 처리
- Timeout 처리

## 완료 조건

- Service가 특정 Provider SDK 타입에 직접 의존하지 않음
- Provider 변경이 핵심 Service 수정 없이 가능

---

# Phase 04 — Embedding Provider

## 목표

문서와 Query를 Vector로 변환하는 Embedding 계층을 구현한다.

## 구현

- Embedding Interface
- 외부 Embedding Provider Adapter
- `EMBEDDING_MODEL`
- Vector Dimension 확인
- Embedding Usage 측정 가능한 경우 수집
- Timeout / 오류 표준화

## 검증

- 단일 문자열 Embedding
- 여러 문자열 Batch Embedding
- Vector Dimension 검증
- 빈 입력 정책 검증
- Provider 오류 검증

## 완료 조건

- Qdrant Collection Dimension과 선택한 Embedding Model Dimension이 일치

---

# Phase 05 — Parser Layer

## 목표

PDF/TXT/MD를 공통 Normalized Document로 변환한다.

## 구현 순서

```text
TXT
↓
MD
↓
PDF
```

## 구현

- Parser Interface
- Parser Registry
- TxtParser
- MarkdownParser
- PdfParser(PyMuPDF)
- 공통 Normalized Document Model
- 문서 Metadata 계산 기반

## PDF Validation

- 정상 PDF
- 손상 PDF
- 암호화 PDF

## 추출 대상

가능한 범위에서:

```text
filename
file_type
page_count
character_count
page
section
content
```

## 완료 조건

- Parser 선택 로직이 Registry에 집중됨
- Parser 구현이 Document Service 전체에 분산되지 않음
- PDF/TXT/MD Fixture 테스트 통과

---

# Phase 06 — Token Measurement & Recursive Chunking

## 목표

Normalized Document를 Retrieval 가능한 Chunk로 변환한다.

## 구현

- Token 계산
- `CHUNK_SIZE`
- `CHUNK_OVERLAP`
- Recursive Chunking
- Chunk Model
- Chunk Metadata 보존

## Chunk Metadata 최소값

```text
chunk_id
document_id
filename
page
section
chunk_text
```

`page`, `section`은 문서 포맷에 따라 Optional이다.

## 문서 통계

```text
page_count
character_count
token_count
chunk_count
```

## 완료 조건

- Chunk Size/Overlap이 환경설정으로 변경 가능
- Chunk마다 원본 위치를 추적할 Metadata 유지
- Citation 생성에 필요한 정보가 소실되지 않음

---

# Phase 07 — Document Ingestion Pipeline

## 목표

원본 문서를 Qdrant 검색 데이터로 만드는 전체 Pipeline을 연결한다.

## 처리 흐름

```text
MinIO
 ↓
Parser
 ↓
AI Validation
 ↓
Metadata / Token 계산
 ↓
Recursive Chunking
 ↓
Embedding
 ↓
Qdrant
```

## 구현

- `POST /internal/documents`
- MinIO 원본 조회
- Parser 선택
- Chunking
- Embedding
- Qdrant Point 저장
- 문서 처리 결과
- 실패 사유 표준화

## Qdrant Payload

최소:

```text
chunk_text
user_id
document_id
filename
page
chunk_id
```

선택:

```text
file_type
section
title
source
created_at
```

## 완료 조건

- PDF/TXT/MD 각각 Ingestion 성공
- Qdrant에서 document_id 기준 Point 확인 가능
- Parsing/Embedding/Qdrant 오류를 구분 가능
- 부분 실패가 성공으로 오인되지 않음

---

# Phase 08 — Document Delete & Status

## 목표

문서 처리 상태 조회와 Vector 삭제 경계를 구현한다.

## 구현

- `DELETE /internal/documents/{document_id}`
- `GET /internal/documents/{document_id}/status`
- Qdrant document_id Filter 기반 삭제
- 실패 결과 표준화

## 주의

Backend DB Transaction과 Qdrant/MinIO 처리는 하나의 Transaction이 아니다.

AI Server는 Backend의 문서 소유권 Source of Truth를 대체하지 않는다.

## 완료 조건

- document_id 범위 Vector 삭제 검증
- 존재하지 않는 문서 처리 검증
- 부분 실패를 호출자에게 식별 가능하게 전달

---

# Phase 09 — Vector Retrieval

## 목표

Agent 없이 순수 Retrieval을 먼저 완성한다.

## 구현

- Query Embedding
- Qdrant Vector Search
- `TOP_K`
- `SCORE_THRESHOLD`
- Metadata Filter
- Retrieval Result Model

## 필수 Filter

```text
user_id
document_id 또는 document_ids
```

## 검증

- 관련 Query 검색
- 무관 Query 검색
- Top-K
- Score Threshold
- user_id 격리
- document_id 격리

## 완료 조건

- 다른 user_id의 Chunk가 검색되지 않음
- Citation 생성에 필요한 Metadata가 Retrieval 결과에 포함됨

---

# Phase 10 — Agent 없는 RAG + Citation

## 목표

Agent Tool Calling을 도입하기 전에 순수 RAG 흐름을 완성한다.

## 흐름

```text
질문
 ↓
Retrieval
 ↓
RAG Context
 ↓
RAG Prompt
 ↓
LLM
 ↓
Answer
 +
Citation
```

## 구현

- RAG Answer Prompt
- Retrieval Context 구성
- 근거 부족 처리
- Citation 생성

## Citation

```text
document_id
filename
chunk_id
page
section
```

## 완료 조건

- 문서 근거 질문에 근거 기반 응답
- Citation이 실제 Retrieval Result에서만 생성됨
- 문서에 근거가 없을 때 임의 Citation을 생성하지 않음

---

# Phase 11 — Document Summary

## 목표

문서 크기에 따른 Summary 전략을 구현한다.

## 전략

### 작은 문서

```text
전체 문서
+
Summary Prompt
↓
LLM
```

### 큰 문서

```text
Chunk별 Summary
↓
부분 Summary 결합
↓
최종 Summary
```

## Python 판단

```text
token_count
llm_context_window
reserved_output_tokens
```

등을 기준으로 전략을 결정한다.

## 필수

- Direct Summary
- Map-Reduce / Hierarchical Summary

## 완료 조건

- 작은 문서 Direct Summary
- Context 초과 문서 Hierarchical Summary
- 전략 선택을 LLM에게 위임하지 않음

---

# Phase 12 — Query Rewrite

## 목표

멀티턴 후속 질문을 Retrieval용 독립 Query로 재작성한다.

## 구현

- Query Rewrite Prompt
- Conversation Context 입력
- 현재 질문 원문 보존
- Retrieval용 Rewrite 결과 분리

## 완료 조건

다음과 같은 대화에서:

```text
User: Qdrant가 뭐야?
Assistant: Vector DB입니다.
User: 그럼 장점은?
```

Retrieval Query가 문맥을 포함한 독립 질문으로 변환된다.

---

# Phase 13 — Context & Token Budget Manager

## 목표

LLM Context Window 초과를 규칙 기반으로 방지한다.

## 기본 Context

```text
Conversation Summary
+
최근 N개 Message
+
RAG Context
+
현재 질문
```

## 구현

- Token 계산
- Recent Message Sliding Window
- Conversation Summary 입력
- 오래된 History Summary 생성
- RAG Context Token 계산
- Output Token Reservation
- 최종 Token Budget 검증

## 완료 조건

- 전체 History 무조건 전달 금지
- Context 초과 상황에서도 예측 가능한 축소 정책 적용
- Output Token 공간을 사전 확보

---

# Phase 14 — Tool Layer

## 목표

이미 검증한 Service 기능을 Agent Tool로 노출한다.

## Tool

### AI Local Tool

```text
search_documents
summarize_document
```

### Backend Tool

```text
list_documents
```

## 원칙

Tool은 기능 자체를 새로 구현하는 장소가 아니다.

```text
Tool
 ↓
기존 Service / Backend Client
```

## AI-only 개발 단계의 list_documents 검증

실제 Backend가 아직 없으면 개발/테스트 전용 Mock 또는 Stub을 사용할 수 있다.

단:

- Production 기능으로 취급하지 않는다.
- Backend가 Source of Truth라는 경계를 변경하지 않는다.
- 실제 계약 형태를 대체하지 않는다.

## 완료 조건

- Tool Input Schema 명시
- Tool Output Schema 명시
- 사용자/문서 Scope 전달
- Tool Error 표준화

---

# Phase 15 — Agent Tool Calling

## 목표

LLM Agent가 질문 의미에 따라 Tool을 선택하도록 한다.

## 분기

```text
문서 검색 질문
→ search_documents

특정 문서 요약
→ summarize_document

문서 목록 질문
→ list_documents

문서와 무관한 일반 질문
→ No Tool → 최종 LLM Answer
```

## 제한

```text
MAX_AGENT_STEPS
MAX_TOOL_CALLS
```

## 완료 조건

최소 시나리오:

| 질문 유형 | 예상 동작 |
| --- | --- |
| 일반 상식 질문 | No Tool |
| 업로드 문서 내용 질문 | `search_documents` |
| 특정 문서 요약 | `summarize_document` |
| 등록 문서 목록 | `list_documents` |

무한 Tool Loop 방지 테스트를 포함한다.

---

# Phase 16 — Usage Aggregation

## 목표

여러 LLM 호출을 한 Agent Run 단위로 집계한다.

## 구현

- LLM Call Usage
- Agent Run Usage
- Call Type
- Provider
- Model
- Input/Output Token
- LLM Call Count
- Retrieval Chunk Count
- Latency
- Status

## 완료 조건

한 요청에서 Agent 판단, Query Rewrite, 최종 답변 등 여러 호출이 발생해도:

```text
개별 LLM Call Usage
+
Agent Run Total Usage
```

를 모두 확인할 수 있다.

---

# Phase 17 — WebSocket Event Model

## 목표

Streaming 전에 Event 계약과 실행 Trace를 구현한다.

## Event

```text
start
status
tool_start
tool_end
retrieval_start
retrieval_result
delta
citation
usage
done
error
cancelled
```

## 규칙

- 가능한 모든 Event에 `request_id`
- 내부 Chain-of-Thought 노출 금지
- 실제 Observable Execution Trace만 노출

## 완료 조건

Agent/RAG 실행을 Event Stream으로 변환할 수 있음

---

# Phase 18 — WebSocket Streaming

## 목표

AI 실행 상태와 최종 답변을 실시간 전달한다.

## Endpoint

```text
WS /internal/ws/chat
```

## 검증 흐름 예

```text
start
↓
status
↓
tool_start
↓
retrieval_start
↓
retrieval_result
↓
tool_end
↓
status
↓
delta ...
↓
citation
↓
usage
↓
done
```

## 완료 조건

- Text Delta Streaming
- Citation Event
- Usage Event
- 오류 시 Error Event
- request_id 유지

---

# Phase 19 — Stability

## 목표

외부 의존성 및 WebSocket 장애 상황을 검증한다.

## 구현/검증

- Client Disconnect
- Server Disconnect
- Heartbeat/Ping-Pong 확장 고려
- Idle Timeout
- Message Size 제한
- 비정상 Event 처리
- LLM Timeout
- Embedding Timeout
- Qdrant 오류
- MinIO 오류
- 제한적 Retry
- Agent Step/Tool Call Limit
- Request Cancel Protocol 기반

## 완료 조건

- 장애가 Stack Trace 그대로 노출되지 않음
- 중복 요청 위험을 식별할 수 있음
- 실패 요청이 `done`으로 잘못 종료되지 않음

---

# Phase 20 — Final AI Server Verification

## 목표

Backend 구현 시작 전에 AI Server 독립 검증을 완료한다.

## 필수 시나리오

### 문서

```text
MinIO 원본
↓
Parsing
↓
Chunking
↓
Embedding
↓
Qdrant 저장
```

### RAG

```text
질문
↓
Query Rewrite 필요 여부
↓
Retrieval
↓
Context
↓
Answer
↓
Citation
```

### Agent

```text
No Tool
search_documents
summarize_document
list_documents
```

### Streaming

```text
start
status
tool/retrieval events
delta
citation
usage
done
```

### 격리

```text
user A
≠
user B
```

Qdrant Metadata Filter를 검증한다.

### 오류

- Parsing 실패
- Embedding 실패
- Qdrant 실패
- LLM 실패
- WebSocket Disconnect
- Timeout

## 최종 완료 기준

CLI/curl/Test/WebSocket Client만으로 다음을 검증할 수 있어야 한다.

```text
문서 처리
+
Vector 저장
+
Retrieval
+
RAG
+
Citation
+
Summary
+
Multi-turn Rewrite
+
Context Budget
+
Agent Tool Calling
+
Usage
+
Streaming
+
오류 처리
```

이 단계가 완료되면 Spring Boot Backend 연결 단계로 진행한다.
