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
| 06 | Token Measurement & Recursive Chunking | NOT_STARTED | - |
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
Phase: 05
Status: VERIFIED
```

---

## 구현 완료

- 공통 `ParserInput`, `ContentUnit`, `NormalizedDocument` 내부 모델
- 확장자 기반 Parser 선택을 한 곳에 집중한 `ParserRegistry`
- 필수 포맷만 등록한 기본 Registry: `txt`, `md`, `pdf`
- TXT 원문 추출, 빈 문서 허용, 긴 Text 보존, 기본 Metadata 계산
- BOM 기반 UTF-8/UTF-16/UTF-32 및 BOM 없는 strict UTF-8 Encoding 정책
- MD 원문 보존과 단순 ATX Heading 기반 Section/Heading Level Metadata 추출
- PyMuPDF 기반 PDF Page별 Text 추출, 1-based Page Number 및 Page Count 유지
- 정상 PDF의 암호화 여부 Metadata와 암호화/손상/일반 Parsing 실패 오류 구분
- 공통 Character Count와 전체 `content` 결합 표현
- 민감 데이터가 없는 TXT/MD/PDF/다중 Page/손상/암호화 Fixture
- OCR, Chunking, Embedding 연결, Qdrant 저장, RAG는 구현하지 않음

---

## 검증

- Phase 04 문서/브랜치 상태 확인: `VERIFIED`, `main`과 Phase 04 완료 커밋 일치
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit/parsers -q`
  - Result: PASS (`26 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest tests/unit -q`
  - Result: PASS (`121 passed`)
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
  - Result: PASS (`127 passed, 8 skipped`; 기존 실제 Infrastructure/LLM/Embedding Test만 조건부 skip)
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

- Phase 05 요구 범위 내 미검증 항목 없음.
- 전체 Test의 조건부 skip 8개는 기존 외부 Infrastructure/LLM/Embedding 검증이며 Parser 계층과 무관함.
- 이미지 전용 PDF의 OCR, Chunking/Embedding/Qdrant/RAG 연결은 명시적인 제외 범위임.

---

## 변경 파일

- `.gitattributes`
- `pyproject.toml`
- `app/core/exceptions.py`
- `app/models/__init__.py`
- `app/models/document.py`
- `app/parsers/__init__.py`
- `app/parsers/base.py`
- `app/parsers/encoding.py`
- `app/parsers/markdown.py`
- `app/parsers/pdf.py`
- `app/parsers/registry.py`
- `app/parsers/text.py`
- `tests/fixtures/documents/sample.txt`
- `tests/fixtures/documents/empty.txt`
- `tests/fixtures/documents/sample.md`
- `tests/fixtures/documents/sample.pdf`
- `tests/fixtures/documents/multi_page.pdf`
- `tests/fixtures/documents/corrupted.pdf`
- `tests/fixtures/documents/encrypted.pdf`
- `tests/unit/parsers/__init__.py`
- `tests/unit/parsers/test_txt.py`
- `tests/unit/parsers/test_markdown.py`
- `tests/unit/parsers/test_pdf.py`
- `tests/unit/parsers/test_registry.py`
- `docs/FILE_STRUCTURE.md`
- `docs/PROGRESS.md`

---

## 다음 작업

- Phase 05 Parser Layer 검증 완료.
- `Phase 06 — Token Measurement & Recursive Chunking` 진행 가능.

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
