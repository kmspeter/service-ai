# Architecture Decisions

이 문서는 `IMPLEMENTATION_SCOPE.md`에 이미 확정된 설계 결정을 짧게 모아 Codex가 구현 중 재검토하거나 임의 변경하지 않도록 한다.

새로운 결정이 필요한 경우 기존 결정을 수정하기보다 새 항목을 추가하고 영향 범위를 기록한다.

---

## D001 — 시스템은 3계층 구조를 사용한다

**Decision**

```text
Frontend
↕
Backend
↕
AI Server
```

Frontend가 AI Server에 직접 접근하지 않는다.

---

## D002 — 현재 저장소의 책임은 AI Server다

**Decision**

AI Server는 AI/RAG 처리에 집중한다.

**Backend Source of Truth**

- 회원
- 로그인
- Role
- 권한
- 사용자 대화 원본
- 문서 소유권
- Billing

AI Server에 이 데이터의 별도 Source of Truth를 만들지 않는다.

---

## D003 — FastAPI를 사용한다

**Decision**

Python 3.12 + FastAPI.

---

## D004 — 원본 문서는 MinIO에 저장한다

**Decision**

개발환경에서 Docker Compose 기반 MinIO를 원본 문서 저장소로 사용한다.

Qdrant에 원본 파일을 저장하지 않는다.

---

## D005 — Vector DB는 Qdrant다

**Decision**

Qdrant는 Chunk/Vector/Retrieval Metadata 저장 및 Vector Search 전용이다.

---

## D006 — 문서 기본 지원 형식은 PDF/TXT/MD다

**Decision**

초기 필수:

```text
PDF
TXT
MD
```

다른 문서 형식과 OCR은 추후 확장이다.

---

## D007 — Parser Registry를 사용한다

**Decision**

포맷별 Parser가 Service 전체에 분산되지 않도록 Registry 경계를 둔다.

---

## D008 — Chunking은 Recursive 방식이다

**Decision**

초기 기본은 Recursive Chunking.

설정:

```text
CHUNK_SIZE
CHUNK_OVERLAP
```

Semantic/Structure-aware/Parent-Child는 초기 구현에 포함하지 않는다.

---

## D009 — RAG 대상 문서는 기본적으로 Embedding한다

**Decision**

Chunk별 Embedding을 생성하고 Qdrant에 저장한다.

Embedding Model 이름은 설정값으로 관리한다.

---

## D010 — 문서 크기 판단은 Python 규칙이다

**Decision**

LLM이 문서 크기/Context 초과 여부를 판단하지 않는다.

사용:

```text
page_count
character_count
token_count
chunk_count
llm_context_window
reserved_output_tokens
history_tokens
rag_context_tokens
```

---

## D011 — Summary는 Direct + Hierarchical을 구현한다

**Decision**

작은 문서:

```text
Direct Summary
```

큰 문서:

```text
Map-Reduce / Hierarchical Summary
```

전략 선택은 Python Token 규칙이다.

---

## D012 — 초기 Agent Tool은 3개다

**Decision**

```text
search_documents
summarize_document
list_documents
```

추가 Tool은 초기 필수 범위가 아니다.

---

## D013 — Tool 실행 경계를 분리한다

**Decision**

```text
AI Local Tool
├─ search_documents
└─ summarize_document

Backend Tool
└─ list_documents
```

Backend 데이터는 Backend Internal API를 통해 조회한다.

---

## D014 — 일반 질문은 No Tool이다

**Decision**

문서와 무관한 일반 질문은 불필요한 Qdrant Search/Tool 호출 없이 LLM이 최종 답변을 생성한다.

---

## D015 — Agent Loop를 제한한다

**Decision**

```text
MAX_AGENT_STEPS
MAX_TOOL_CALLS
```

를 적용한다.

---

## D016 — Query Rewrite는 Retrieval 전용이다

**Decision**

후속 질문을 독립 Query로 재작성할 수 있으나 사용자 원문 Message를 덮어쓰지 않는다.

---

## D017 — 전체 대화 History를 매번 전달하지 않는다

**Decision**

```text
Conversation Summary
+
최근 N개 Message
+
RAG Context
+
현재 질문
```

구조를 기본으로 한다.

---

## D018 — Citation은 Retrieval 결과에서 생성한다

**Decision**

Citation 기본:

```text
document_id
filename
chunk_id
page
section
```

실제 검색 근거가 없는 Citation은 생성하지 않는다.

Phase 10에서는 실제 LLM Context에 포함된 Retrieval Result만 Citation Source로 사용한다.
동일한 `(document_id, filename, chunk_id, page, section)` Citation은 검색 순서를 유지하며 한 번만 반환한다.
LLM이 답변 본문에 생성한 Citation 형태 문자열은 Application Citation으로 채택하지 않는다.

---

## D019 — Chat Streaming은 WebSocket이다

**Decision**

최종 경로:

```text
Frontend ↔ Backend ↔ AI Server
```

AI Server Internal WebSocket:

```text
/internal/ws/chat
```

---

## D020 — Observable Execution Trace만 노출한다

**Decision**

노출:

- Agent 상태
- Tool 상태
- Query Rewrite 여부
- Retrieval 상태
- 검색 결과 수
- Summary 상태
- 답변 생성 상태

금지:

- Chain-of-Thought
- System Prompt
- API Key
- Stack Trace
- 보안 내부 Metadata

---

## D021 — Usage는 Run과 Call을 분리한다

**Decision**

```text
Agent Run Usage
LLM Call Usage
```

Provider별 응답을 공통 모델로 정규화한다.

---

## D022 — Qdrant 검색에 user_id Filter를 적용한다

**Decision**

Backend 권한 검증과 별개로 AI Server에서도 `user_id` Filter를 적용한다.

Defense in Depth 원칙이다.

---

## D023 — Backend DB와 AI 작업은 단일 Transaction이 아니다

**Decision**

상태 기반 처리:

```text
PROCESSING
→ COMPLETED
→ FAILED
```

부분 실패를 고려한다.

---

## D024 — 초기 문서 처리는 단순하게 시작한다

**Decision**

Queue 기반 Background Worker는 초기 필수가 아니다.

향후 Queue로 확장 가능한 Service 경계만 유지한다.

---

## D025 — Prompt를 분리 관리한다

**Decision**

분리 대상:

```text
Agent
RAG Answer
Summary
Query Rewrite
Conversation Summary
```

---

## D026 — Secret을 하드코딩하지 않는다

**Decision**

환경변수/설정 계층을 사용한다.

로그에도 Secret을 남기지 않는다.

---

## D027 — 외부 의존 호출에 Timeout을 둔다

**Decision**

Retry는 무조건 적용하지 않는다.

오류 유형별 정책을 사용한다.

---

## D028 — request_id로 전 구간 요청을 추적한다

**Decision**

REST Header/DTO와 WebSocket Event에서 가능한 한 동일한 `request_id`를 유지한다.

향후 OpenTelemetry로 확장 가능하게 한다.

---

## D029 — Health와 Readiness를 분리한다

**Decision**

```text
/health
/ready
```

를 제공한다.

---

## D030 — AI Server Internal Endpoint는 일반 사용자용이 아니다

**Decision**

Private Network/Internal Credential/mTLS/Gateway 등으로 보호 가능한 구조를 유지한다.

구현 초기 복잡도에 맞는 방식을 선택하되 인터넷에 무제한 노출되는 구조는 피한다.

---

## D031 — Retrieval 기본값은 설정에서 관리하고 내부 요청 Override를 허용한다

**Decision**

`TOP_K`, `SCORE_THRESHOLD`는 설정 계층의 기본값을 사용한다.

내부 Service와 개발 검증은 요청별 Override를 허용하되 설정과 동일한 범위 검증을 적용한다.
모든 검색은 `user_id`를 필수 Filter로 사용하며 문서 범위가 지정된 경우에만
`document_id` 또는 `document_ids` Filter를 추가한다.

---

## D032 — Qdrant Point ID는 사용자 범위를 포함한 결정적 UUID다

**Decision**

Qdrant Point의 `id`와 payload의 `chunk_id`에는 같은 UUID5 문자열을 사용한다.
UUID5 입력은 길이로 구분한 `user_id + document_id + chunk_index` 조합으로 구성한다.

같은 사용자의 같은 문서를 같은 Chunk 설정으로 재처리하면 ID가 유지되고,
서로 다른 사용자가 같은 `document_id`를 사용해도 Point ID가 충돌하지 않는다.

---

## D033 — Application 조립과 Lifecycle은 Container에서 관리한다

**Decision**

`ApplicationContainer`가 현재 Phase의 Service와 Infrastructure Resource를 조립한다. FastAPI
`lifespan`은 Container의 `start()`/`close()`만 호출한다. Container가 직접 생성한 의존성만 닫고,
테스트나 수동 실행에서 주입한 의존성은 호출자가 소유한다.

Phase 14 이후 Tool/Agent/WebSocket Service도 같은 Composition Root에 추가한다. API, Tool 또는
Service 내부에서 외부 SDK Client를 임의 생성하지 않는다.

---

## D034 — REST request_id는 Header와 Contract 값이 하나여야 한다

**Decision**

`X-Request-ID`가 없으면 POST body 또는 query의 `request_id`를 요청 Context, 로그, 응답 body와
응답 헤더에 사용한다. 헤더가 있으면 계약 값과 정확히 일치해야 하며, 불일치는
`REQUEST_ID_MISMATCH` 422로 거부한다.

---

## D035 — Readiness는 현재 노출한 Application 기능까지 확인한다

**Decision**

`/ready`는 Qdrant/MinIO 연결만으로 준비 완료를 선언하지 않는다. 기본 설정에서는 문서 처리에 필요한
설정과 Ingestion/Management Service 조립 여부도 확인한다. 의도적으로 해당 기능을 제외한 배포만
`READINESS_REQUIRE_DOCUMENT_PROCESSING=false`를 사용한다.

---

## D036 — 품질 저하 Fallback은 예상된 Application 오류에만 적용한다

**Decision**

Query Rewrite와 Conversation Summary는 Provider/검증 등 표준 `ApplicationError`에 대해서만 원래
질의/기존 요약으로 fallback하고, `request_id`, `operation`, `status=fallback`, `error_code`를
구조화 로그로 남긴다. 프로그래밍 오류를 포함한 예상 밖 예외는 숨기지 않고 전파한다.

---

## D037 — Provider 중립 모델과 Port를 분리한다

**Decision**

LLM/Embedding Request, Result, Usage는 `app/models/`에 둔다. `app/ports/`는 Protocol과 외부 경계에
필요한 최소 DTO만 가지며, Runtime 기능과 Collection/Bucket 관리 기능은 별도 Protocol로 분리한다.
