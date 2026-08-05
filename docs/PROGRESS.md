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
| 01 | Project Skeleton | NOT_STARTED | - |
| 02 | Infrastructure Clients | NOT_STARTED | - |
| 03 | LLM Provider Abstraction | NOT_STARTED | - |
| 04 | Embedding Provider | NOT_STARTED | - |
| 05 | Parser Layer | NOT_STARTED | - |
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
Phase: 01
Status: NOT_STARTED
```

---

## 완료된 항목

없음.

---

## 현재 Blocker

없음.

---

## 미검증 항목

전체.

---

## 다음 작업

`docs/IMPLEMENTATION_SCOPE.md` 추가 후 `Phase 01 — Project Skeleton` 시작.

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
