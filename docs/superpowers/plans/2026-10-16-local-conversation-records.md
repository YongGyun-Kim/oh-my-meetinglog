# Local Conversation Records Implementation Plan

실행 결정(2026-10-16): 사용자의 ‘맥북 웹 + 로컬 서버만 먼저 진행’ 지시에 따라 현재 세션에서 직접 구현한다. 아이폰·LAN 접속은 제외한다. 후속 모델 조사를 반영해 기본 화자 구분 연결 후보를 Nemotron 3로 갱신하며, 품질은 검증 전까지 미확인으로 표시한다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한국어 1:1 인터뷰·상담 녹음을 로컬 우선으로 처리해 화자별 전사와 원문에 근거한 대화 기록을 제공하는 개인용 웹 서비스를 만든다.

**Architecture:** React 웹, FastAPI 서버, SQLite 작업 큐를 읽는 단일 워커로 구성한다. 음성 추론은 별도 자식 프로세스에서 순차 실행하고, Ollama 분석과 OpenAI 대체 경로도 같은 결과 계약으로 정규화한다. 전사·분석 버전을 보존하며 단계 완료를 트랜잭션으로 반영한다.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, SQLite, FFmpeg/FFprobe, MLX-Audio, MLX Whisper, Ollama, OpenAI Python SDK, React, TypeScript, Vite, Vitest, Testing Library, Playwright, pytest, httpx.

**Spec:** [사용자 승인 설계안](../specs/2026-10-16-local-conversation-records-design.md). 승인일: 2026-10-16. 이 계획은 설계안의 실행 순서를 정의하며 제품 코드가 아니다.

**후속 조사(2026-10-16):** 모델 선택 전 [Plaud 전처리 조사](../../research/2026-10-16-plaud-audio-preprocessing.md)와 [모델 후보·평가 기준](../../research/2026-10-16-audio-model-candidates.md)을 확인한다. 다대다 대화 요구와 추가 후보가 생겼으며, 아래 초기 엔진명은 확정 선택이 아니다. 엔진 관련 실행 항목은 모델 결정 후 갱신한다.

## Global Constraints

아래 제품 조건은 승인 설계안에서 그대로 가져왔다.

- 첫 사용 사례는 **한국어 1:1 인터뷰·상담**이다.
- 마이크 녹음과 기존 음성 파일 입력을 모두 지원한다.
- 실시간 자막은 필요하지 않다. **녹음 종료 후 정확한 결과**를 제공한다.
- 품질과 속도가 충분한 처리는 PC에서 끝낸다. 부족한 단계에는 외부 API를 사용할 수 있다.
- macOS Apple Silicon과 Chrome을 우선 지원한다.
- 한 파일은 최대 2시간·1GB로 제한한다. 녹음도 최대 2시간으로 제한하고 종료 전에 안내한다.
- 로그인 없이 한 사람이 사용하며, 원본과 기록은 로컬 디스크에 저장한다.
- 서버는 기본적으로 `127.0.0.1`에서만 수신한다.
- API 키는 서버 측 비밀 설정에 두고 브라우저 응답·로그·내보내기에 포함하지 않는다.
- 로컬 전용 처리 중에는 모델을 자동 다운로드하지 않고, 로컬 LLM 연결도 루프백 주소의 설치된 모델로 제한한다.
- 동시 추론 작업 수는 하나로 시작한다.

실행 환경과 프로젝트 지침:

- 기존 Orca 연결 worktree와 현재 브랜치를 그대로 사용한다. 이미 격리되어 있으므로 추가 worktree를 만들지 않는다.
- **모든 AI-DLC 엔진 명령은 PATH의 원래 `aidlc`로 실행한다. 위임된 에이전트에도 같은 실행 명령을 전달한다. 명령의 인수와 플래그는 그대로 유지한다. 실행파일을 사용할 수 없으면 알리고 중단한다.**
- 이 계획은 AI-DLC 초기화나 엔진 상태 변경을 요구하지 않는다. 현재 프로젝트에는 생성된 AI-DLC 실행 지침이 없다.
- 현재 Node.js는 22.23.1, uv는 0.7.19이며 기본 Python은 3.13.5다. 프로젝트 Python 3.12 환경을 별도로 만든다.
- 의존성은 실행 시 설치하고 `uv.lock`, `web/package-lock.json`을 커밋한다. 음성 모델·녹음·DB·비밀 파일은 커밋하지 않는다.
- 테스트는 실제 계약과 실패 복구를 검증한다. 정적 문구나 단순 컴포넌트 모양을 복제하는 테스트는 추가하지 않는다.
- 공식 SDK와 모델 메서드의 실제 반환값은 고정한 패키지 버전에서 확인한다. 아래 외부 호출 예제의 반환값을 검증 없이 저장하지 않는다.

## Review Focus

1. 정상 컨테이너 안의 긴 침묵: 전사·분석을 만들어내지 않고 ‘인식된 음성 없음’으로 끝나야 한다. Task 5의 무음 분기 테스트가 담당한다.
2. 마지막 녹음 데이터가 늦게 도착하거나 청크가 중복·누락됨: 중복 저장을 막고, 완성되지 않은 녹음을 처리 큐에 넣지 않아야 한다. Task 2와 Task 10의 종료 순서 테스트가 담당한다.
3. 긴 대화의 짧은 맞장구·겹침·화자 순서 변화: 발언을 지우거나 화자 A/B를 무조건 합치지 않아야 한다. Task 5와 Task 6의 연결 테스트가 담당한다.
4. 분석 중 다른 탭에서 전사 편집 또는 기록 삭제: 작업이 최신 버전을 덮어쓰거나 삭제된 기록을 되살리지 않아야 한다. Task 3, Task 4, Task 9의 경쟁 상태 테스트가 담당한다.
5. 로컬 전용 실행에 원격 Ollama 주소·누락 모델·키가 함께 설정됨: 외부 전송 없이 구체적인 준비 오류를 반환해야 한다. Task 7의 차단 테스트가 담당한다.

## 파일 배치와 책임

| 경로 | 책임 |
| --- | --- |
| `pyproject.toml`, `.python-version`, `uv.lock` | Python 실행·의존성·테스트 설정 |
| `.gitignore`, `.env.example` | 데이터·비밀 제외와 서버 설정 예시 |
| `backend/src/meetinglog/app.py`, `config.py`, `cli.py` | 앱 생성, 서버 설정, 명령 진입점 |
| `backend/src/meetinglog/domain.py` | 단계 간 공통 Pydantic 계약 |
| `backend/src/meetinglog/db.py`, `migrations/*.sql` | 연결·마이그레이션·트랜잭션 |
| `backend/src/meetinglog/recordings/` | 입력 저장, 청크, 전처리, 기록 API |
| `backend/src/meetinglog/transcripts/` | 버전 저장, 편집, 화자 표시 정보 |
| `backend/src/meetinglog/jobs/` | 작업 큐, 단계 실행, 취소·복구 |
| `backend/src/meetinglog/engines/` | 준비된 모델, 로컬·API 어댑터, 처리 경로 선택 |
| `backend/src/meetinglog/analysis/` | 근거 검증, 구간 분석·병합, 분석 저장 |
| `backend/src/meetinglog/exports.py`, `settings_api.py` | JSON·Markdown, 준비 상태 조회 |
| `web/src/features/recordings/` | 목록, 업로드, 녹음 |
| `web/src/features/detail/` | 음성 재생, 전사 편집, 분석·근거 이동 |
| `web/src/features/settings/` | 실행 모드와 준비 상태 |
| `web/src/lib/api.ts`, `types.ts` | 서버 통신과 생성된 계약 |
| `tests/`, `web/src/**/*.test.tsx`, `web/e2e/` | Python·컴포넌트·브라우저 검증 |
| `evaluation/`, `docs/verification/` | 평가 형식과 실제 검증 보고서 |
| `scripts/dev.sh`, `scripts/check.sh` | 로컬 실행과 품질 확인 |

각 새 Python 패키지에 `__init__.py`를 만든다. 추론 라이브러리는 어댑터 호출 내부에서 지연 import한다. API 앱과 일반 단위 테스트가 MLX·모델 다운로드에 의존하지 않게 한다. 아래 테스트 조각에서 사용하는 `pytest`, `unittest.mock`과 계약 타입은 각 테스트 모듈에 명시적으로 import한다. 공통 fixture는 해당 작업에서 `tests/conftest.py`에 추가하고, fixture의 존재를 가정한 채 테스트를 건너뛰지 않는다.

## 공통 계약

Task 1에서 다음 타입을 `domain.py`에 정의한다. ID는 저장 시 UUID 문자열을 생성하며, 시간은 원본 기준 정수 밀리초다. 모든 Pydantic 모델은 `extra="forbid"`를 사용한다.

| 타입 | 필드 |
| --- | --- |
| `Mode` | `Literal["auto", "local_only", "api"]` |
| `Recording` | `id: str`, `title: str`, `source: Literal["microphone", "file"]`, `input_state: Literal["recording", "uploading", "ready", "invalid"]`, `duration_ms: int | None`, `created_at: datetime`, `generation: int` |
| `Word` | `text: str`, `start_ms: int`, `end_ms: int` |
| `Turn` | `id: str`, `start_ms: int`, `end_ms: int`, `speaker_id: str | None`, `text_original: str`, `text_edited: str | None`, `review_flags: list[str]`, `words: list[Word]` |
| `Speaker` | `id: str`, `display_name: str`, `role: str | None` |
| `Transcript` | `id: str`, `recording_id: str`, `parent_id: str | None`, `turns: list[Turn]`, `speakers: list[Speaker]`, `created_at: datetime` |
| `Fact` | `text: str`, `evidence_turn_ids: list[str]` |
| `Overview` | `kind: Literal["interview", "counseling", "conversation", "unknown"]`, `summary: Fact`, `main_topics: list[Fact]` |
| `Topic` | `title: str`, `start_ms: int`, `end_ms: int`, `discussion: list[Fact]`, `different_views: list[Fact]`, `conclusion: Fact | None`, `evidence_turn_ids: list[str]` |
| `QuestionAnswer` | `question: Fact`, `answer: Fact | None` |
| `Action` | `text: str`, `owner_speaker_id: str | None`, `due_text: str | None`, `evidence_turn_ids: list[str]` |
| `AnalysisBody` | `overview: Overview`, `topics: list[Topic]`, `question_answers: list[QuestionAnswer]`, `agreements: list[Fact]`, `open_questions: list[Fact]`, `actions: list[Action]` |
| `AnalysisVersion` | `id: str`, `transcript_id: str`, `body: AnalysisBody`, `provider: str`, `model: str`, `prompt_version: str`, `created_at: datetime` |
| `Job` | `id: str`, `recording_id: str`, `transcript_id: str | None`, `kind: Literal["process", "analyze"]`, `state: str`, `stage: str`, `generation: int`, `mode: Mode`, `created_at: datetime` |
| `SpeechResult` | `turns: list[Turn]`, `speakers: list[Speaker]`, `no_speech: bool`, `provider: str`, `model: str`, `raw_artifact: str` |
| `StageRequest` | `job_id: str`, `recording_id: str`, `generation: int`, `stage: str`, `input_path: str`, `output_path: str`, `mode: Mode` |
| `StageResult` | `job_id: str`, `generation: int`, `stage: str`, `artifact_path: str`, `metadata: dict[str, str | int | float | bool | None]` |

`Turn`은 `0 <= start_ms < end_ms`, 비어 있지 않은 원문을 검증하고, `Transcript`는 발언 ID 중복을 거부한다. 구현 설명과 화면의 언어는 한국어로 통일한다. `AnalysisBody`의 nullable 필드도 출력 JSON에서는 생략하지 않고 null로 포함한다. 분석 스키마는 구조 검증용이며 의미의 사실성을 자동 보장하지 않는다.

오류는 `{"error":{"code":str,"message":str,"retryable":bool}}`로 통일한다. 입력 오류 422, 편집·청크 충돌 409, 용량 초과 413, 존재하지 않거나 삭제된 기록 404, 준비되지 않은 엔진 503을 사용한다. 외부 SDK 오류 본문이나 API 키를 그대로 반환하지 않는다.

## 실행 순서

Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 순서로 진행한다. 각 작업은 아래 실패 테스트를 먼저 실행하고 계약을 완성한 뒤 해당 범위만 커밋한다. 테스트 이름과 코드가 예시인 경우에도 같은 사용자 행동과 실패 조건을 유지한다.

### Task 1: 로컬 서버와 공통 데이터 계약

**Files:** Create `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `backend/src/meetinglog/{__init__,app,config,domain,db,cli}.py`, `backend/src/meetinglog/migrations/001_core.sql`, `tests/{conftest,test_boot,test_domain}.py`. Create `uv.lock` during dependency resolution.

**Interfaces:** Produces `Settings(data_dir: Path = Path("data"), max_upload_bytes: int = 1_000_000_000, max_duration_ms: int = 7_200_000)`, `create_app(settings: Settings | None = None) -> FastAPI`, `Database(path: Path).connect() -> sqlite3.Connection`, `Database.migrate() -> None`, and all common contracts above.

- [x] **Step 1: 부팅·영속성·잘못된 시간 계약의 실패 테스트를 작성한다.**

```python
def test_boot_creates_persistent_store(tmp_path):
    from fastapi.testclient import TestClient
    from meetinglog.app import create_app
    from meetinglog.config import Settings
    for _ in range(2):
        with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
            assert client.get('/api/health').json() == {'status': 'ok'}
    assert (tmp_path / 'meetinglog.sqlite3').is_file()
```

`test_domain.py`에서는 종료가 시작보다 이른 발언, 같은 ID의 발언 두 개, 음수 시각을 각각 거부하는 테스트를 추가한다.

- [x] **Step 2: `uv run --python 3.12 --with pytest pytest tests/test_boot.py tests/test_domain.py -q`를 실행해 앱 모듈이 없어 실패하는 것을 확인한다.**
- [x] **Step 3: Python 패키지·설정·DB를 구현한다.** `pyproject.toml`은 hatchling으로 `backend/src/meetinglog`를 패키징하고 `[project.scripts]`의 `meetinglog = "meetinglog.cli:main"`을 선언한다. 기본 의존성은 `fastapi`, `uvicorn`, `pydantic-settings`, `python-multipart`, `httpx`, `openai`, `numpy`, `soundfile`; 개발 그룹은 `pytest`, `pytest-asyncio`, `respx`, `ruff`; `speech` extra는 `mlx-audio`, `mlx-whisper`, `huggingface-hub`, `torch`, `pyyaml`; `evaluation` extra는 `jiwer`, `pyannote.metrics`다. 잠금 파일에 실제 해석된 버전을 고정한다. 설정은 `MEETINGLOG_` 접두사, 서버 비밀은 `OPENAI_API_KEY`를 사용한다.

```python
def connect(self):
    connection = sqlite3.connect(self.path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute('PRAGMA busy_timeout = 10000')
    return connection
```

마이그레이션 버전을 DB에 기록하고 WAL을 켠다. `recordings`, `jobs`, `job_events`, `schema_migrations`를 만든다. `jobs`에는 단계, 기준 전사 ID, 취소 여부, 시도 수, heartbeat, generation을 보관한다. `data/`, `models/`, `.env`, 캐시·빌드 출력은 Git에서 제외한다. CLI `serve`는 `uvicorn`을 `127.0.0.1:8765`에서 시작한다. 앱 시작 시 DB 초기화만 수행하며 모델을 로드하지 않는다.

- [x] **Step 4: `uv sync` 후 `uv run pytest tests/test_boot.py tests/test_domain.py -q`와 `uv run ruff check backend tests`를 통과시킨다.**
- [x] **Step 5: 위 파일만 스테이징하고 `git commit -m "feat: add local server and persistent domain contracts"`를 실행한다.**

### Task 2: 파일 입력·녹음 청크·음성 전처리

**Files:** Create `recordings/{__init__,storage,media,service,api}.py` under `backend/src/meetinglog/`; create `tests/{audio_fixtures,test_inputs,test_media}.py`; modify `app.py`.

**Interfaces:** Consumes `Settings`, `Database`, `Recording`. Produces `InputService.create(source: str, title: str) -> Recording`, `append_chunk(recording_id: str, sequence: int, body: bytes) -> str` (SHA-256), `finalize(recording_id: str, last_sequence: int) -> Recording`, `import_file(filename: str, chunks: Iterable[bytes]) -> Recording`, `MediaInfo(duration_ms: int, sample_rate: int, channels: int)`, `probe(path: Path) -> MediaInfo`, `normalize(source: Path, destination: Path) -> MediaInfo`.

- [x] **Step 1: 같은 청크 재전송·서로 다른 내용의 재전송·중간 청크 누락을 검증한다.** `tests/audio_fixtures.py`의 `write_silence(path: Path, seconds: int = 1) -> Path`는 표준 `wave`로 16kHz·16bit·mono 무음 WAV를 생성한다. 파일명에 `../../`가 있어도 저장 경로는 기록 UUID 아래에 있어야 한다. 작은 테스트 용량 제한을 설정해 스트리밍 중 초과를 검증한다.

```python
def test_missing_chunk_does_not_finalize(input_service):
    record = input_service.create('microphone', '인터뷰')
    first_hash = input_service.append_chunk(record.id, 0, b'header')
    assert input_service.append_chunk(record.id, 0, b'header') == first_hash
    input_service.append_chunk(record.id, 2, b'last')
    with pytest.raises(InputConflict, match='missing_chunk'):
        input_service.finalize(record.id, last_sequence=2)
```

`input_service` fixture는 임시 DB·디스크를 연결한다. `InputConflict`는 `recordings/service.py`에 정의하는 충돌 예외다.

- [x] **Step 2: `uv run pytest tests/test_inputs.py tests/test_media.py -q`를 실행해 해당 모듈이 없어 실패하는 것을 확인한다.**
- [x] **Step 3: 청크를 `{UUID}/chunks/{sequence:06d}.bin`에 임시 기록 후 atomic rename한다.** 청크 PK는 `(recording_id, sequence)`이며 hash가 같으면 성공을 재반환하고 다르면 409를 반환한다. 전체 크기를 DB 트랜잭션에서 계산해 1GB를 넘으면 413으로 거부한다. 마지막 순번까지 연속이며 파일 검증이 성공한 경우에만 `ready`로 전환한다. 정상화 파일은 원본과 별도로 만든다.

```python
command = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(source),
           '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(destination)]
subprocess.run(command, check=True, capture_output=True, timeout=180)
```

`ffprobe -v error -show_format -show_streams -of json`을 argv 배열로 호출해 실제 음성 스트림과 길이를 검사한다. 손상 컨테이너·2시간 초과·음성 스트림 없음은 `invalid`로 기록한다. 입력 API는 `POST /api/recordings`(multipart 파일), `POST /api/recordings/drafts`(제목·source), `PUT /api/recordings/{id}/chunks/{sequence}`(binary body), `POST /api/recordings/{id}/finalize`(last_sequence)다. 이 단계에서는 입력 저장·검증까지 완성하고 자동 작업 등록은 Task 9에서 연결한다.

- [x] **Step 4: FFmpeg 미설치 시 `brew install ffmpeg`로 준비하고 `uv run pytest tests/test_inputs.py tests/test_media.py -q`를 통과시킨다.** FFprobe로 생성 WAV의 1,000ms 길이와 16kHz mono 출력도 확인한다. 이 무음 fixture를 음성 인식 품질 평가 자료로 사용하지 않는다.
- [x] **Step 5: `git commit -m "feat: ingest audio files and durable recording chunks"`로 해당 범위만 커밋한다.**

### Task 3: 전사 버전·화자 수정·동시 편집

**Files:** Create `transcripts/{__init__,repository,service,api}.py`, `migrations/002_transcripts.sql`; create `tests/test_transcript_versions.py`; modify `app.py`.

**Interfaces:** Produces `TranscriptRepository.save_generated(recording_id: str, speech: SpeechResult, expected_generation: int, producer_job_id: str | None = None) -> Transcript`, `get(transcript_id: str) -> Transcript`, `current(recording_id: str) -> Transcript | None`, `TranscriptService.edit(recording_id: str, base_version_id: str, changes: list[dict]) -> Transcript`, `rename_speaker(recording_id: str, speaker_id: str, display_name: str) -> None`. `VersionConflict` is defined in `transcripts/service.py`.

- [x] **Step 1: 원문 보존과 두 탭의 낡은 버전 수정 거부를 검증한다.** 테스트 내부에 `SpeechResult`를 두 발언·두 화자로 구성해 저장한다. fixture `transcript_service_with_two_turns`는 서비스와 최초 전사 두 값을 반환한다.

```python
def test_edit_is_versioned(transcript_service_with_two_turns):
    service, original = transcript_service_with_two_turns
    edited = service.edit(original.recording_id, original.id,
                          [{'turn_id': original.turns[0].id, 'text': '수정한 발언'}])
    assert edited.id != original.id
    assert service.repository.get(original.id).turns[0].text_edited is None
    with pytest.raises(VersionConflict):
        service.edit(original.recording_id, original.id,
                     [{'turn_id': original.turns[0].id, 'text': '다른 탭 수정'}])
```

- [x] **Step 2: `uv run pytest tests/test_transcript_versions.py -q`로 실패를 확인한다.**
- [x] **Step 3: 전사 payload와 부모 버전, current 포인터를 저장한다.** `BEGIN IMMEDIATE` 안에서 현재 ID·기록 generation을 비교한 뒤 새 전사를 저장한다. 생성 전사는 producer_job_id의 unique 제약으로 같은 작업의 재실행에 기존 버전을 반환한다. 내용·화자 배정·역할 변경은 새 버전으로 만들고, 표시 이름은 안정적인 화자 ID의 표시 정보 테이블에서 갱신한다. 역할 변경도 분석의 기준 전사를 바꾸도록 한다. 원문·단어 시간은 유지하고 수정본만 변경한다.

```sql
UPDATE recordings SET current_transcript_id = ?
WHERE id = ? AND current_transcript_id = ? AND generation = ?;
```

업데이트 건수가 1이 아니면 전체 트랜잭션을 rollback하고 409로 응답한다. 편집 API는 `PATCH /api/recordings/{id}/transcript`에 `base_version_id`와 변경 목록을 요구한다. 화자 이름은 `PATCH /api/recordings/{id}/speakers/{speaker_id}`로 수정한다. 다른 기록의 발언·화자 ID는 거부한다.

- [x] **Step 4: 위 테스트와 잘못된 화자 ID·역할 변경·이름 변경 테스트를 통과시킨다.**
- [x] **Step 5: `git commit -m "feat: preserve transcript revisions and speaker edits"`로 커밋한다.**

### Task 4: 작업 워커·중단 복구·취소

**Files:** Create `jobs/{__init__,repository,runner,process,api}.py`, `tests/{test_jobs,test_process_control}.py`; modify `cli.py`, `app.py`.

**Interfaces:** Produces `JobRepository.enqueue(recording_id: str, kind: str, transcript_id: str | None, mode: Mode) -> Job`, `claim() -> Job | None`, `cancel(job_id: str) -> None`, `commit_stage(result: StageResult) -> bool`, `Worker.run_once() -> bool`, `ProcessRunner.run(request: StageRequest, timeout_s: float) -> StageResult`. `Worker` takes a `stage_command: Callable[[StageRequest], list[str]]` for injectable executors. The real engine executor is connected in Task 8.

- [x] **Step 1: 중단 복구, 취소 후 늦게 온 결과 거부, 동일 활성 작업 중복 방지를 검증한다.**

```python
def test_cancelled_job_cannot_publish(job_repo, recording):
    job = job_repo.enqueue(recording.id, 'process', None, 'local_only')
    claimed = job_repo.claim()
    assert claimed.id == job.id
    job_repo.cancel(job.id)
    result = StageResult(job_id=job.id, generation=job.generation,
                         stage='speech', artifact_path='speech.json', metadata={})
    assert job_repo.commit_stage(result) is False
```

`job_repo`와 `recording` fixture는 임시 DB에 각각 저장소·ready 입력을 만든다. 별도 테스트 프로세스가 30초 대기하게 한 뒤 취소·시간 제한으로 2초 안에 종료되는지 검증한다.

- [x] **Step 2: `uv run pytest tests/test_jobs.py tests/test_process_control.py -q`로 실패를 확인한다.**
- [x] **Step 3: 워커 singleton lock, 트랜잭션 claim, heartbeat와 단계 체크포인트를 구현한다.** 시작 시 `fcntl.flock`으로 데이터 디렉터리의 worker lock을 얻은 프로세스만 이전 running 작업을 interrupted로 전환한다. 완료 artifact는 임시 파일에 쓴 후 rename하고, DB 반영 시 job 상태·취소 여부·recording generation을 다시 확인한다. 재시작은 완료된 마지막 단계 다음부터 진행한다.

```python
child = subprocess.Popen(command, start_new_session=True,
                         stdout=log_file, stderr=log_file, env=child_env)
os.killpg(child.pid, signal.SIGTERM)
```

실제 종료는 자식 실행 중 취소·시간 제한을 감시한 경우에만 수행하고, 2초 후 남아 있으면 SIGKILL·wait한다. subprocess에는 `shell=True`를 사용하지 않는다. 워커 종료·기록 삭제에도 같은 정리를 적용한다. CLI `worker`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`을 연결한다.

- [x] **Step 4: 워커를 종료·재시작하는 통합 테스트와 위 테스트를 통과시킨다.** 두 번째 워커 시작이 기존 실행 작업을 interrupted로 바꾸지 않고 명확히 종료되는지도 확인한다.
- [x] **Step 5: `git commit -m "feat: run durable cancellable processing jobs"`로 커밋한다.**

### Task 5: 준비된 모델로 로컬 음성 처리

**Files:** Create `engines/{__init__,models,local_speech,local_executor}.py`, `recordings/alignment.py`; create `tests/{test_model_readiness,test_local_speech,test_alignment}.py`; modify `cli.py`.

**Interfaces:** Consumes `Word`, `Turn`, `Speaker`, `SpeechResult`, normalized WAV. Produces `ModelRegistry.require(name: str) -> Path`, `ModelRegistry.prepare(names: list[str]) -> None`, `LocalSpeech.transcribe(path: Path) -> SpeechResult`, `SpeakerSpan(speaker_id: str, start_ms: int, end_ms: int)`, `align_turns(text: str, words: list[Word], speakers: list[SpeakerSpan], offset_ms: int) -> list[Turn]`. `LocalSpeech` takes `vad`, `asr`, `aligner`, `diarizer` objects so tests can inject deterministic responses. Only the executor instantiates actual models.

- [x] **Step 1: 무음에서 ASR·분석을 호출하지 않는 테스트, 단어와 화자의 시간 결합 테스트를 작성한다.**

```python
def test_silence_never_invokes_asr(silence_wav, fake_vad, fake_asr, speech_factory):
    fake_vad.get_speech_timestamps.return_value = []
    speech = speech_factory(vad=fake_vad, asr=fake_asr)
    result = speech.transcribe(silence_wav)
    assert result.no_speech is True
    assert result.turns == []
    fake_asr.generate.assert_not_called()
```

`speech_factory`는 모델 객체를 주입한 `LocalSpeech`를 반환한다. `test_alignment.py`에는 200ms 맞장구, 두 화자가 동시에 활성인 구간, 화자 근거 없는 단어, 입력 청크 경계의 중복 단어를 각각 포함한다. 중복 발언만 제거하고 짧은 별도 발언은 남겨야 한다.

- [x] **Step 2: `uv run pytest tests/test_model_readiness.py tests/test_local_speech.py tests/test_alignment.py -q`로 실패를 확인한다.**
- [x] **Step 3: 사전 준비 CLI와 로컬 어댑터를 구현한다.** `prepare-models`만 Hugging Face 다운로드를 호출한다. 모델별 revision·실제 경로·필수 파일을 `models/manifest.json`에 저장한다. 추론은 로컬 경로를 요구하며 자식 환경에 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`을 설정한다. 누락 파일은 `model_not_ready`로 끝낸다. `doctor`는 준비 상태를 읽기만 한다.

```python
from mlx_audio.stt import load as load_stt
asr = load_stt(str(asr_path))
text = asr.generate(str(chunk_path), language='Korean').text
del asr
aligner = load_stt(str(aligner_path))
aligned = aligner.generate(audio=str(chunk_path), text=text, language='Korean')
```

모델은 Qwen3-ASR-1.7B-8bit, Qwen3-ForcedAligner-0.6B-8bit, Silero VAD와 MLX Nemotron 3를 준비한다. 아래 Sortformer 변환 경로는 비교용 참고이며 기본 모델 준비에 포함하지 않는다. 변환은 모델 준비 작업이며 음성 처리 중 실행하지 않는다.

```bash
uv sync --extra speech
uv run python -m mlx_audio.vad.models.sortformer.convert \
  --nemo-path nvidia/diar_streaming_sortformer_4spk-v2.1 \
  --output-dir models/sortformer-v2.1
```

VAD는 `min_speech_duration_ms=100`, `speech_pad_ms=200`, `return_seconds=True`로 호출해 짧은 맞장구를 일괄 제거하지 않게 한다. 음성 범위를 최대 30초 창으로 나누고 인접 창의 800ms를 겹친다. 원본 오프셋을 유지한다. 동일 시간·동일 문자열의 겹친 경계 단어만 제거한다. ASR 원문과 정렬 단어의 대응이 깨지면 원문을 보존하고 검토 표시를 남긴다. Sortformer는 전체 파일에 한 번 `diarizer.generate_stream(str(path), chunk_duration=5.0)`을 호출해 상태를 유지한다. 화자 배정은 시간 교집합을 기준으로 하고, 경쟁하는 두 화자가 있으면 overlap, 근거가 없으면 unknown_speaker를 표시한다. 원본 엔진 응답도 따로 보존한다. 큰 모델은 순차 로드·해제하고 단계 자식 종료로 GPU 메모리를 반환한다.

- [x] **Step 4: 일반 테스트를 통과시킨 뒤 준비된 모델로 짧은 WAV의 실행·형식 smoke 검증을 수행한다.** 이 실행은 준비 상태 확인이며 한국어 정확도 검증 결과로 보고하지 않는다. Whisper large-v3 비교 어댑터는 같은 `SpeechResult` 계약을 사용하고 평가 명령에서만 선택한다. Sortformer가 실제 한국어 품질 기준을 충족하지 못하면 pyannote 비교 어댑터를 같은 경계에 추가한다. 다운로드 조건 수락을 대신 수행하거나 토큰을 만들지 않는다.
- [x] **Step 5: `git commit -m "feat: process speech with prepared local models"`로 코드·모델 준비 설명을 커밋한다. 모델 파일은 제외한다.**

### Task 6: 외부 음성 API와 긴 입력의 화자 연결

**Files:** Create `engines/cloud_speech.py`, `recordings/cloud_audio.py`, `tests/{test_cloud_speech,test_cloud_audio}.py`.

**Interfaces:** Produces `CloudSpeech.transcribe(path: Path) -> SpeechResult`, `prepare_uploads(path: Path, max_bytes: int = 24_000_000) -> list[AudioPart]`, `AudioPart(path: Path, offset_ms: int, overlap_ms: int)`. `CloudSpeech` takes an injected OpenAI client for tests. Uses Task 5's `SpeakerSpan` and source offset convention.

- [x] **Step 1: diarized_json 정규화·오프셋·이름 역전·불확실한 연결을 검증한다.**

```python
def test_unknown_chunk_speaker_is_not_forced_to_first_person(cloud_speech_with_parts):
    engine, path = cloud_speech_with_parts
    result = engine.transcribe(path)
    unmatched = next(turn for turn in result.turns if turn.text_original == '추가 발언')
    assert unmatched.speaker_id is None
    assert 'unknown_speaker' in unmatched.review_flags
```

fixture는 두 API 응답에서 두 번째 응답의 A/B 순서를 뒤집고, 참조에 일치하지 않은 세 번째 음성을 추가한다. 별도로 25MB를 넘는 입력이 한 번의 요청으로 전송되지 않는지 검사한다.

- [x] **Step 2: `uv run pytest tests/test_cloud_speech.py tests/test_cloud_audio.py -q`로 실패를 확인한다.**
- [x] **Step 3: 16kHz mono·24kbps MP3로 인코딩한 뒤 실제 크기를 검사한다.** 단일 파일이 제한 안이면 한 번 전송한다. 초과하면 음성 경계 근처에서 나누고 원본 오프셋·겹침을 보존한다. 30초 초과 입력은 아래 요청을 사용한다.

```python
with part.path.open('rb') as audio:
    response = client.audio.transcriptions.create(
        model=settings.openai_speech_model,
        file=audio,
        response_format='diarized_json',
        chunking_strategy='auto',
    )
```

초기 모델 기본값은 `gpt-4o-transcribe-diarize`다. `prompt`나 지원하지 않는 단어별 timestamp 옵션을 보내지 않는다. 청크 분할 시 첫 응답에서 확보한 2~10초의 겹치지 않는 단독 발화로 화자 참조를 만든다. 후속 요청의 `known_speaker_names`에는 기록 내부의 안정적인 ID를 사용하고 `known_speaker_references`에 짧은 data URL을 전달한다. 참조가 없거나 대응이 불확실하면 알 수 없는 화자로 남긴다. 새 외부 결과는 전사·화자를 함께 생성하며 로컬 화자 번호와 무조건 결합하지 않는다.

외부 SDK의 자동 재시도는 끄고 Task 7의 정책 한 곳에서만 재시도한다. 서버에 필요한 오류 코드만 보관하고 비밀·전체 SDK 오류 본문은 저장하지 않는다. `no_speech`는 유효한 발언이 없는 결과에만 설정한다.

- [x] **Step 4: API mock 테스트와 실제 FFmpeg 인코딩 크기 테스트를 통과시킨다.** API 키가 구성된 경우에만 짧은 실제 요청으로 계정 지원 여부를 확인한다. 키가 없으면 실제 요청 미실행을 검증 보고서에 기록한다.
- [x] **Step 5: `git commit -m "feat: add diarized cloud transcription fallback"`로 커밋한다.**

### Task 7: 로컬 우선 선택·대체 경로·외부 전송 차단

**Files:** Create `engines/{policy,retries}.py`, `tests/test_engine_policy.py`; modify `config.py`, `engines/models.py`.

**Interfaces:** Produces `EnginePolicy.execute(stage: Literal["speech", "analysis"], mode: Mode, duration_ms: int, local: Callable[[], T], cloud: Callable[[], T]) -> T`, `QualityProfile(stage: str, status: Literal["unverified", "passed", "failed"], model_revision: str, report_id: str | None)`, `StageUnavailable`, `assert_loopback_endpoint(url: str) -> None`.

`T`는 `policy.py`의 `TypeVar`다. 품질 프로필은 `data/quality-profiles.json`에 atomic write로 저장한다. 모델 revision 또는 Ollama digest가 달라지면 이전 passed 상태를 재사용하지 않는다. Task 12의 실제 보고서 ID가 있는 경우에만 passed·failed 판정을 저장한다.

- [x] **Step 1: 로컬 전용 차단과 단계별 fallback을 검증한다.**

```python
def test_local_only_never_falls_back(policy, failing_local, cloud_spy):
    with pytest.raises(StageUnavailable):
        policy.execute('speech', 'local_only', 60_000, failing_local, cloud_spy)
    cloud_spy.assert_not_called()
```

추가 테스트는 원격 Ollama URL, localhost의 외부 DNS 재지정, 누락 모델과 API 키가 함께 존재하는 경우를 다룬다. 루프백은 `localhost`, `127.0.0.1`, `[::1]`만 허용하고 실제 연결 대상도 루프백이어야 한다. 요청 리다이렉트는 따르지 않는다.

- [x] **Step 2: `uv run pytest tests/test_engine_policy.py -q`로 실패를 확인한다.**
- [x] **Step 3: 선택 규칙을 구현한다.** local_only는 준비된 로컬만, api는 설정된 API만 사용한다. auto는 평가 passed인 로컬을 우선 사용하고 실패·시간 초과·출력 오류 때 해당 단계의 API로 전환한다. failed인 조합은 API가 있으면 API를 선택한다. unverified는 준비된 로컬을 먼저 실행하되 처리 이력과 화면에 미검증 표시를 남긴다. 어떤 경우에도 평가가 실행되지 않은 모델을 passed로 저장하지 않는다. API가 없는 실패 상태는 명확한 준비·재시도 안내로 끝낸다.

```python
def stage_timeout_seconds(stage, duration_ms):
    seconds = duration_ms / 1000
    return max(300, seconds * 0.25) if stage == 'analysis' else max(180, seconds * 0.5)
```

HTTP 429, 5xx, 네트워크 오류만 최대 두 번 재시도하고 Retry-After가 있으면 적용한다. 취소 신호를 확인할 수 있게 긴 대기 대신 짧은 대기 조각을 사용한다. 401·403·입력 4xx는 반복하지 않는다. 원격 처리 후 응답을 잃은 재시도는 중복 비용 가능성을 job event에 기록한다. 구조 오류는 한 번의 교정 시도 후 정책으로 넘긴다. 전환 이유·실행 장소·모델을 결과 metadata에 남긴다.

- [x] **Step 4: 주입된 sleep·HTTP 클라이언트로 시도 횟수와 취소를 검증한다.** 단위 테스트는 실제 긴 대기나 외부 요청을 사용하지 않는다.
- [x] **Step 5: `git commit -m "feat: enforce local first engine selection policies"`로 커밋한다.**

### Task 8: 원문에 근거한 대화 분석과 전체 처리 연결

**Files:** Create `analysis/{__init__,grounding,chunking,prompts,service,repository}.py`, `engines/{local_analysis,cloud_analysis}.py`, `migrations/003_analysis.sql`, `tests/{test_grounding,test_analysis,test_pipeline}.py`; modify `engines/local_executor.py`, `jobs/runner.py`.

**Interfaces:** Produces `validate_grounding(body: AnalysisBody, transcript: Transcript) -> None`, `AnalysisService.generate(transcript_id: str, mode: Mode, producer_job_id: str | None = None) -> AnalysisVersion`, `AnalysisRepository.current(recording_id: str) -> AnalysisVersion | None`, `AnalysisEngine.generate(transcript: Transcript) -> AnalysisBody`, `Pipeline.run(job: Job) -> None`. `AnalysisEngine`은 `analysis/service.py`의 프로토콜이며 두 분석 어댑터는 같은 `generate` 계약을 구현한다. `Pipeline`은 `jobs/runner.py`에 둔다.

- [x] **Step 1: 존재하지 않는 근거와 입력 밖의 담당자 거부, 분석 중 편집, 긴 질문·답변 문맥 보존을 검증한다.**

```python
def test_invented_citation_is_rejected(analysis_body, transcript):
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    analysis_body.overview.summary.evidence_turn_ids = ['missing-turn']
    with pytest.raises(GroundingError, match='unknown_turn'):
        validate_grounding(analysis_body, transcript)
```

fixture `analysis_body`는 존재하는 발언 ID만 인용한 `AnalysisBody`, `transcript`는 Task 3의 두 발언 전사다. `test_pipeline.py`는 speech 성공·analysis 실패에서도 전사가 조회되는지, no_speech에서 분석을 실행하지 않는지 검사한다.

- [x] **Step 2: `uv run pytest tests/test_grounding.py tests/test_analysis.py tests/test_pipeline.py -q`로 실패를 확인한다.**
- [x] **Step 3: 분석 프롬프트 v1·로컬 및 외부 어댑터·근거 검증을 구현한다.** 프롬프트는 한국어로 원문의 부정·수치·조건 보존, 추정한 사람·역할·기한 생성 금지, 근거 발언 ID 필수, 해당 항목이 없으면 빈 배열·null 반환을 명시한다. 전사에 포함된 지시문은 분석할 대화 내용으로 취급하며 실행할 지시로 따르지 않는다. 시스템 도구·웹 검색은 연결하지 않는다.

```python
response = http_client.post(
    '/api/chat',
    json={'model': settings.ollama_model, 'messages': messages,
          'format': AnalysisBody.model_json_schema(), 'stream': False,
          'keep_alive': 0, 'options': {'num_ctx': 32768, 'temperature': 0}},
)
response.raise_for_status()
body = AnalysisBody.model_validate_json(response.json()['message']['content'])
```

Ollama 기본값은 설치된 `gpt-oss:20b`이고 루프백 endpoint만 사용한다. 분석 실패·취소에서도 모델 해제를 시도한다. OpenAI 기본값은 `gpt-5-mini`; Responses의 `text.format` JSON Schema 또는 `responses.parse`로 같은 계약을 요청한다. SDK 파싱 후에도 발언 ID, 화자 ID, 주제 시간 범위, 비어 있는 근거를 검증한다. 분석 원문과 원래 전사는 서로 덮어쓰지 않는다.

입력은 UTF-8 기준 16,000바이트 안의 발언 묶음으로 나누고 마지막 두 발언을 다음 묶음에 함께 제공한다. 시스템 프롬프트와 출력 여유를 포함해 32,768 컨텍스트 한도를 넘지 않는지 확인한다. 한 발언 자체가 길면 문자 경계에서 나누되 동일 발언 ID를 유지한다. 구간 결과를 병합할 때 근거 집합·내용이 같은 항목만 중복 제거하고, 최종 정리에서도 원래 발언 ID를 보존한다. 큰 입력은 여러 요약을 한 번에 무제한으로 넣지 않고 같은 크기로 재귀 병합한다.

`Pipeline`은 prepare → speech → transcript 저장 → analysis 저장 순서로 연결한다. 생성 전사와 분석에 실제 job ID를 producer_job_id로 전달한다. 분석 저장에도 unique 제약을 적용하고, 단계 체크포인트와 결과 반영을 같은 트랜잭션으로 완료한다. 결과 저장 직후 워커가 중단되어도 재실행으로 동일 버전을 중복 생성하지 않는 테스트를 추가한다. 분석은 시작 시 고정한 전사 버전을 참조한다. 뒤늦은 결과는 새로운 current 전사나 수정본을 덮어쓰지 않는다. 단계 시간은 정책의 제한을 사용한다.

- [x] **Step 4: Python 분석·파이프라인 테스트와 실제 Ollama의 짧은 구조화 응답 smoke 검증을 수행한다.** JSON 성공과 근거 ID 존재 여부를 사람이 검토하는 의미 정확도 검증과 구분한다.
- [x] **Step 5: `git commit -m "feat: generate grounded versioned conversation records"`로 커밋한다.**

### Task 9: 기록 조회·재처리·삭제·내보내기 API

**Files:** Create `exports.py`, `settings_api.py`, `recordings/deletion.py`, `migrations/004_deletion.sql`, `tests/{test_recording_api,test_exports,test_deletion,test_settings}.py`; modify `recordings/api.py`, `app.py`, `jobs/runner.py`.

**Interfaces:** Produces `export_json(recording_id: str, transcript_id: str, analysis_id: str | None) -> dict`, `export_markdown(recording_id: str, transcript_id: str, analysis_id: str | None) -> str`, `DeletionService.request(recording_id: str) -> None`, `cleanup_pending() -> int`. API responses use Pydantic models: `RecordingList(items: list[Recording])`, `RecordingDetail(recording: Recording, transcript: Transcript | None, analysis: AnalysisVersion | None, analysis_stale: bool, job: Job | None)`, `Readiness(mode: Mode, engines: list[dict])`.

- [x] **Step 1: 저장부터 내보내기까지의 API 연결, 음성 Range, 비밀 제외·삭제 경쟁을 검증한다.**

```python
def test_export_does_not_leak_server_configuration(client_with_record):
    client, record_id = client_with_record
    response = client.get(f'/api/recordings/{record_id}/export?format=json')
    assert response.status_code == 200
    data = response.json()
    assert data['schema_version'] == 1
    assert 'OPENAI_API_KEY' not in response.text
    assert 'raw_artifact' not in response.text
```

테스트 설정에는 `OPENAI_API_KEY`에 해당하는 고유한 canary 비밀과 임시 디렉터리 절대 경로를 넣고, 설정 응답·오류·내보내기·수집된 로그 어디에도 값이 없는지 확인한다. 분석 중 전사를 수정하면 detail의 `analysis_stale`가 true여야 한다. 삭제 직전에 끝난 자식 결과가 파일·DB를 다시 생성하지 않는지도 검증한다.

- [x] **Step 2: `uv run pytest tests/test_recording_api.py tests/test_exports.py tests/test_deletion.py tests/test_settings.py -q`로 실패를 확인한다.**
- [x] **Step 3: 입력 준비 완료 시 process 작업을 하나만 등록하고 아래 경로를 연결한다.**

| Method / Path | 입력과 결과 |
| --- | --- |
| `GET /api/recordings` | 생성 시각 역순 목록 |
| `GET /api/recordings/{id}` | RecordingDetail, 분석의 기준 전사와 현재 전사의 차이 포함 |
| `GET /api/recordings/{id}/audio` | 브라우저 재생용 원본 또는 파생 음성. Range 요청 206, 잘못된 범위 416 |
| `POST /api/recordings/{id}/process` | `{mode}` → 새 process Job, 수정본 보존 |
| `POST /api/recordings/{id}/analyze` | `{mode, transcript_id}` → 해당 버전에 고정한 analyze Job |
| `GET /api/recordings/{id}/export` | `format=json|markdown`, 선택적 버전 ID. 서로 다른 전사 기준의 분석을 섞지 않음 |
| `DELETE /api/recordings/{id}` | tombstone·generation 증가·활성 작업 취소 후 202 |
| `GET /api/settings` | 실행 모드, 모델 준비 여부·미검증 여부, API 구성 유무. 비밀 값 제외 |
| `PATCH /api/settings` | `{mode}` 저장. API 키를 웹 API로 받거나 반환하지 않음 |

삭제 요청 직후 모든 조회는 404다. 워커는 활성 자식을 종료한 뒤 원본·파생 파일·전사·분석을 지우고 마지막에 DB 행을 cascade 삭제한다. 대기 중인 삭제는 워커 재시작 시에도 완료한다. `deleted_at`과 generation 검사를 모든 결과 반영에 적용한다.

내보내기는 버전 ID를 먼저 고정해 읽고, 현재 화자 이름을 ID로 해석한다. JSON에는 `schema_version=1`, 기록 정보, 전사·분석 버전, 처리 이력을 포함하고 내부 경로·오류 원문·비밀을 제외한다. Markdown에는 시간과 화자를 넣고 의미 없는 빈 결정·할 일 표는 생략한다. 파일명은 안전한 문자와 기록 ID로 생성한다.

로컬 앱의 기본 Host와 변경 요청의 Origin을 검사한다. 허용 Origin은 개발의 `http://localhost:5173`, `http://127.0.0.1:5173`과 실제 서버의 루프백 Origin이다. 임의의 외부 Origin·`Origin: null` 요청을 거부하고 wildcard CORS를 설정하지 않는다. CLI의 Origin 없는 루프백 요청은 허용한다.

- [x] **Step 4: HTTP 상태·Range·내보내기 버전 일치·삭제 복구·비밀 제외 테스트를 통과시킨다.**
- [x] **Step 5: `git commit -m "feat: expose recording history exports and lifecycle APIs"`로 커밋한다.**

### Task 10: 웹 목록·파일 가져오기·마이크 녹음

**Files:** Create `web/{package.json,package-lock.json,index.html,vite.config.ts,tsconfig.json,tsconfig.app.json,tsconfig.node.json}`, `web/src/{main.tsx,App.tsx,styles.css}`, `web/src/lib/{api.ts,types.ts,schema.d.ts}`, `web/src/features/recordings/{RecordingList,UploadDialog,Recorder}.tsx`, `web/src/features/recordings/{useRecorder.ts,Recorder.test.tsx,UploadDialog.test.tsx}`, `web/src/test/{setup.ts,media.tsx}`.

**Interfaces:** Consumes Task 9 OpenAPI contracts. Produces `api.listRecordings()`, `api.upload(file: File)`, `api.createDraft(title: string)`, `api.putChunk(id: string, sequence: number, body: Blob)`, `api.finalize(id: string, lastSequence: number)`, `useRecorder()` with `state`, `elapsedMs`, `level`, `start()`, `stop()`, `error`. IDs and detail shapes are imported from generated OpenAPI types; do not maintain a second handwritten server contract.

- [x] **Step 1: 마지막 dataavailable가 도착한 뒤 업로드·finalize가 완료되는 순서를 검증한다.**

```tsx
it('waits for the final audio chunk before finalizing', async () => {
  const capture = await renderRecorderWithFakeMedia()
  await capture.start()
  capture.emitChunk(new Blob(['first']))
  await capture.stop()
  expect(capture.api.finalize).not.toHaveBeenCalled()
  capture.emitFinalChunk(new Blob(['last']))
  capture.emitStopped()
  await waitFor(() => expect(capture.api.finalize).toHaveBeenCalledWith('rec-1', 1))
})
```

테스트 helper `renderRecorderWithFakeMedia()`는 `web/src/test/media.tsx`에 만들며 실제 MediaRecorder와 동일한 dataavailable·stop 이벤트 순서를 제어한다. helper의 `stop()`은 종료 요청만 보내고, 마지막 이벤트는 테스트가 `emitFinalChunk()`와 `emitStopped()`로 따로 발생시킨다. 추가 테스트는 권한 거부, 중복 stop, 중간 업로드 실패, 2시간 자동 종료를 다룬다.

- [x] **Step 2: 테스트 의존성을 설치한 뒤 `npm --prefix web run test -- --run src/features/recordings/Recorder.test.tsx`로 미구현 녹음 화면의 실패를 확인한다.**
- [x] **Step 3: React·TypeScript·Vite 셸과 입력 화면을 구현한다.** 런타임 의존성은 `react`, `react-dom`, `@tanstack/react-virtual`; 개발 의존성은 Vite·React 플러그인·TypeScript·React 타입·Vitest·jsdom·Testing Library·user-event·Playwright·openapi-typescript다. `typecheck`, `build`, `test`, `e2e` 스크립트를 정의한다. Vite는 `/api`를 루프백 FastAPI에 proxy한다.

`schema.d.ts`는 Task 12의 `meetinglog schema` 출력에 `openapi-typescript`를 적용해 생성한다. 작업 중에는 동일한 `create_app().openapi()`를 사용한다. 입력 화면의 미디어 MIME은 `MediaRecorder.isTypeSupported`로 선택한다. 기본 시도 순서는 WebM/Opus, WebM, MP4이며 모두 미지원이면 파일 가져오기 안내를 보여준다.

```ts
let uploads = Promise.resolve()
let nextSequence = 0
recorder.addEventListener('dataavailable', (event) => {
  if (event.data.size === 0) return
  const sequence = nextSequence++
  uploads = uploads.then(() => api.putChunk(recordingId, sequence, event.data))
})
recorder.addEventListener('stop', async () => {
  await uploads
  await api.finalize(recordingId, nextSequence - 1)
})
```

실제 handler에는 실패 상태 전환·재시도 한도·정리 finally를 추가한다. 업로드 큐가 실패하면 finalize하지 않는다. 메모리의 미전송 Blob이 32MB를 넘으면 녹음을 중지하고 저장 실패를 알린다. `start(5000)`으로 주기 전송하고, 종료는 마지막 dataavailable와 업로드 ACK를 기다린다. 정상·오류 종료 모두 마이크 track과 AudioContext를 해제한다. 입력 레벨과 경과 시간, 현재 마이크 녹음임을 표시하고 1분 전 종료 안내를 제공한다.

화면은 한국어의 간결한 도구 UI로 만든다. 목록에는 제목·길이·작성 시각·처리 상태를 보여주고, 빈 목록은 녹음·파일 입력 행동을 바로 제공한다. 파일 업로드는 실제 전송 진행을 표시한다. 예상 완료 시간을 측정 없이 만들어 보여주지 않는다.

- [x] **Step 4: 녹음·업로드 테스트와 `npm --prefix web run typecheck`, `npm --prefix web run build`를 통과시킨다.** Web Audio 레벨 측정이 중지 후 계속 실행되지 않는지도 검사한다.
- [x] **Step 5: `git commit -m "feat: capture and import audio in the local web app"`로 커밋한다.**

### Task 11: 대화 상세·전사 편집·분석 근거·설정 화면

**Files:** Create `web/src/features/detail/{RecordingDetail,TranscriptPane,AnalysisPane,AudioPlayer,SpeakerEditor}.tsx`, `web/src/features/detail/{useRecording.ts,RecordingDetail.test.tsx}`, `web/src/features/settings/{SettingsPage.tsx,SettingsPage.test.tsx}`, `web/src/test/detail.tsx`; modify `web/src/{App.tsx,styles.css}`, `web/src/lib/api.ts`.

**Interfaces:** Consumes `RecordingDetail`, `Readiness` and versioned edit endpoints. Produces `AudioPlayer.seek(ms: number)`, detail's `selectedTurnId`, edit requests with `base_version_id`, analysis requests with `transcript_id`. `useRecording(id: string)` returns `detail`, `refresh`, `isLoading`, `error` and aborts obsolete polling requests.

- [x] **Step 1: 발언→음성 시각 이동, 근거→발언 이동, stale 분석 표시, 409 편집 충돌을 검증한다.**

```tsx
it('opens the cited turn without replacing the transcript', async () => {
  const view = await renderDetailWithFixture()
  await userEvent.click(view.getByRole('button', {name: '00:01 화자 A 발언 듣기'}))
  expect(view.getByTestId('turn-t1')).toHaveAttribute('aria-current', 'true')
  expect(view.audio.currentTime).toBe(1.25)
})
```

helper `renderDetailWithFixture()`를 `web/src/test/detail.tsx`에 만들고 t1의 시작 시각은 1,250ms로 고정한다. 충돌 테스트는 409 후 편집 문안을 보존하면서 최신 전사 조회를 제안하는지 확인한다. AI가 만든 이름·날짜가 없는 결과를 화면에서 임의로 보충하지 않는지도 검사한다.

- [x] **Step 2: `npm --prefix web run test -- --run src/features/detail/RecordingDetail.test.tsx src/features/settings/SettingsPage.test.tsx`로 실패를 확인한다.**
- [x] **Step 3: 넓은 화면은 전사와 분석을 병렬 배치하고 좁은 화면은 탭으로 전환한다.** 플레이어는 원본 시간축을 사용하고, 가상 목록으로 긴 전사의 DOM 수를 제한한다. 근거 이동은 가상 목록의 해당 인덱스를 먼저 보이게 한 뒤 선택·재생 위치를 갱신한다. 발언 수정은 원문과 수정본을 구분하고 화자 이름·역할 편집을 제공한다.

```ts
await api.editTranscript(recordingId, {
  base_version_id: detail.transcript.id,
  changes: [{turn_id: turnId, text: editedText}],
})
await refresh()
```

분석은 overview, topics, question_answers, agreements, open_questions, actions를 렌더링한다. 근거는 발언 시각과 화자를 표시한 키보드 접근 가능한 버튼으로 제공하며 내부 ID는 화면에 노출하지 않는다. 빈 합의·할 일 목록은 과장된 빈 카드로 채우지 않는다. 미확인 화자·겹침·불명확 구간에는 검토 표시를 제공한다. 내용은 React 텍스트로 렌더링하고 모델 출력을 HTML로 실행하지 않는다.

분석 실패에도 전사와 음성을 사용할 수 있게 하며 단계별 재시도를 제공한다. 변경 후 이전 분석 표시와 다시 분석 동작을 연결한다. 설정은 auto/local_only/api, 엔진 준비·미검증·외부 구성 상태를 보여준다. 키 입력 대신 서버의 `.env` 설정 방법을 안내한다. 엔진 ID와 전환 이력은 상세 정보에서 확인한다. 모든 입력에 label, 명확한 focus, 충분한 대비를 적용하고, 상태 변화는 aria-live로 전달한다.

- [x] **Step 4: 컴포넌트 테스트·typecheck·build를 통과시키고 1440×900, 1280×800, 390×844 화면에서 잘림과 재생·편집·근거 이동을 확인한다.**
- [x] **Step 5: `git commit -m "feat: review edit and export grounded conversation records"`로 커밋한다.**

### Task 12: 실제 평가·브라우저 통합 검증·실행 문서

**Files:** Create `backend/src/meetinglog/evaluation.py`, `evaluation/{schema.json,corpus.example.json,README.md}`, `tests/{__init__,test_evaluation,e2e_server}.py`, `web/{playwright.config.ts,e2e/recording.spec.ts}`, `scripts/{dev,check}.sh`, `docs/verification/2026-10-16-local-mvp.md`; modify `cli.py`, `README.md`, `web/package.json`.

**Interfaces:** Produces CLI commands `meetinglog doctor`, `meetinglog prepare-models`, `meetinglog serve`, `meetinglog worker`, `meetinglog schema`, `meetinglog evaluate --manifest PATH --mode MODE --output PATH`; produces evaluation JSON with `id`, `status`, `model_revisions`, `cer`, `der`, `duration_ms`, `elapsed_ms`, `peak_memory_bytes`, `human_review`, `limitations`. `id`는 보고서 UUID이고, 측정하지 않은 수치 필드는 null을 허용한다.

- [x] **Step 1: 정답이 없거나 불충분한 평가를 passed로 기록하지 않는 테스트를 작성한다.**

```python
def test_missing_reference_cannot_verify_local_quality(tmp_path):
    manifest = tmp_path / 'corpus.json'
    manifest.write_text('{"schema_version":1,"items":[]}', encoding='utf-8')
    result = evaluate_manifest(manifest, mode='local_only')
    assert result.status == 'insufficient_evidence'
    assert result.cer is None
    assert result.der is None
```

`evaluate_manifest(path: Path, mode: Mode) -> EvaluationReport`와 `EvaluationReport`는 `evaluation.py`에 정의한다. CER 정규화가 숫자·부정 표현을 지우지 않는 테스트와, human_review가 미완료이면 분석 품질 passed를 금지하는 테스트도 추가한다.

- [x] **Step 2: `uv run pytest tests/test_evaluation.py -q`로 실패를 확인한다.**
- [x] **Step 3: 평가 manifest와 계산기를 구현한다.** manifest 항목은 `id`, `audio_path`, `reference_transcript_path`, `reference_rttm_path`, `split`(`quality` 또는 `performance`), `human_review_path`를 포함한다. 경로는 manifest 기준으로 해석한다. 실제 자료가 없는 예시는 `{"schema_version":1,"items":[]}`이며 실행 시 부족한 증거 상태를 반환한다. 평가용 정답·음성은 Git에 넣지 않는다.

```python
def normalize_reference(text):
    normalized = unicodedata.normalize('NFC', text)
    return ''.join(char for char in normalized
                   if not char.isspace() and not unicodedata.category(char).startswith('P'))
```

CER은 정규화한 정답·인식문에 `jiwer.cer`를 적용하고, DER은 `DiarizationErrorRate(collar=0, skip_overlap=False)`를 사용한다. 30분 이상의 정답 구간과 별도 60분 연속 녹음이 있어야 설계의 품질·성능 판정을 완료한다. 무음 정답은 CER 분모에 억지로 넣지 않고 별도 무음 실패 항목으로 보고한다. 모델 준비 시간·업로드 시간은 구분하되, 실제 처리 시간에는 디코딩·모델 로드·전사·화자 구분·분석을 포함한다. 워커 자식과 별도 Ollama 프로세스의 메모리 측정 범위를 구분하고, 측정하지 못한 값은 0 대신 null과 이유를 기록한다. 실제 자료가 부족하면 자동 테스트가 통과해도 모델 품질은 미검증 상태다. 평가 실행 전에는 `uv sync --extra speech --extra evaluation`로 평가 의존성도 준비한다.

human_review에는 주제·질문과 답변·수치·부정 표현의 보존, 실제 근거, 추정한 결정·담당자·기한 유무를 기록한다. 음성의 성격에 맞는 정답 자료가 확보된 후 같은 구간에서 Qwen·Whisper·API를 비교한다. 화자 결과가 기준에 못 미치면 준비 조건이 충족된 pyannote를 비교하고, 모든 조합과 실패를 보고서에 남긴다. 측정 없이 더 좋다고 선택하지 않는다.

- [x] **Step 4: 브라우저 통합 테스트를 작성하고 전체 검증을 실행한다.** `tests/e2e_server.py`는 실제 입력·DB·작업 API에 테스트 전용 고정 엔진을 주입한다. 이 주입은 테스트 모듈 안에서만 정의하며 제품 설정에는 가짜 엔진 옵션을 노출하지 않는다. Playwright는 파일 입력→전사 확인→화자 수정→다시 분석→근거 이동→내보내기→새로고침 후 보존을 검증한다. 마이크는 Chromium fake media device로 녹음 시작·종료·청크 순서를 확인한다. 모델 정확도 검증과 브라우저 검증을 보고서에서 구분한다.

```bash
uv run ruff check backend tests
uv run ruff format --check backend tests
uv run pytest -m 'not live' -q
npm --prefix web run typecheck
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run e2e
git diff --check
```

`scripts/check.sh`는 위 명령을 순서대로 실행하고 첫 실패에 중단한다. `scripts/dev.sh`는 API·워커·Vite를 시작하고 Ctrl+C 때 자신이 시작한 PID와 자식만 종료한다. 공유 Ollama 서버를 종료하거나 `kill 0`를 사용하지 않는다. CLI schema 명령은 OpenAPI JSON만 stdout에 출력하며 모델·워커를 실행하지 않는다.

README에는 아래 실행 순서, 필수 준비, API 키 선택 설정, 데이터 위치, 취소·재처리, 로컬 전용 동작, 측정 결과의 한계를 적는다.

```bash
uv sync --extra speech
npm --prefix web ci
uv run meetinglog doctor
uv run meetinglog prepare-models
bash scripts/dev.sh
```

실제 한국어 자료와 API 키가 준비된 경우만 해당 live 검증을 실행한다. 없는 경우 수행하지 않은 검증을 보고서의 limitations에 적고, 품질 목표 달성이나 외부 연결 성공을 주장하지 않는다. 중간 모델 출력·화면 캡처·검증 로그는 개인 음성과 비밀이 없는 범위로 남긴다.

- [x] **Step 5: `git commit -m "test: verify local recording workflow and document quality evidence"`로 커밋한다.** 코드 동작·브라우저 동작·실제 모델 품질의 결과를 나누어 최종 보고한다. 실행 지침, 실제 통과한 명령, 미검증 항목을 사용자가 재현할 수 있게 제공한다.

## 설계 요구사항 대응표

| 설계 항목 | 구현·검증 작업 |
| --- | --- |
| 1–2. 로컬 웹, 한국어 1:1, 로컬 우선 | Tasks 1, 5, 7, 10, 12 |
| 3. 녹음·파일·조회·수정·분석 흐름 | Tasks 2, 3, 8, 9, 10, 11 |
| 4. 원문 보존·근거·미확인 화자·빈 결과 | Tasks 3, 5, 8, 11, 12 |
| 5. HTTP·워커·SQLite·로컬 파일 분리 | Tasks 1, 2, 4, 8 |
| 6. 전처리·화자 연결·모델 준비·API·timeout | Tasks 2, 4, 5, 6, 7 |
| 7. 구조화 기록과 긴 입력 병합 | Tasks 1, 8, 9, 12 |
| 8. 버전·CAS 편집·stale·삭제·내보내기 | Tasks 3, 8, 9, 11 |
| 9. 중단 복구·재시도·취소·메모리 | Tasks 4, 5, 7, 9, 12 |
| 10. 실제 평가와 기능 검증의 구분 | Tasks 5, 6, 8, 12 |
| 11. 실행 가능한 첫 릴리스 | Tasks 9, 10, 11, 12 |

## 실행 전 확인할 공식 자료

외부 예제는 2026-10-16 확인 기준이다. 실행 중 버전 차이를 발견하면 고정한 패키지의 공식 인터페이스를 다시 확인하고, 제품 계약은 유지한 채 어댑터를 수정한다.

- [MLX Qwen3-ASR·ForcedAligner 사용법](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/models/qwen3_asr/README.md)
- [MLX Sortformer 변환·상태 유지 사용법](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/vad/models/sortformer/README.md)
- [MLX Silero VAD](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/vad/models/silero_vad/README.md)
- [Ollama Chat API](https://docs.ollama.com/api/chat)
- [Ollama 구조화 출력](https://docs.ollama.com/capabilities/structured-outputs)
- [OpenAI 전사·화자 구분](https://developers.openai.com/api/docs/guides/speech-to-text)
- [OpenAI 구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

## 실행 방법과 검토 상태

이 계획은 사용자의 맥북 로컬 구현 진행 지시에 따라 직접 실행했다. 구현·검증 결과와 실제 품질의 한계는 [검증 보고서](../../verification/2026-10-16-local-mvp.md)에 기록한다.

- **직접 실행(추천):** 현재 세션에서 순서대로 구현하고 마지막에 전체 변경을 검토한다. 열두 작업이 같은 데이터 계약과 버전 관리에 연결되어 있어 맥락을 유지하기 쉽다.
- **하위 에이전트 실행:** 작업별 구현·검토를 분리한다. 새 실행·검토 맥락이 반복되어 비용이 늘 수 있으며, 사용자 선택 후 해당 워크플로를 적용한다.

현재는 직접 실행 방식으로 작업했다. 마지막 전체 코드 검토는 executing-plans 스킬의 필수 독립 검토 절차를 따른다. 위임 시 원래 `aidlc` 실행 규칙과 읽기 전용 검토 지침을 함께 전달한다.
