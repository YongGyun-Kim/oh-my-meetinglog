# 맥북·아이폰 웹에서의 녹음과 음성 처리 적용성

확인일: 2026-10-16. 범위는 기존 [Plaud 전처리 조사](2026-10-16-plaud-audio-preprocessing.md)와 [모델 후보](2026-10-16-audio-model-candidates.md)를 맥북·아이폰 웹에서 사용할 수 있는지 검토하는 것이다. 제품 구현이나 모델 채택 결정은 아니다.

## 1. 판단과 검증 상태

**두 기기에서 웹으로 녹음·파일 입력·결과 확인을 제공하는 구조는 가능하다.** 무거운 음성 처리는 맥북의 로컬 프로세스에 두는 구성을 우선 검증할 가치가 있다. 아이폰 웹에서 모든 모델을 실행하는 구성은 별도 개발·측정 없이는 지원 가능하다고 확정할 수 없다.

| 구성 | 판단 | 현재 근거 |
| --- | --- | --- |
| 맥북 Chrome → 같은 맥북의 로컬 서버 | 실행 경로가 명확함 | 실제 브라우저 API·합성 톤 녹음·디코딩 확인. 실제 마이크·모델 미검증 |
| 맥북 Safari → 같은 맥북의 로컬 서버 | 공식 웹 API 기준 가능 | 문서 확인. 이 세션에서 Safari 실행 검증은 하지 않음 |
| 아이폰 Safari → 맥북 로컬 서버 | 조건부 가능, 우선 비교할 구성 | 웹 녹음 지원. 아이폰이 신뢰하는 HTTPS·접속 권한·전송 복구 필요. 실기기 미검증 |
| 아이폰 Safari → 외부 처리 서버/API | 웹 제품 구조로 가능 | 맥북 없이 처리할 대안. 로컬 전용 처리와 구분하며 기존 서버 측 API 키 관리 유지 |
| 아이폰 Safari 안에서 전체 처리 | 일부 웹 추론 기술은 존재, 후보 모델 전체는 미검증 | WebGPU/WASM과 웹용 ASR 예제가 있지만 모델·기기별 변환·메모리·품질 측정 필요 |
| 아이폰 잠금·앱 전환 중 연속 녹음 | 첫 웹 버전의 보장 항목으로 확정하지 않음 | 인터럽트·백그라운드 동작에 대한 실기기 검증 필요. 네이티브 수음 대안도 비교 |

**아직 정하지 않은 제품 조건:** 아이폰 단독 처리가 필수인지, 잠금·다른 앱 사용 중 연속 녹음이 필수인지. 아래 제안은 이 조건을 임의로 확정하지 않는다.

## 2. 맥북 Chrome에서 실제 확인한 내용

검증 환경은 제어 가능한 macOS 보고 Chrome 155 브라우저, HTTPS 페이지다. 제품 서버가 아닌 `https://example.com`의 새 탭에서 브라우저 API를 검사했다. 실제 마이크 권한을 요청하거나 주변 대화를 녹음하지 않았다. 종료 시 합성 입력 트랙·AudioContext와 해당 탭을 정리했다.

| 항목 | 관측 결과 | 해석 범위 |
| --- | --- | --- |
| `getUserMedia`, `MediaRecorder` | API 존재 | 실제 마이크 수음·권한 획득을 시험한 결과는 아님 |
| `AudioWorkletNode`, WebAssembly | API 존재 | 전처리 모델 실행이나 처리 속도는 미검증 |
| Screen Wake Lock | API 존재 | 락 획득·장시간 유지 성공을 시험하지 않음 |
| WebGPU | 어댑터 획득, `shader-f16` 기능 확인 | AI 모델 로드·연산·품질 성공을 뜻하지 않음 |
| 오디오 제약 | 잡음 억제·AGC·AEC·채널 수 등의 제약 인식 보고 | 실제 마이크의 적용값·원시 배열 채널을 확인한 결과는 아님 |
| WebM/Opus | 합성 톤을 5개 청크로 녹음하고 결합·디코딩 성공 | 짧은 인코딩 경로의 확인 |
| MP4/AAC | 합성 톤을 5개 청크로 녹음하고 결합·디코딩 성공 | 같은 조건의 다른 인코딩 경로 확인 |

시험은 48kHz AudioContext의 440Hz 톤을 MediaStreamDestination에 연결하고, 각 포맷에서 약 1.25초 동안 `MediaRecorder.start(250)`으로 수행했다. 스피커에는 연결하지 않았다. 디코딩한 파형의 RMS로 실제 신호가 담겼음을 확인했다. 생성 스트림의 스테레오 결과는 **물리적 마이크 채널 수의 측정값이 아니다.**

WebM 디코딩 길이는 약 1.14초, MP4는 약 1.258초였다. 이는 짧은 합성 입력의 결과이며 길이 보존·시작과 끝 발언 보존을 검증한 수치가 아니다. 장시간 녹음의 시각 정렬은 별도 확인한다.

원시 관측값: [Chrome 기능·합성 녹음 결과 JSON](evidence/2026-10-16-macos-chrome-audio-probe.json). iOS 시뮬레이터 도구도 확인했으나 현재는 Command Line Tools만 있고 `simctl`은 사용할 수 없었다. 아이폰 Safari·PWA의 실제 검증 결과는 없다.

## 3. 웹에서 적용 가능한 수음·전처리 범위

### 3.1 녹음과 기존 파일 입력

Safari는 마이크 스트림과 MediaRecorder 기반 녹음을 지원한다. 파일 입력도 표준 파일 선택으로 구현할 수 있다. 브라우저에서 모든 원본 코덱을 즉시 디코딩하지 못하더라도, 파일 바이트를 맥북 서버로 전송해 서버에서 검증·변환하는 경로를 사용할 수 있다. [WebKit MediaRecorder 설명](https://webkit.org/blog/11353/mediarecorder-api/), [MDN 파일 입력](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/file)

Safari를 AAC 전용으로 가정하면 안 된다. Safari 18.4부터 MediaRecorder의 WebM/Opus 지원이 추가됐고, Safari 26에는 ALAC·PCM 지원도 소개됐다. 실행 기기의 `isTypeSupported()`와 실제 인코딩 결과로 선택한다. 지원 보고가 있어도 자원 부족 등으로 녹음에 실패할 수 있다. [WebKit Safari 18.4](https://webkit.org/blog/16574/webkit-features-in-safari-18-4/), [WebKit Safari 26의 Media 업데이트](https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/), [MDN 포맷 지원 검사](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static)

제안하는 협상 순서는 Opus/WebM과 AAC/MP4 중 실제 지원·결과를 확인한 포맷을 선택하고, MIME과 실제 컨테이너를 함께 기록하는 것이다. Safari의 무손실 옵션은 별도 품질·파일 크기 실험으로 둔다. 파일 확장자만 바꾸거나 WAV 지원을 가정하지 않는다.

### 3.2 마이크 전처리 제어

웹에서는 잡음 억제·AGC·AEC와 채널 수를 요청할 수 있다. 다음 세 가지는 서로 다른 결과다.

1. `getSupportedConstraints()` — 브라우저가 해당 제약을 인식하는가.
2. 트랙의 `getCapabilities()` — 선택된 입력이 어떤 설정을 제공하는가.
3. 트랙의 `getSettings()` — 실제로 어떤 값이 선택됐는가.

자료에 없는 설정값은 ‘미확인’으로 남긴다. 브라우저 설정을 껐다는 이유로 기기·OS의 모든 신호 처리가 우회됐다고 주장하지 않는다. [MDN capabilities](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/getCapabilities), [MDN settings](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/getSettings), [W3C Media Capture](https://w3c.github.io/mediacapture-main/)

**Plaud의 마이크 배열과 웹의 `channelCount`는 같은 기능이 아니다.** 내장 물리 마이크마다 독립된 원시 채널을 주는 표준 권한을 확인한 것은 아니다. 스테레오 스트림을 받더라도 배열의 원시 마이크 신호인지 검증해야 한다. 단일 채널을 복제해 공간 정보를 만들 수는 없다.

따라서 재생용 개선본과 ASR용 입력을 나누는 소프트웨어 구조는 재사용할 수 있지만, Plaud의 하드웨어 수음·빔포밍까지 그대로 재현된다고 보지 않는다. 다채널 외장 입력은 실제 노출 채널을 확인한 뒤 별도 비교한다.

### 3.3 어느 쪽에서 전처리할 것인가

웹의 Web Audio·AudioWorklet과 WASM으로 일부 신호 처리를 구현할 수 있다. 다만 초기에는 입력이 훼손되지 않도록 수신 원본을 보존하고, 무거운 개선·분리 모델은 맥북 워커에서 실행하는 구성이 단순하다. 녹음 종료 후 처리라는 기존 요구와도 맞는다.

아이폰 브라우저의 재생용 개선은 선택 기능으로 두고, 그 개선 파형을 전사에 무조건 재사용하지 않는다. 전사·화자 구분의 기준 입력과 개선 입력을 비교하는 원칙은 두 기기에서 동일하다. 실제로는 브라우저가 전달한 신호부터 보존하므로 ‘수신 원본’이지 하드웨어 무가공 신호라는 뜻은 아니다.

## 4. 모델을 웹에서 사용한다는 두 가지 의미

### 웹 화면 + 맥북의 로컬 모델

브라우저는 녹음·파일 전송·진행 상황·재생·전사 편집을 담당하고, 맥북의 Python/네이티브 프로세스가 모델을 실행한다. 기존 Qwen3-ASR·화자 구분기·전처리·Ollama 후보를 같은 서버 인터페이스로 활용할 수 있는 경로다. 모델별 실제 성능은 여전히 미측정이다.

MLX-Audio는 현재 검토한 경로에서 Python 패키지·MLX 기반 실행 환경을 사용한다. 이 패키지를 아이폰 웹 페이지에 설치하는 방식은 아니다. [MLX-Audio 실행 환경](https://github.com/Blaizzy/mlx-audio/blob/main/docs/getting-started/index.md), [패키지 의존성](https://github.com/Blaizzy/mlx-audio/blob/main/pyproject.toml)

### 브라우저 안의 모델

Safari 26부터 macOS·iOS에 WebGPU가 도입됐다. 따라서 ‘아이폰 웹은 GPU 추론 자체가 불가능하다’고 판단하면 안 된다. 다만 후보 모델에 맞는 웹 실행 구현·가중치 변환·지원 연산과 성능 검증이 필요하다. [WebKit의 WebGPU 설명](https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/)

Transformers.js에는 WebGPU 기반 Whisper ASR 예제가 있고 ONNX Runtime Web은 WASM·GPU 실행 경로를 제공한다. 공식 Whisper 예제의 `tiny.en`은 영어용이므로 한국어 결과의 증거가 아니다. 한국어 모델과 전역 화자 구분·장시간 입력·분석까지 같은 기기에서 측정해야 한다. [Transformers.js WebGPU](https://huggingface.co/docs/transformers.js/guides/webgpu), [ONNX Runtime Web](https://onnxruntime.ai/docs/tutorials/web/)

공식 문서 간에도 시점 차이가 있다. ONNX Runtime Web의 브라우저 지원 표는 Safari WebGPU를 미지원으로 표시하는 반면, WebKit의 Safari 26 설명은 ONNX Runtime·Transformers.js 실행을 소개한다. 표 하나로 실행 가능 여부를 단정하지 않고 **고정한 런타임·브라우저·기기에서 모델을 실제 실행**한다. [ORT 지원 표](https://onnxruntime.ai/docs/get-started/with-javascript/web.html)

| 기존 후보 | 맥북 서버 경로 | 아이폰 순수 웹 경로의 현재 판단 |
| --- | --- | --- |
| Qwen3-ASR + ForcedAligner | 기존 MLX 후보로 유지 가능 | 웹 구현·정렬 결합·한국어 속도 미검증 |
| Nemotron 3 / Community-1 / Sortformer | 로컬 화자 구분 후보로 비교 가능 | 사용 가능한 웹 변환·캐시·클러스터링·정확도 미검증 |
| MOSS-Transcribe-Diarize | Python/MLX 후보로 비교 가능 | 웹 통합 실행·90분 입력·출력 메모리 미검증 |
| DeepFilterNet / MossFormer2 / Demucs 등 | 필요한 입력에 서버 전처리 비교 가능 | 각각의 웹 포팅·연산·품질·장시간 안정성 미검증 |
| Ollama `gpt-oss:20b` | 맥북 프로세스에서 분석 후보 | 설치된 Ollama 모델을 아이폰 페이지에서 그대로 실행할 수 있는 경로는 확인하지 못함 |

이 표의 ‘미검증’은 불가능하다는 뜻이 아니다. WebGPU 지원과 후보 모델 전체의 제품 수준 실행 성공은 다른 검증 항목이다.

## 5. 아이폰에서 맥북에 연결하는 조건

마이크 접근에는 보안 컨텍스트와 사용자 권한이 필요하다. 맥북 자신의 `http://localhost`는 예외가 있지만, 아이폰에서 연 `http://192.168.x.x:포트`에는 같은 예외가 적용되지 않는다. 아이폰의 `localhost`도 맥북이 아닌 아이폰 자신이다. [MDN getUserMedia 보안 조건](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)

추천하는 로컬 네트워크 구성은 다음과 같다. 아직 서버 설정이나 인증서를 변경하지 않았다.

```mermaid
flowchart LR
    A[맥북 웹 화면] --> B[맥북 로컬 API]
    C[아이폰 Safari 녹음·업로드] -->|신뢰 가능한 HTTPS와 접속 권한| D[맥북의 선택적 LAN 진입점]
    D --> B
    B --> E[원본 파일과 작업 저장]
    E --> F[맥북 워커의 음성 모델]
    F --> G[로컬 분석 또는 설정한 외부 API]
    G --> H[전사·대화 기록]
    H --> B
```

- **연결:** 같은 Wi-Fi 등 맥북에 도달할 수 있는 네트워크와, 아이폰이 신뢰하는 인증서·이름을 준비한다. 인증서 경고를 무시하는 접속을 마이크 접근의 정상 경로로 삼지 않는다.
- **동일 출처:** 가능하면 웹과 API를 같은 HTTPS 진입점으로 제공한다. HTTPS 페이지가 HTTP 맥북 API를 직접 호출하도록 구성하지 않는다.
- **접속 권한:** 기존 localhost 전용·무로그인 설정을 그대로 LAN에 노출하지 않는다. 기기 연결 코드·세션 등 가벼운 페어링과 Origin 검증을 설계한다. 로컬 전용 서버를 자동으로 모든 주소에 바인딩하지 않는다.
- **가용성:** 맥북이 켜져 있고 깨어 있어야 처리할 수 있다. 외출·맥북 꺼짐 상황은 파일 보관 후 나중에 전송하거나 외부 처리 서버 경로로 별도 다룬다.
- **처리 위치:** 이 구성은 ‘아이폰 안에서 처리’가 아니라 ‘아이폰에서 맥북으로 전송해 로컬 네트워크에서 처리’다. 외부 API 사용 여부는 별도로 기록한다.

이는 기존 승인 설계의 `127.0.0.1` 전용·한 사용자·무로그인 경계를 확장하는 제안이다. 현재 설계를 이미 변경하거나 LAN 서비스를 개방한 상태는 아니다.

## 6. 잠금·앱 전환과 장시간 녹음

아이폰에서 전면 웹 녹음과 잠금·백그라운드 녹음을 같은 지원 항목으로 취급하지 않는다. Safari의 마이크 중단과 MediaRecorder 이벤트 지연이 문서에 설명되어 있고, WebKit에는 백그라운드 수음 문제 보고도 있다. 오래된 버그 보고를 현재 모든 아이폰에서 반드시 중단된다는 증거로 사용하지 않는다. [MDN dataavailable 주의사항](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event), [WebKit 문제 기록](https://bugs.webkit.org/show_bug.cgi?id=226620)

Wake Lock은 보이는 페이지에서 자동 화면 꺼짐을 줄이는 데 사용할 수 있다. 사용자의 직접 잠금·다른 앱 이동·저전력 상태에서 계속 녹음을 보장하는 API는 아니다. 홈 화면 웹앱에서도 지원되지만 네이티브 백그라운드 녹음 권한을 얻는다는 의미는 아니다. [MDN Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API), [WebKit 홈 화면 웹앱 지원](https://webkit.org/blog/16574/webkit-features-in-safari-18-4/)

**제안하는 첫 웹 지원 범위:** 전면 녹음, 가능한 경우 화면 유지, 녹음 중단 감지·명시, 수신한 구간 보존, 파일 가져오기. 잠금 중 녹음이 필수라면 iOS 기본 녹음 후 가져오기 또는 네이티브 수음 모듈을 비교한다. 네이티브 앱에는 AVAudioSession과 background audio 설정이 있지만 전화·알람 등의 중단 처리는 여전히 필요하다. [Apple 네이티브 녹음·백그라운드 설명](https://developer.apple.com/documentation/avfaudio/avaudiosession/category-swift.struct/record)

장시간 녹음은 다음 사항을 검증한다.

- `timeslice`는 정확한 주기가 아니다. 청크 개수로 녹음 길이를 계산하거나, 이벤트가 없으면 즉시 녹음 종료라고 단정하지 않는다.
- 청크에는 순번·크기·수신 확인을 두고, 녹음 상태와 서버 수신 상태를 구분한다. 모든 청크가 독립 재생 파일이라고 가정하지 않는다.
- 전체 2시간 음성을 아이폰 메모리에 모아 마지막에 한 번 전송하지 않는다. 저장·전송 버퍼를 제한하고 실패 시 확보한 구간을 보존한다.
- `mute`·`unmute`·`ended`, `visibilitychange`, 컨테이너 디코딩 결과로 중단을 관측한다. 무음 대화와 입력 중단을 동일하게 표시하지 않는다. [MDN 트랙 mute](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/mute_event)
- 전송이 끝나 작업이 서버에 등록된 이후에는 아이폰 페이지가 처리 완료 때까지 열려 있을 필요가 없는 구조로 한다. 업로드 도중의 백그라운드 전송은 별도 검증 대상이다.

기존 2시간·1GB 제한과 무손실 수음의 관계도 확인한다. 48kHz·16bit PCM을 2시간 저장하면 모노 약 691MB, 스테레오 약 1.38GB다. 단순 PCM 바이트 계산으로 스테레오는 기존 용량 제한을 넘는다. 무손실 코덱의 실제 크기·모바일 메모리는 별도 측정한다.

## 7. 다음 실기기 검증 표

현재 결과는 API·짧은 합성 인코딩까지만 확인한 것이다. 아래 항목이 통과하기 전에는 아이폰 녹음이나 장시간 녹음의 지원 완료를 선언하지 않는다.

| 검증 | 환경·실행 | 판정할 결과 |
| --- | --- | --- |
| 마이크·설정 | 맥북 Chrome/Safari, 실제 아이폰 Safari와 사용 시 PWA | 권한 허용·거부, 실제 채널·샘플레이트·전처리 설정, 거부 후 복구 |
| 한국어 수음 | 같은 한국어 1:1·3명 이상 대화를 기기별 녹음 | 작은 응답·부정·수치·겹침 누락, 전처리 전후 CER·DER·cpCER |
| 포맷과 종료 | Opus/WebM, AAC/MP4, 지원 시 무손실 | 정상 최종 컨테이너, 처음·마지막 발언, 실제 길이·메모리 |
| HTTPS·접속 | 실제 아이폰 → 같은 네트워크 맥북 | 보안 컨텍스트, 마이크 사용, 페어링, 다른 기기의 무단 접근 차단 |
| 장시간 | 10분 예비 시험 후 60분, 최종 지원 길이 120분 | 누락 구간·이벤트 간격·버퍼·배터리·발열·서버 수신 일치 |
| 중단 | 직접 잠금, 자동 잠금, 앱·탭 전환, 통화·알람, 블루투스 변경 | 계속 수음되는지 실제 파형으로 확인, 중단 표시·구간 보존·재시작 |
| 전송 장애 | Wi-Fi 끊김·복구, 맥북 절전·서버 재시작 | 중복·누락 없는 전송 복구, 이미 받은 데이터 보존 |
| 처리 독립성 | 업로드·작업 등록 확인 후 아이폰 탭 종료 | 맥북에서 계속 처리하고 재접속 시 동일 결과 표시 |
| 순수 웹 추론 | 해당 경로가 필수일 때만 모델·런타임을 고정 | 한국어 품질, 실행 성공, 처리 시간·메모리·발열·장시간 화자 ID |

## 8. 기존 설계 체크리스트 검토

`solution-architect` 스킬로 누락·충돌·근거를 보조 점검했다. 별도 승인이나 배포를 수행한 것은 아니다.

- **누락:** 기존 초기 계획에는 아이폰의 HTTPS 접속·페어링, 포맷 협상, 입력 설정 기록, 잠금·전송 장애의 모바일 검증 범위가 충분히 명시되지 않았다.
- **충돌:** localhost 전용·무로그인 설정은 아이폰의 LAN 접속과 그대로 양립하지 않는다. ‘웹 사용’과 ‘모델을 브라우저 안에서 실행’도 구분해야 한다.
- **필요한 근거:** documented — 위 공식 자료. observed — macOS 보고 Chrome의 API·합성 톤 인코딩 결과 JSON. required evidence — 실제 마이크, Safari·아이폰, HTTPS LAN, 장시간·중단 시험과 한국어 모델 평가.
- **다음 검토:** 아이폰 단독 처리·잠금 녹음의 제품 요구를 정하고, 필요한 경우 연결 경계와 네이티브 수음 대안을 설계에 반영한다. 모델 선택 전에는 실제 입력 조건에서 품질과 처리 시간을 측정한다.
