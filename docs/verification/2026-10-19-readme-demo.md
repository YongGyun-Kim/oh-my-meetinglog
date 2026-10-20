# README 데모 검증

확인일: 2026-10-19. README에서 앱의 동작과 검증 범위를 보여주기 위해 실제 웹 화면을 촬영했다. 애플리케이션 코드와 기존 테스트는 수정하지 않았다.

## 환경과 입력

- macOS, Python 3.12.11, Node.js 22.23.1, Vite 8.3.4, Playwright Chromium.
- 브라우저 표시 영역은 1440×900이다. 스크린샷은 페이지 전체 높이로 저장했다.
- 입력은 16kHz 모노 PCM의 6초 무음 WAV다. 사적인 녹음이나 실제 대화는 사용하지 않았다.
- `tests.e2e_server`의 임시 데이터베이스와 파일 저장소를 사용했다. 웹, API, 워커, FFmpeg와 SQLite는 실제로 실행했다.
- 음성·분석 단계는 `tests/analysis_fixtures.py`의 두 발언과 분석을 반환하는 테스트 엔진이다. 전사 문장은 무음 파일에서 인식한 결과가 아니다.
- 새 음성 모델을 다운로드하거나 외부 API를 호출하지 않았다.

기능 검증 서버와 웹을 각각 실행했다.

```bash
uv run --no-sync python -m tests.e2e_server
```

```bash
MEETINGLOG_API_URL=http://127.0.0.1:8766 npm --prefix web run dev -- --port 5174
```

연결 가능한 Browser 플러그인 브라우저가 없어, 저장소에 설치한 Playwright Chromium으로 촬영했다. 촬영용 스크립트는 임시 경로에서 실행했으며 애플리케이션에 추가하지 않았다. 촬영이 끝난 뒤 브라우저와 테스트 서버를 종료했다.

## 확인한 동작

1. 파일 가져오기 화면에서 WAV를 업로드하고, 처리 완료 후 두 화자의 전사와 분석을 확인했다.
2. 첫 화자의 이름을 `인터뷰어`, 역할을 `질문자`로 변경하고 화면에 반영됐는지 확인했다.
3. 첫 발언을 `서비스는 언제 시작할까요?`로 수정했다.
4. 기존 분석이 수정 전 전사를 기준으로 한다는 안내가 나타나는지 확인했다.
5. 다시 분석한 뒤 안내가 사라지고 최신 전사에 대응하는 분석이 저장되는지 확인했다.
6. `근거 00:02 화자 B`를 눌러 해당 발언이 선택되고 음성 재생 위치가 2.2초로 이동하는지 확인했다.
7. JSON을 다운로드하고 수정한 발언이 포함됐는지 확인했다.
8. 기록 목록에 완료한 파일이 남는지 확인했다. API에서도 작업 상태 `succeeded`, `analysis_stale=false`, 수정한 전사를 확인했다.
9. 위 과정의 브라우저 `pageerror`가 없는지 확인했다.

## 결과물

| 파일                                              | 내용                                                              |
| ------------------------------------------------- | ----------------------------------------------------------------- |
| [browser-detail.png](assets/browser-detail.png)   | 전사 수정과 재분석을 완료한 두 화자의 전사·분석                   |
| [browser-edited.png](assets/browser-edited.png)   | 수정한 전사와 수정 전 분석 안내                                   |
| [browser-library.png](assets/browser-library.png) | 완료한 기록이 남아 있는 목록                                      |
| [browser-flow.webm](assets/browser-flow.webm)     | 파일 업로드부터 수정·재분석·내보내기·목록 확인까지의 12.84초 영상 |

스크린샷과 영상은 실제 화면을 그대로 저장했다. 음성 인식이나 분석 품질을 입증하는 자료로 사용하지 않는다.

README의 [local-result.png](assets/local-result.png)는 2026-10-16에 실제 로컬 모델로 한국어 합성 음성을 처리한 기존 기록이다. 이번 기능 촬영과 구분하며, 그 실행의 환경과 한계는 [기존 검증 문서](2026-10-16-local-mvp.md)에 있다.

## 자동 검사

같은 작업에서 `bash scripts/check.sh`를 실행해 종료 코드 0을 확인했다.

| 검사                            | 결과      |
| ------------------------------- | --------- |
| Ruff lint·format                | 통과      |
| 백엔드 테스트                   | 71개 통과 |
| TypeScript 타입 검사            | 통과      |
| 웹 컴포넌트 테스트              | 16개 통과 |
| Vite 프로덕션 빌드              | 통과      |
| Playwright 브라우저 통합 테스트 | 3개 통과  |
| `git diff --check`              | 통과      |

처음 `uv sync`로 기본 의존성만 설치했을 때는 모델 다운로드 차단 테스트의 `huggingface_hub` import가 실패했다. `speech` 선택 의존성에 선언된 `huggingface-hub`를 `uv pip install huggingface-hub`로 설치한 뒤 전체 검사를 다시 실행했다. README의 표준 설치·검사 명령은 `uv sync --extra speech`로 이 의존성을 포함한다. 이번 작업에서는 음성 모델 실행용 패키지 전체 설치와 모델 가중치 다운로드를 다시 검증하지 않았다.

기존 Starlette TestClient의 AnyIO 사용 중단 예정 경고와 Playwright의 색상 환경 변수 경고는 남아 있다. 테스트 실패는 없다.

README와 이 문서의 내부 파일 링크·목차를 검사했다. 세 PNG의 형식과 크기를 확인하고, WebM은 FFmpeg로 전체 디코딩해 오류가 없는지 확인했다.
