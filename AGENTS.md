# AGENTS.md

## Project

Python 3.12 + FastAPI 기반 Agentic RAG AI Server.

최종 요구사항:
- `docs/IMPLEMENTATION_SCOPE.md`

구현 순서:
- `docs/DEVELOPMENT_PLAN.md`

설계:
- `docs/ARCHITECTURE.md`

Contract:
- `docs/CONTRACTS.md`

테스트:
- `docs/TESTING.md`

진행상태:
- `docs/PROGRESS.md`

---

## Document Priority

충돌 시 다음 순서를 따른다.

1. 사용자의 현재 지시
2. `IMPLEMENTATION_SCOPE.md`
3. `AGENTS.md`
4. `CONTRACTS.md`
5. `ARCHITECTURE.md`
6. `DEVELOPMENT_PLAN.md`

요구사항이 불명확하면 임의로 범위를 확장하지 않는다.

---

## Scope

현재 저장소는 AI Server만 구현한다.

최종 구조:

Frontend
↕
Spring Boot Backend
↕
FastAPI AI Server

AI Server는 다음의 Source of Truth가 아니다.

- 사용자
- 인증
- Role/권한
- 대화 원본
- 문서 소유권
- Billing

Backend 책임을 AI Server에 구현하지 않는다.

---

## Core Stack

- Python 3.12
- FastAPI
- LangChain Tool Calling
- PyMuPDF
- Recursive Chunking
- Qdrant
- MinIO
- External LLM API
- External Embedding API
- WebSocket

확정 기술을 임의로 교체하지 않는다.

---

## Development Rules

1. 사용자가 지정한 Phase만 구현한다.
2. 다음 Phase를 선행 구현하지 않는다.
3. `IMPLEMENTATION_SCOPE.md`에 없는 기능을 임의로 추가하지 않는다.
4. 기능을 구현한 뒤 반드시 테스트한다.
5. 테스트하지 않은 기능을 완료로 표시하지 않는다.
6. 환경값과 Secret을 하드코딩하지 않는다.
7. Provider/외부 시스템은 Adapter/Interface 경계를 유지한다.
8. Tool에서 기존 Service 기능을 중복 구현하지 않는다.
9. Prompt를 Service 코드 전체에 분산시키지 않는다.
10. Contract를 임의 변경하지 않는다.

---

## Do Not Implement Unless Requested

- OCR
- Queue
- Reranker
- Hybrid Search
- Semantic Chunking
- Multi-Agent
- Web Search
- SQL Agent
- 추가 문서 포맷
- Billing
- SSO
- Kubernetes

확장 가능성만 고려하고 실제 구현하지 않는다.

---

## Security

금지:

- API Key 하드코딩
- Secret 로그 출력
- System Prompt 노출
- Chain-of-Thought 노출
- Stack Trace 외부 반환
- 다른 사용자의 Qdrant 데이터 검색

Qdrant Retrieval에는 사용자 Scope Filter를 유지한다.

---

## Agent

초기 Tool:

- `search_documents`
- `summarize_document`
- `list_documents`

일반 질문은 필요하지 않으면 Tool을 호출하지 않는다.

반드시 다음 제한을 유지한다.

- `MAX_AGENT_STEPS`
- `MAX_TOOL_CALLS`

---

## Testing

작업 후 `docs/TESTING.md`에 따라 관련 테스트를 실행한다.

기본 순서:

구현
→ Unit Test
→ Integration Test
→ 필요한 경우 CLI/curl/WebSocket 검증

외부 API Key나 Infrastructure 부족으로 실행하지 못한 테스트는
실행한 것처럼 보고하지 않는다.

---

## Progress

작업 완료 후 `docs/PROGRESS.md`를 갱신한다.

상태:

- NOT_STARTED
- IN_PROGRESS
- BLOCKED
- IMPLEMENTED
- VERIFIED

테스트가 완료되지 않았다면 `VERIFIED`를 사용하지 않는다.

---

## Completion Report

작업 종료 시 다음을 보고한다.

- 구현 내용
- 수정/추가 파일
- 실행한 테스트
- 테스트 결과
- 미검증 항목
- 남은 문제
- 다음 Phase 진행 가능 여부

범위를 넘어서는 대규모 변경이 필요하면 임의로 수행하지 않는다.