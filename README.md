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

## 핵심 기능

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

테스트와 정적 검사:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

`/ready`는 애플리케이션 설정, Qdrant 연결, MinIO 연결과 bucket 접근을 확인한다. 개발환경에서
`MINIO_AUTO_CREATE_BUCKET=true`이면 애플리케이션 시작 시 설정된 bucket 생성을 시도한다.
