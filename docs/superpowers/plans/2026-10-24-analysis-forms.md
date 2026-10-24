# 대화 정리 양식 개편 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 일반 회의·요구사항 협의·검토와 결정·진행 점검·사용자 인터뷰의 출력 구조와 화면을 실제로 구분한다.
**Architecture:** 새 분석은 양식별로 허용된 제목의 섹션을 생성한다. 섹션은 주제별 문단, 선택지 비교, 후속 조치를 담는다. 기존 AnalysisBody는 저장 결과 읽기 호환으로 유지하고 새 FormAnalysisBody와 구분한다. 분할 입력의 결과는 순서를 보존하며 두 개씩 모델로 통합하고, 모든 단계의 근거·기한·담당자를 검증한다.
**Tech Stack:** 기존 Python/Pydantic/FastAPI, React/TypeScript, Ollama/OpenAI. 의존성 추가 없음.
**Spec:** 사용자가 승인한 직전 대화의 다섯 양식·출력 순서·누락 처리 규칙. 채용 면접 제외.

## Global Constraints

- 녹음과 기존 분석을 덮어쓰지 않는다. 기존 meeting/project/interview ID를 유지하고 decision/progress를 추가한다.
- 프로젝트 양식의 목표·예산·일정이 언급되지 않았으면 최종 결과에서만 빈 섹션으로 보존해 언급 없음으로 표시한다. 다른 빈 항목은 숨긴다.
- 문장 ID 근거는 유지하며 기본 화면에 시간·근거 버튼을 노출하지 않는다.
- 제안·희망·확정·보류·철회를 구별하고 외부 지식으로 채우지 않는다. 생성 제안 기능은 추가하지 않는다.
- 담당자의 발언자 ID와 원문에 나온 외부 담당자 이름을 지원한다. 기한은 근거 본문의 표현만 허용한다.
- 양식 선택만으로 실행하지 않으며 정리 시작 또는 재정리 때 새 분석을 만든다.
- JSON은 새 분석 구조가 포함된 경우 schema_version 3, 기존 구조와 전사만 내보내기는 2를 유지한다.

## Review Focus

- 저장된 구버전 분석·Markdown 내보내기가 새 형식 때문에 깨지지 않는다.
- 구간 통합 단계에도 근거·기한 검증과 재시도가 적용되고 후반부 변경·철회가 전달된다.
- 일부 구간에서 예산이 없더라도 다른 구간의 예산을 언급 없음으로 덮지 않는다.
- 임의 섹션·비교표·담당자를 허용하지 않고 HTML 문자열을 실행하지 않는다.
- 새로운 두 양식이 API·큐·워커·결과·내보내기까지 보존된다.

### Task 1: 양식 계약·모델 생성·검증·내보내기

**Files:** backend/src/meetinglog/domain.py, analysis/forms.py, analysis/prompts.py, analysis/service.py, analysis/grounding.py, engines/local_analysis.py, engines/cloud_analysis.py, exports.py, tests/analysis_fixtures.py, tests/test_analysis.py, tests/test_analysis_forms.py, tests/test_exports.py, tests/test_grounding.py.
**Interfaces:** FormAnalysisBody.sections; AnalysisSection(title, groups, comparisons, actions); ParagraphGroup(title, paragraphs); OptionComparison(option, points); FormAction extends Action with owner_text. AnalysisVersion.body는 새 형식과 기존 형식의 union. 엔진 generate와 merge는 새 형식만 생성한다. canonicalize(body, form)는 섹션 정렬·빈 항목 제거·필수 누락 항목 보존을 맡는다.

- [x] 실제 요청 경계와 저장 호환성·잘못된 근거·기한·새 양식 전달·통합·필수 누락을 검사하는 테스트를 작성해 실패를 확인한다.
- [x] 계약·양식 정의·프롬프트·엔진·통합·내보내기를 구현하고 백엔드 검사를 통과한다.

### Task 2: 양식 선택·결과 표시·회귀 검증

**Files:** web/src/lib/schema.d.ts, web/src/features/detail/AnalysisPane.tsx, AnalysisFormDialog.tsx, web/src/test/detail.tsx, web/src/features/detail/RecordingDetail.test.tsx, tests/e2e_server.py, web/e2e/recording.spec.ts, web/src/styles.css, README.md.
**Interfaces:** 기존 분석은 기존 화면, 새 분석은 저장된 섹션 순서·문단·비교표·후속 조치를 표시한다. 빈 섹션은 언급 없음. FormOption.sections는 양식 선택 시 출력 항목을 미리 보여준다.

- [x] 화면·구버전 읽기·비교표·근거 숨김·누락 표시·양식 선택 후 실행을 검사하는 테스트를 작성해 실패를 확인한다.
- [x] UI·스키마·브라우저 fixture·README를 갱신하고 전체 검사와 데스크톱·모바일 화면을 확인한다.
- [x] 전체 변경을 독립 리뷰하고 필요한 회귀 수정 후 원래 작업 폴더에 반영한다.

## 검증 결과

- 전체 검사: Python 128개, 웹 37개, 브라우저 6개 테스트와 lint·형식·타입·빌드 통과. 마지막 프롬프트 변경 뒤 Python 128개를 다시 확인했다.
- 독립 리뷰에서 발견한 통합 근거 범위와 Markdown 문단 구분 문제를 재현 테스트로 확인하고 수정했다. 빈 후속 조치도 재시도 대상으로 검증한다.
- gpt-oss:20b는 추론이 출력 한도를 모두 사용하는 사례가 있어 think=low를 지정했다. 다른 모델에는 이 설정을 보내지 않는다. 참고: https://docs.ollama.com/capabilities/thinking
- 가상 발언 7개로 실제 로컬 모델을 확인했다. 마지막 실행에서 요구사항 협의 17.4초, 검토와 결정 16.8초. 명시된 후속 조치·외부 담당자·기한, 결정 결과·비교표를 확인했다. 이 수치는 장시간 녹음의 성능 지표가 아니다.
- 모델의 의미 해석과 누락 방지를 보장하지 않는다. 초기 실행에서 후속 조치 누락과 담당자 오배정이 있었고 지시를 보강했다. 실제 장시간 녹음과 외부 분석 API는 이번에 실행하지 않았다.
