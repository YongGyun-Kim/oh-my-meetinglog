# oh-my-meetinglog

한국어 인터뷰·상담 녹음을 화자별 전사와 근거가 연결된 대화 기록으로 만드는 로컬 웹 서비스.

맥북 브라우저 + 같은 Mac의 로컬 서버로 실행하는 첫 MVP입니다. 마이크 녹음과 파일 가져오기, 화자별 전사, 원문을 보존하는 수정, 근거가 연결된 대화 분석, Markdown·JSON 내보내기를 제공합니다.

한국어 1:1부터 품질을 검증하며 추후 다대다 대화를 고려합니다. 현재 로컬 모델 조합은 교체 가능한 초기 후보이며 실제 인터뷰의 CER·DER 및 60분 처리 성능은 **미검증**입니다. 아이폰·다른 기기의 접속은 후속 범위입니다.

## 실행

Apple Silicon Mac, Python 3.12(uv가 준비), Node.js 22.12 이상, FFmpeg·FFprobe, Ollama가 필요합니다. 현재 개발 기기는 M5 Pro / 메모리 48GB입니다. 더 작은 Mac의 실행 가능 메모리는 아직 측정하지 않았습니다.

```bash
brew install ffmpeg
uv sync --extra speech
npm --prefix web ci
ollama pull gpt-oss:20b
uv run --no-sync meetinglog prepare-models
uv run --no-sync meetinglog doctor
bash scripts/dev.sh
```

Ollama 서버를 실행한 상태에서 [http://127.0.0.1:5173](http://127.0.0.1:5173)을 엽니다. `scripts/dev.sh`는 API(8765), 작업자, 웹(5173)을 시작합니다. Ctrl+C는 이 스크립트가 시작한 프로세스만 종료하며 공유 Ollama 서버는 종료하지 않습니다. 포트가 이미 사용 중이면 기존 실행을 먼저 종료하세요.

초기 모델 다운로드에는 네트워크와 수 GB 저장 공간이 필요합니다. 다운로드가 Xet 전송에서 멈추는 환경은 `HF_HUB_DISABLE_XET=1 uv run --no-sync meetinglog prepare-models`로 재시도할 수 있습니다. 추론은 준비된 로컬 경로만 사용하며 자동으로 모델을 다운로드하지 않습니다. `models/manifest.json`에 실제 모델 revision을 저장합니다.

### 사용 흐름

1. **녹음 시작**으로 마이크 권한을 허용하거나 **파일 가져오기**로 녹음을 선택합니다. 최대 2시간 / 1GB입니다.
2. 녹음 종료 후 마지막 데이터 저장이 완료되면 전사·화자 구분·분석을 순서대로 진행합니다. 녹음 중에는 브라우저를 열어 두세요. 종료 후에는 서버와 작업자가 계속 처리합니다.
3. 발언의 시각이나 분석 근거를 누르면 원본 음성의 해당 위치로 이동합니다. 재생 버튼으로 소리를 들을 수 있습니다.
4. 발언과 화자 이름·역할을 수정할 수 있습니다. 전사 수정은 새 버전을 만들며 원문은 보존합니다. 이전 분석에는 기준 버전을 표시하고 **다시 분석**으로 갱신합니다.
5. **내보내기**에서 현재 전사에 대응하는 Markdown 또는 AI 분석용 JSON을 받습니다. 수정 후 재분석 전에는 최신 전사만 내보내고, 이전 분석을 섞지 않습니다.

처리는 취소하거나 원본에서 다시 전사할 수 있습니다. 분석만 실패하면 전사와 음성은 남으며 **다시 분석**으로 재시도합니다. 작업자를 정상 종료한 뒤 다시 실행하면 중단된 작업을 재개합니다. **삭제**는 원본·전사·분석을 삭제하며 실행 중인 처리를 먼저 중지합니다. 브라우저가 녹음 도중 닫힌 경우에는 ‘저장 미완료’로 남으며 자동 복구하지 않습니다.

## 처리 방식과 데이터

기본 모드는 **로컬 전용**입니다. 외부 API로 자동 전환하지 않습니다. 설정에서 자동 선택 또는 외부 API로 바꿀 수 있습니다. 자동 선택은 로컬 실패·시간 초과 또는 증거가 있는 평가 실패 시 구성된 API로 전환합니다. ‘정확도 미검증’은 품질 통과를 뜻하지 않습니다.

현재 로컬 조합은 Silero VAD → Qwen3-ASR 1.7B → Qwen3 ForcedAligner → Nemotron 3 Diarization → Ollama `gpt-oss:20b`입니다. 음성 모델은 순차 로드하며 처리 작업은 한 번에 하나입니다. 원본의 채널·표본화율은 보존하고 16kHz 모노 파생본으로 추론합니다. 강한 잡음 제거와 겹친 음성 분리는 기본 적용하지 않습니다. 불확실한 화자·겹침·시간 정렬에는 검토 표시를 남깁니다.

- `data/meetinglog.sqlite3`: 기록, 작업 상태, 전사·분석 버전
- `data/recordings/`: 원본, 녹음 청크, 추론용 파생 파일과 엔진 결과
- `models/`: 준비된 음성 모델과 revision manifest

이 경로와 `.env`는 Git에서 제외합니다. 로컬 파일은 OS 계정의 파일 권한을 사용하며 앱 자체 암호화는 제공하지 않습니다. 서버와 웹은 loopback에만 바인딩합니다.

외부 API 사용은 `.env.example`을 참고해 프로젝트 `.env`에 `OPENAI_API_KEY`를 설정하고 API와 작업자를 다시 실행하세요. 브라우저에는 키를 전달하지 않습니다. 구성 여부와 실제 호출 성공 여부는 구분합니다. 외부 모드에서는 음성·텍스트가 API 제공자에게 전송되며 재시도에 추가 요금이 발생할 수 있습니다. API 키가 없는 환경에서는 외부 실제 호출을 검증하지 않았습니다.

## 개발·검증

```bash
# 처음 한 번 브라우저 설치가 필요할 수 있습니다.
npm --prefix web exec playwright install chromium
bash scripts/check.sh

# OpenAPI TypeScript 계약 갱신
uv run --no-sync meetinglog schema > web/src/lib/schema.json
web/node_modules/.bin/openapi-typescript web/src/lib/schema.json -o web/src/lib/schema.d.ts
```

- [실행 확인 결과와 미검증 항목](docs/verification/2026-10-16-local-mvp.md)
- [실제 음성 평가 방법](evaluation/README.md)

## 설계·조사

- [로컬 웹 MVP 설계안](docs/superpowers/specs/2026-10-16-local-conversation-records-design.md)
- [구현 계획](docs/superpowers/plans/2026-10-16-local-conversation-records.md)
- [Plaud 음성 전처리 조사](docs/research/2026-10-16-plaud-audio-preprocessing.md)
- [음성 모델 후보·제약·평가 기준](docs/research/2026-10-16-audio-model-candidates.md)
- [맥북·아이폰 웹 적용성 및 실제 확인 범위](docs/research/2026-10-16-macbook-iphone-web-feasibility.md)
