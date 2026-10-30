# 연결된 CLI의 모델·추론 목록 조회

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Codex·Claude Code가 반환한 모델 목록과 모델별 지원 추론 수준을 설정 화면에 표시한다.
**Architecture:** 새 cli_catalog 모듈이 로그인 상태를 확인하고, 격리된 CLI 제어 채널에서 메타데이터만 조회한다. AnalysisOptions에 모델별 상세 목록을 추가하고 기존 모델 ID 목록은 유지한다. 웹은 조회된 모델 선택과 모델별 추론 수준을 표시하고, 저장 API도 조합을 검증한다.
**Tech Stack:** 기존 Python/subprocess/select/Pydantic/React. 의존성 추가 없음.
**Spec:** 직전 대화에서 승인한 실제 목록 조회·지원 추론만 표시·조회 실패 시 안내와 직접 입력 보조. Claude 계정은 로그아웃 상태이므로 로그인 후 실제 사용 권한 검증은 수행하지 않는다.

## Global Constraints

- Codex initialize → initialized → model/list. nextCursor로 페이지를 끝까지 읽고 CLI가 보낸 순서·기본값·지원 수준을 보존한다.
- Claude 공식 SDK supportedModels()는 initialize 응답의 models를 반환한다. value/displayName/resolvedModel/supportsEffort/supportedEffortLevels를 사용한다. 지원 필드가 없으면 추측하지 않고 기본값만 표시한다.
- 모델에 요청을 보내거나 분석·도구·MCP·훅·로그인을 실행하지 않는다. 인증 정보는 읽거나 반환하지 않는다. 임시 폴더, 실행 시간·출력 크기 제한, 프로세스 그룹 종료를 적용한다.
- 로그아웃·조회 실패를 고정 모델 목록으로 대체하지 않는다. 직접 입력 보조에서는 추론을 기본값으로 제한한다. 저장된 값은 조용히 변경하지 않고 화면에서 불일치를 알린다.
- 정상 조회 시 서버도 모델·추론 조합을 확인한다. 조회 실패 시 기본 추론만 설정할 수 있다. 전사 방식과 실행 중 분석의 설정 고정은 유지한다.
- Ollama 설치 목록 조회는 유지한다. 기존 OpenAI API 설정은 이번 Codex·Claude 조회 변경의 범위 밖이다.

## Sources

- https://learn.chatgpt.com/docs/app-server#list-models-modellist
- https://code.claude.com/docs/en/cli-reference
- https://github.com/anthropics/claude-agent-sdk-typescript
- 공식 npm @anthropic-ai/claude-agent-sdk 0.3.310 sdk.d.ts ModelInfo / SDKControlInitializeResponse, sdk.mjs Query.supportedModels() 확인. 런타임 의존성으로 설치하지 않는다.

## Review Focus

- 로그인 없는 Claude의 로컬 기본 카탈로그를 실제 계정 권한으로 표시하지 않는다.
- 모델 변경·느린 이전 응답·재조회가 지원하지 않는 추론 수준을 되살리지 않는다.
- CLI 출력·로그의 계정 정보는 API에 노출하지 않고 종료·시간 초과 후 자식을 남기지 않는다.
- 서버는 화면을 우회한 지원하지 않는 모델·추론 조합을 저장하지 않는다.
- 기존 저장 설정과 직접 입력 보조를 유지하며 고정된 CLI 목록으로 실패를 가리지 않는다.

### Task 1: 메타데이터 조회와 서버 검증
**Files:** analysis/cli_catalog.py, analysis/settings.py, domain.py, settings_api.py, tests/test_cli_catalog.py, tests/test_analysis_settings.py, tests/test_cli_analysis.py.
**Interfaces:** ModelOption(id,name,reasoning,default_reasoning,aliases), AnalysisOptions.catalog, validate_selection(settings, runtime). 기존 options(provider,model,runtime) 호출과 모델 ID 배열은 유지한다.
- [x] CLI 제어 채널·페이지 처리·지원 정보 누락·로그아웃·오류·종료와 저장 검증의 실패를 확인한다.
- [x] 문서·설치된 CLI 응답을 기준으로 구현하고 백엔드 검사를 통과한다.

### Task 2: 모델 선택 화면
**Files:** AnalysisSettings.tsx/test.tsx, CliConnections.test.tsx, schema.d.ts, recording.spec.ts, README.md.
**Interfaces:** 모델 선택 → 해당 모델의 추론 수준만 표시, 모델 변경 시 기본값으로 초기화, 조회 실패 시 직접 입력과 기본 추론.
- [x] 모델별 옵션 변경·불일치·이전 응답 무시·저장 실패를 확인한다.
- [x] 화면과 타입을 갱신하고 전체 검사·독립 리뷰 후 원래 프로젝트에 반영한다.

## 확인한 프로토콜

- Codex CLI 0.163.0의 실제 model/list가 모델 7개와 모델별 supportedReasoningEfforts/defaultReasoningEffort/isDefault를 반환했다. 앱과 같은 OpenAI 제공사를 지정한다.
- Claude Code 2.1.280은 로그인 없이도 initialize에 기본 모델 5개를 반환한다. 따라서 이 응답만으로 계정 권한을 확인했다고 보지 않으며, 제품 조회는 인증 상태가 connected인 경우에만 실행한다.
- Claude 초기화 응답의 models 항목에서 value/resolvedModel/displayName/supportsEffort/supportedEffortLevels를 확인했다. opus[1m]과 같은 문맥 길이 별칭을 허용한다. 새 SDK를 런타임 의존성으로 추가하지 않았다.
- 실제 Claude 계정 권한과 분석 호출은 미검증이다. 공식 SDK 타입/구현, 설치된 CLI 초기화 응답, 통제된 제어 채널과 실패 응답으로 검증한다.

## 최종 검증

- Python 152개·웹 42개 테스트, lint·형식·타입 검사·빌드 통과.
- 기존 브라우저 6개가 통과했다. 새 설정 시나리오는 접힌 select의 옵션 가시성·라벨 매칭을 기다리던 테스트를 역할 기반 선택으로 수정한 뒤 별도로 통과했다. 총 7개 시나리오를 확인했다.
- 데스크톱 1440px·모바일 390px 설정 화면과 가로 넘침을 확인했다.
- 독립 리뷰에서 병합을 막는 추가 결함을 발견하지 못했다.
- 실제 Codex 모델 목록 7개와 각 모델의 지원 추론 수준·기본값을 조회했다. Claude는 로그아웃 상태에서 제품 목록을 비우고 로그인·새로 고침 안내를 표시한다.
- Claude 공식 SDK 타입·구현과 설치된 CLI 초기화 응답을 대조했지만, 로그인 후 계정 권한과 실제 Claude 분석은 확인하지 않았다. 이번 검증에서는 모델 추론 요청을 보내지 않았다.
