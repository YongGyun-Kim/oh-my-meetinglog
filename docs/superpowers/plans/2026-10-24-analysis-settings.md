# 대화 분석 모델 설정 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 웹에서 분석 도구·모델·추론 수준을 저장하고 다음 분석에 적용한다.
**Architecture:** settings 테이블에 분석 설정을 별도 저장한다. 워커는 분석 시작 때 설정을 한 번 읽어 StageRequest에 고정하고, 분석 엔진은 같은 양식·근거 검증 경로를 사용한다. CLI는 빈 임시 폴더에서 도구·사용자 확장 없이 실행한다.
**Tech Stack:** 기존 Python/Pydantic/FastAPI/React, subprocess. 새 의존성 없음.
**Spec:** 대화에서 승인한 전사와 분석 설정 분리, 웹 기본값 저장, Codex·Claude Code 계정 사용과 모델·추론 선택.

## Global Constraints

- Ollama·Codex·Claude Code·기존 OpenAI API를 지원한다. 기존 설정이 없으면 기존 mode/환경변수 동작을 보존한다.
- 계정 인증은 CLI가 관리한다. 인증 출력·원문·셸 명령은 브라우저에 반환하지 않는다.
- 실행파일·인수·경로는 서버가 정한다. 웹은 provider/model/reasoning만 전달한다.
- 설정 저장이 분석을 시작하지 않는다. 실행 중인 분석은 설정 변경의 영향을 받지 않는다. 명시된 제공사 실패 시 다른 제공사로 넘기지 않는다.
- CLI는 빈 임시 폴더, 표준입력 프롬프트, 제한된 도구, 시간 제한, 프로세스 종료를 적용한다. 기존 MCP·훅은 실행하지 않는다.
- 모델은 설치 목록(Ollama), 제공사 기본값·별칭과 직접 입력을 제공한다. 제공사마다 추론 옵션을 구분하며 지원 범위가 다른 모델은 서버 오류를 명확히 표시한다.

## Review Focus

- 분석 설정이 전사 mode를 바꾸거나 원치 않는 API fallback을 유발하지 않는다.
- 워커 취소·시간 초과 시 CLI 자식이 남지 않는다.
- 실패 출력에 포함된 인증정보가 API/작업 로그에 노출되지 않는다.
- 설정 변경·서버 재시작과 기존 저장 분석의 호환성을 유지한다.
- CLI의 사용자 MCP/훅/프로젝트 지시가 대화 정리에서 실행되지 않는다.

### Task 1: 설정 계약과 엔진 연결
**Files:** domain.py, analysis/settings.py, settings_api.py, engines/cli_analysis.py, local_analysis.py, cloud_analysis.py, analysis/service.py, jobs/runner.py, jobs/process.py, jobs/stage_guard.py, engines/local_executor.py, tests/test_analysis_settings.py, tests/test_cli_analysis.py, tests/test_process_control.py.
**Interfaces:** AnalysisSettings(provider,model,reasoning), GET/PATCH /api/settings/analysis, GET /api/settings/analysis/options?provider&model, StageRequest.analysis_settings, CliAnalysis.generate/merge.
- [x] 저장·입력 제한·설정 고정·CLI 실행·실패·취소 테스트를 작성해 실패를 확인한다.
- [x] 기존 실행 경로를 보존하며 설정된 도구로 실행한다.
- [x] 백엔드 검사 후 커밋한다.

### Task 2: 웹 설정과 검증
**Files:** AnalysisSettings.tsx/test.tsx, SettingsPage.tsx, CliConnections.tsx, api.ts, types.ts, schema.d.ts, styles.css, e2e_server.py, recording.spec.ts, README.md.
**Interfaces:** 분석 도구/모델/추론 선택과 저장, 저장 성공·오류 표시, 기존 로그인 영역 재사용.
- [x] 저장·새로고침·도구 변경·실패 복구 테스트의 실패를 확인한다.
- [x] 화면·타입·문서·fixture를 갱신한다.
- [x] 전체 검사·브라우저 화면·독립 리뷰 후 원래 프로젝트에 반영한다.

## 검증 결과

- Python 143개, 웹 39개, 브라우저 7개 테스트와 lint·형식·타입·빌드 통과.
- Codex 계정으로 가상 발언 2개를 실제 분석했다. 7.5초에 완료됐고 양식·근거 검증을 통과했다. 장시간 녹음의 성능 지표는 아니다.
- CLI의 실패·시간 초과·취소, 설정 고정, 자동 API 전환 차단, 실제 워커→분석 저장→내보내기 경로를 가짜 실행파일로 확인했다. OpenAI 모델·추론 전달은 SDK 경계에서 확인했다.
- 독립 리뷰의 두 지적을 재현한 뒤 수정했다. 실행 가드가 완료된 엔진의 하위 프로세스까지 종료하고, 작업별 임시 폴더를 삭제한다. 실행파일을 시작하지 못한 경우에도 정리한다.
- 데스크톱 1440px·모바일 390px 화면을 확인했다.
- 실제 Claude 분석과 OpenAI API 호출은 실행하지 않았다. 모델·추론 수준의 지원 범위는 도구 버전·계정·모델마다 다르다. Codex 모델 목록은 고정하지 않고 기본값 또는 직접 입력을 사용한다.

참고: [Codex 비대화형 실행](https://learn.chatgpt.com/docs/non-interactive-mode), [Codex 설정](https://learn.chatgpt.com/docs/config-file/config-reference), [Claude Code 비대화형 실행](https://code.claude.com/docs/en/headless), [Claude Code 모델 설정](https://code.claude.com/docs/en/model-config).
