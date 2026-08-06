# Agentic RAG AI Server

`Frontend ↔ Backend ↔ AI Server` 3계층 구조에서 AI/RAG 처리를 담당하는 Python FastAPI 서버다.

이 저장소는 우선 **AI Server를 독립적으로 구현·검증**한 뒤 Spring Boot Backend와 연결하는 흐름을 전제로 한다.

---

## 기술 스택

- Python 3.12
- FastAPI
- LangChain Tool Calling
- PyMuPDF
- Recursive Chunking
- Qdrant
- MinIO
- OpenAI API / Ollama Cloud 등 외부 LLM API
- 외부 Embedding API
- WebSocket

---

## 현재 구현 범위 (Phase 01~13)

- PDF/TXT/MD Parsing
- Recursive Chunking
- Embedding
- Qdrant Vector 저장/검색
- 사용자/문서 Metadata Filtering
- RAG
- Citation
- Document Summary
- Query Rewrite
- Multi-turn Context 관리
- Health/Readiness와 문서 처리 Internal REST

Phase 14~20에서 구현할 항목:

- Agent Tool Calling
- LLM/Agent Usage 측정
- Observable Execution Trace
- WebSocket Streaming
- 표준 오류 Event

---

## 문서 구조

```text
AGENTS.md
README.md

docs/
├─ IMPLEMENTATION_SCOPE.md   # 사용자가 별도 추가
├─ DEVELOPMENT_PLAN.md
├─ ARCHITECTURE.md
├─ CONTRACTS.md
├─ TESTING.md
├─ DECISIONS.md
├─ FILE_STRUCTURE.md
└─ PROGRESS.md
```

### 문서 역할

| 문서 | 역할 |
| --- | --- |
| `IMPLEMENTATION_SCOPE.md` | 최종 요구사항 / Source of Truth |
| `AGENTS.md` | Codex 작업 규칙 |
| `DEVELOPMENT_PLAN.md` | 구현 순서와 Phase 완료 조건 |
| `ARCHITECTURE.md` | AI Server 내부 구조와 의존 방향 |
| `CONTRACTS.md` | DTO / Event / Tool / Internal API 계약 |
| `TESTING.md` | Unit / Integration / CLI 검증 정책 |
| `DECISIONS.md` | 확정 설계 결정 기록 |
| `PROGRESS.md` | 구현 진행 상태 |
| `FILE_STRUCTURE.md` | 현재 파일 구조와 계층별 책임 |

---

## 최종 시스템 경계

```text
React + Vite + MUI
        ↕ REST / WebSocket
Spring Boot Backend
        ↕ Internal REST / WebSocket
FastAPI AI Server
        ↕
Qdrant / MinIO / LLM / Embedding API
```

AI Server는 인증/회원/권한/문서 소유권/대화 원본 데이터의 Source of Truth가 아니다.

---

## 개발 방식

기능을 한 번에 완성하지 않고 `docs/DEVELOPMENT_PLAN.md`의 Phase 순서대로 구현한다.

기본 원칙:

```text
구현
↓
Unit Test
↓
Integration Test
↓
CLI / curl / WebSocket Client 검증
↓
Phase 완료
```

Backend를 구현하기 전까지 AI Server가 독립적으로 검증 가능한 영역은 CLI, 테스트 코드, curl, WebSocket Client 등을 사용한다.

Backend가 필요한 경계는 실제 Backend 계약을 침범하지 않는 개발용 Mock/Fixture로만 대체할 수 있다.

---

## Embedding Provider

현재 기본 Embedding Provider는 DeepInfra의 OpenAI 호환 Embeddings API이며,
`Qwen/Qwen3-Embedding-8B`의 Vector Dimension은 4096이다.

```text
EMBEDDING_PROVIDER=deepinfra
DEEPINFRA_API_KEY=<로컬 환경에만 설정>
DEEPINFRA_BASE_URL=https://api.deepinfra.com/v1/openai
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
```

Provider별 API Key는 서로 덮어쓰지 않고 로컬 환경에만 보관한다. `LLM_PROVIDER`와
`EMBEDDING_PROVIDER`가 활성 Key를 선택하며, 실제 모델명은 각각 `LLM_MODEL`과
`EMBEDDING_MODEL`에서 결정한다. 기존 Hugging Face/OpenAI 경로도 선택지로 유지한다.

Embedding Dimension이 바뀌면 기존 Qdrant Collection을 재사용하지 않고 새 Collection을
사용해야 한다.

---

## 개발 시작 전

1. `.env.example` 기준 개발 환경값 준비
2. Python 3.12 가상환경 구성
3. 의존성 설치
4. `docs/DEVELOPMENT_PLAN.md`의 Phase 순서대로 진행

Windows PowerShell 기준 실행 방법:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
# .env에서 로컬 개발 Credential 설정
docker compose up -d
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

서버 확인:

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/ready
```

문서 처리 요청은 Backend 전용 Internal Endpoint로만 제공한다.

```powershell
curl.exe -X POST http://localhost:8000/internal/documents `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: req-001" `
  -d '{"request_id":"req-001","user_id":"user-123","document_id":"doc-001","storage_key":"documents/doc-001/source.pdf"}'
```

`X-Request-ID`를 전달하면 body/query의 `request_id`와 같아야 한다. 헤더가 없으면 body/query 값을
요청 Context, 구조화 로그, 응답 헤더에 사용한다. 값이 다르면 HTTP 422와
`REQUEST_ID_MISMATCH`를 반환한다.

처리 성공은 `COMPLETED`, 단계별 실패는 `FAILED`와 표준 `failure_reason`으로 반환한다.
`user_id`는 일반 사용자 입력이 아니라 Backend가 검증해 전달한 실행 Context여야 한다.

Vector 삭제와 AI 처리 상태 조회도 Backend 전용이며, body가 없는 요청의 실행 Context는 query로 전달한다.

```powershell
curl.exe -X DELETE "http://localhost:8000/internal/documents/doc-001?request_id=req-delete-001&user_id=user-123"
curl.exe "http://localhost:8000/internal/documents/doc-001/status?request_id=req-status-001&user_id=user-123"
```

삭제는 `user_id + document_id`가 모두 일치하는 Qdrant Vector만 제거한다. Backend Metadata와 MinIO
원본은 변경하지 않으며, Qdrant 실패는 재처리 가능한 실패 결과로 반환한다.

Agent 없는 Dense Vector Retrieval은 내부 `RetrievalService`로 제공한다. 기본 검색 수와 점수 기준은
환경설정에서 관리하며 모든 검색에 Backend 검증 `user_id` Filter를 강제한다.

```text
TOP_K=5
SCORE_THRESHOLD=0.5
```

개발 Collection의 검색 결과와 Citation용 Metadata는 수동 실행 스크립트로 직접 확인할 수 있다.
각 파일 상단의 대문자 변수만 수정하고 저장소 루트에서 `.py`를 실행한다. Secret과 Provider 설정은
코드에 쓰지 않고 `.env`에 둔다.

```powershell
.\.venv\Scripts\python.exe scripts\manual_chunking.py
.\.venv\Scripts\python.exe scripts\manual_ingestion.py
.\.venv\Scripts\python.exe scripts\manual_retrieval.py
.\.venv\Scripts\python.exe scripts\manual_rag.py
.\.venv\Scripts\python.exe scripts\manual_summary.py
.\.venv\Scripts\python.exe scripts\manual_llm.py
```

Agent 없는 순수 RAG는 Retrieval 결과를 token 상한 내 JSON Context로 구성하고, 전용 RAG Prompt로
LLM 답변을 생성한다. Citation은 LLM 문자열이 아니라 실제 Context에 포함된 Retrieval Result에서
애플리케이션이 생성한다. 검색 결과가 없으면 LLM을 호출하지 않고 근거 부족 응답과 빈 Citation을 반환한다.

```text
MAX_CONTEXT_TOKENS=12000
```

테스트와 정적 검사:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
```

`/health`는 프로세스 생존만 확인한다. `/ready`는 필수 Infrastructure 설정, Qdrant 연결, MinIO 연결과
bucket 접근, 현재 노출된 문서 처리 서비스의 조립 및 필수 Embedding 설정을 모두 확인한다. 운영상 문서
처리 기능 없이 서버를 준비 상태로 둘 필요가 있을 때만 `READINESS_REQUIRE_DOCUMENT_PROCESSING=false`를
명시한다. 개발환경에서 `MINIO_AUTO_CREATE_BUCKET=true`이면 시작 시 설정된 bucket 생성을 시도한다.
