# AI Server Progress

## 상태 규칙

상태 값:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
IMPLEMENTED
VERIFIED
```

의미:

- `NOT_STARTED`: 작업 시작 전
- `IN_PROGRESS`: 구현 중
- `BLOCKED`: 외부 의존/결정 문제로 진행 불가
- `IMPLEMENTED`: 코드 구현은 완료했으나 전체 검증 전
- `VERIFIED`: 해당 Phase의 요구 검증 완료

`IMPLEMENTED`를 `VERIFIED`와 동일하게 취급하지 않는다.

---

## 현재 진행상태

| Phase | 내용 | 상태 | 검증 |
| ---: | --- | --- | --- |
| 01 | Project Skeleton | VERIFIED | Unit/Integration 10 tests + curl 검증 통과 |
| 02 | Infrastructure Clients | VERIFIED | Docker Compose + 22 tests + `/ready` 검증 통과 |
| 03 | LLM Provider Abstraction | VERIFIED | OpenAI/Ollama/Gemini Unit·Regression + Ollama/Gemini 실제 검증 통과 |
| 04 | Embedding Provider | VERIFIED | OpenAI Embedding Unit·Regression + 실제 Qdrant Dimension 검증 통과 |
| 05 | Parser Layer | VERIFIED | TXT/MD/PDF fixture Unit 26 tests + 전체 Regression 통과 |
| 06 | Token Measurement & Recursive Chunking | VERIFIED | Token/Chunk/Metadata Unit 20 tests + 전체 Regression 통과 |
| 07 | Document Ingestion Pipeline | NOT_STARTED | - |
| 08 | Document Delete & Status | NOT_STARTED | - |
| 09 | Vector Retrieval | NOT_STARTED | - |
| 10 | Agent 없는 RAG + Citation | NOT_STARTED | - |
| 11 | Document Summary | NOT_STARTED | - |
| 12 | Query Rewrite | NOT_STARTED | - |
| 13 | Context & Token Budget Manager | NOT_STARTED | - |
| 14 | Tool Layer | NOT_STARTED | - |
| 15 | Agent Tool Calling | NOT_STARTED | - |
| 16 | Usage Aggregation | NOT_STARTED | - |
| 17 | WebSocket Event Model | NOT_STARTED | - |
| 18 | WebSocket Streaming | NOT_STARTED | - |
| 19 | Stability | NOT_STARTED | - |
| 20 | Final AI Server Verification | NOT_STARTED | - |

---

## 현재 Phase

```text
Phase: 06
Status: VERIFIED
```

---

## 구현 완료

- `Chunk`, `DocumentStatistics`, `ChunkingResult` 내부 모델
- 현재 기본 Embedding 모델 `text-embedding-3-small`과 일치하는 `tiktoken` BPE Token 계산
- `TOKENIZER_MODEL`과 선택적인 `TOKENIZER_ENCODING` 기반 Tokenizer 정책
- Token 단위 `CHUNK_SIZE`, `CHUNK_OVERLAP` 중앙 환경설정 및 유효성 검증
- LangChain `RecursiveCharacterTextSplitter` 기반 범용 Recursive Chunking
- `page_count`, `character_count`, `token_count`, `chunk_count` 문서 통계
- 결정적 UUID 기반 고유 `chunk_id`, 0-based `chunk_index`, 문서/파일 Metadata 유지
- PDF Page와 MD Section을 Citation 경계로 취급하고 Chunk/Overlap의 경계 횡단 금지
- TXT는 `chunk_id`와 `chunk_index`로 위치 및 순서 추적
- 빈 문서는 빈 Chunk 없이 `token_count=0`, `chunk_count=0` 처리
- Parser → Chunking → Token/Metadata JSON 출력 개발용 CLI
- Embedding 호출, Qdrant 저장, Ingestion API는 구현하지 않음

---

## 검증

- Phase 05 문서/커밋 상태 확인: `VERIFIED`, `main`과 Phase 05 완료 커밋 `acea2e8` 일치
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit/parsers -q`
  - Result: PASS (`26 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit/chunking tests/unit/test_config.py -q`
  - Result: PASS (`20 passed`)
- Command: `.\.venv\Scripts\python.exe -m scripts.inspect_chunking tests\fixtures\documents\multi_page.pdf`
  - Result: PASS (`page_count=3`, `token_count=9`, `chunk_count=3`, Page 1/2/3 Metadata 확인)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit -q`
  - Result: PASS (`136 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`142 passed, 8 skipped`; 기존 실제 Infrastructure/LLM/Embedding Test만 조건부 skip)
- Command: `.\.venv\Scripts\python.exe -m ruff check .`
  - Result: PASS
- Command: `.\.venv\Scripts\python.exe -m pip check`
  - Result: PASS (`No broken requirements found`)
- Command: `git diff --check`
  - Result: PASS

---

## 현재 Blocker

없음.

---

## 미검증 항목

- Phase 06 요구 범위 내 미검증 항목 없음.
- 전체 Test의 조건부 skip 8개는 기존 외부 Infrastructure/LLM/Embedding 검증이며 Phase 06과 무관함.
- Embedding/Qdrant 저장 및 Ingestion 연결은 후속 Phase의 명시적인 제외 범위임.

---

## 변경 파일

- `.env.example`
- `pyproject.toml`
- `app/chunking.py`
- `app/core/config.py`
- `app/models/__init__.py`
- `app/models/document.py`
- `app/services/__init__.py`
- `app/services/chunking.py`
- `scripts/inspect_chunking.py`
- `tests/unit/chunking/__init__.py`
- `tests/unit/chunking/test_recursive.py`
- `tests/unit/test_config.py`
- `docs/FILE_STRUCTURE.md`
- `docs/PROGRESS.md`
- `docs/TESTING.md`

---

## 다음 작업

- Phase 06 Token Measurement & Recursive Chunking 검증 완료.
- `Phase 07 — Document Ingestion Pipeline` 진행 가능.

---

# Progress Update Template

Phase 완료/진행 시 아래 형식으로 갱신한다.

```markdown
## 현재 Phase

Phase: XX
Status: IN_PROGRESS | IMPLEMENTED | VERIFIED | BLOCKED

## 구현 완료

- ...
- ...

## 검증

- Command: `...`
  - Result: PASS
- Command: `...`
  - Result: PASS

## 실패/미검증

- ...

## 변경 파일

- `...`

## 다음 작업

- ...
```

검증하지 않은 항목을 임의로 `VERIFIED`로 표시하지 않는다.
