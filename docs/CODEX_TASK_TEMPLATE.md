# Codex Task Template

Codex에 Phase별 작업을 지시할 때 사용할 템플릿이다.

---

## 기본 템플릿

```text
AGENTS.md와 docs/IMPLEMENTATION_SCOPE.md를 먼저 읽어라.

현재 작업:
docs/DEVELOPMENT_PLAN.md의 Phase XX를 구현한다.

반드시 확인:
- docs/ARCHITECTURE.md
- docs/CONTRACTS.md
- docs/TESTING.md
- docs/DECISIONS.md
- docs/PROGRESS.md

규칙:
1. Phase XX 범위만 구현한다.
2. 다음 Phase를 선행 구현하지 않는다.
3. IMPLEMENTATION_SCOPE.md에 없는 기능을 추가하지 않는다.
4. Backend/Frontend 책임을 AI Server에 구현하지 않는다.
5. 기존 Contract를 임의로 변경하지 않는다.
6. 환경값과 Secret을 하드코딩하지 않는다.
7. 구현 후 해당 Phase의 Unit/Integration/수동 검증을 수행한다.
8. 테스트 실패가 있으면 원인을 수정한 후 다시 검증한다.
9. 실제 외부 Provider/Infra 부족으로 검증하지 못한 항목은 명확히 구분한다.
10. 작업 후 docs/PROGRESS.md를 실제 검증 결과에 맞게 갱신한다.

완료 보고:
- 구현한 내용
- 수정/추가 파일
- 실행한 테스트 명령
- 테스트 결과
- 미검증 항목
- 발견한 문제
- 다음 Phase 진입 가능 여부

Phase XX 외의 대규모 리팩터링이 필요해 보이면 임의 수행하지 말고 이유와 영향 범위를 먼저 설명한다.
```

---

## Phase 01 예시

```text
AGENTS.md와 docs/IMPLEMENTATION_SCOPE.md를 먼저 읽어라.

docs/DEVELOPMENT_PLAN.md의
"Phase 01 — Project Skeleton"만 구현한다.

Phase 02 이상의 기능은 구현하지 마라.

구현 후 docs/TESTING.md에 따라 가능한 테스트를 실행하고,
실제 검증 결과만 docs/PROGRESS.md에 반영해라.

마지막에는 다음을 보고해라.

1. 구현 내용
2. 생성/수정 파일
3. 테스트 명령과 결과
4. 남아있는 오류 또는 미검증
5. Phase 02 진입 가능 여부
```

---

## 버그 수정 템플릿

```text
AGENTS.md와 현재 관련 문서를 먼저 읽어라.

문제:
<증상>

기대 동작:
<기대 결과>

재현:
<명령/요청/테스트>

요구:
- 원인을 먼저 찾는다.
- 범위와 무관한 리팩터링은 하지 않는다.
- 수정 전후 동작 차이를 테스트로 증명한다.
- Contract 변경이 필요하면 임의 변경하지 말고 영향부터 보고한다.
- 수정 후 관련 테스트를 실행한다.
- 필요하면 PROGRESS.md의 Blocker/검증 상태를 갱신한다.
```

---

## 검증 전용 템플릿

```text
코드는 수정하지 말고 현재 Phase 구현을 검증해라.

기준:
- docs/IMPLEMENTATION_SCOPE.md
- docs/DEVELOPMENT_PLAN.md
- docs/CONTRACTS.md
- docs/TESTING.md

확인:
1. 요구사항 누락
2. 범위 밖 구현
3. Contract 위반
4. 사용자/문서 Scope 누락
5. Secret/로그 문제
6. 테스트 누락
7. 오류 처리 누락
8. 다음 Phase와 잘못 결합된 부분

결과는 중요도 순으로 정리하고,
각 문제에 파일/위치/근거/수정 방향을 제시해라.
코드 수정은 하지 마라.
```
