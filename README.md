# oh-my-meetinglog

## 소개

한국어 대화를 녹음하고 전사·대화 정리·내보내기를 제공하는 로컬 웹 앱이다.
제한된 디바이스에서 음성 인식과 대화 정리의 품질을 개선하고, 결과를 다음 작업에 사용할 수 있게 만드는 것이 목적이다.
정리한 대화는 Markdown·JSON으로 내보내 Codex·Claude Code 등에 전달할 수 있다. 보고서·견적서 작성이나 PoC 개발 등 후속 작업은 해당 에이전트에서 진행한다.

## 실행 화면

[![한국어 인터뷰의 전사와 대화 정리 화면](docs/verification/assets/fcseoul-detail.png)](docs/verification/assets/fcseoul-flow.webm)

[데모 영상 보기 · WebM](docs/verification/assets/fcseoul-flow.webm)

2026-10-20 버전에서 처리가 끝난 뒤 촬영한 무음 화면이다. 현재 화면과 일부 차이가 있다.

샘플 출처: **FC SEOUL**, [FC서울 신인 심원성 & 이태석 첫 인터뷰](https://www.youtube.com/watch?v=GnxVJrvGhRE), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) · [라이선스 기록](https://commons.wikimedia.org/wiki/File:FC서울_신인_심원성_%26_이태석_첫_인터뷰.webm). 원본에서 음성을 추출해 자동 전사·분석한 뒤 앱 화면을 촬영했다.

## 주요 기능

- 브라우저 마이크 녹음과 음성 파일 가져오기
- 화자별 전사와 문장 편집, 문장을 눌러 해당 음성 구간 재생
- 회의·인터뷰·프로젝트 논의 폼을 선택해 대화 정리
- 필요할 때 정리 내용의 근거 발언 확인
- 전사와 정리 결과를 Markdown·JSON으로 내보내 에이전트에 전달

현재 대화 분석은 Ollama를 사용한다. Codex·Claude Code는 **설정 → 대화 분석 모델**에서 로그인만 지원하며, 분석 실행과 MCP 연결은 아직 지원하지 않는다.

## 빠른 시작

로컬 음성 모델은 **Apple Silicon Mac**을 대상으로 한다. Python 3.12, Node.js 22.12 이상이 필요하며 브라우저는 Chrome을 기준으로 확인했다. 최소 메모리 요구량은 아직 확인하지 않았다.

### 1. 설치

Homebrew를 사용하는 경우 아래 명령을 실행한다.

```bash
git clone https://github.com/YongGyun-Kim/oh-my-meetinglog.git
cd oh-my-meetinglog
brew install uv node ffmpeg ollama
uv sync --extra speech
npm --prefix web ci
```

### 2. 모델 다운로드

| 용도           | 모델                                                                                                  |
| -------------- | ----------------------------------------------------------------------------------------------------- |
| 음성 구간 탐지 | [Silero VAD](https://huggingface.co/mlx-community/silero-vad)                                         |
| 전사           | [Qwen3-ASR 1.7B · 8bit](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit)                     |
| 발언 시간 정렬 | [Qwen3 ForcedAligner 0.6B · 8bit](https://huggingface.co/mlx-community/Qwen3-ForcedAligner-0.6B-8bit) |
| 화자 구분      | [Nemotron 3 Diarization](https://huggingface.co/mlx-community/Nemotron-3-Diarization)                 |
| 대화 분석      | [gpt-oss:20b · Ollama](https://ollama.com/library/gpt-oss)                                            |

Ollama 앱이나 서버를 실행한다. 실행 중인 서버가 없다면 별도 터미널에서 시작한다.

```bash
ollama serve
```

프로젝트 폴더의 다른 터미널에서 모델을 다운로드한다. 음성 모델은 파일만 수동으로 내려받지 말고 아래 명령으로 준비한다.

```bash
ollama pull gpt-oss:20b
uv run --no-sync meetinglog prepare-models
```

최초 다운로드에는 인터넷 연결과 수 GB 이상의 저장 공간이 필요하다.

### 3. 실행

```bash
bash scripts/dev.sh
```

[http://127.0.0.1:5173](http://127.0.0.1:5173)을 연다. 웹·API·워커가 함께 실행되며, **설정 → 로컬 엔진 준비 상태**에서 모델 준비 여부를 확인할 수 있다.

녹음하거나 파일을 가져온 뒤 전사를 확인한다. **대화 정리**에서 폼을 고르고 **정리 시작**을 누르면 분석을 실행한다.

현재는 서버 컴퓨터에서 접속하는 로컬 실행을 기준으로 한다. 원본 음성·전사·정리 결과는 `data/`, 음성 모델은 `models/`에 저장하며 두 경로는 Git에서 제외한다.

종료는 `Ctrl+C`로 한다. 별도로 실행한 Ollama는 따로 종료한다.
