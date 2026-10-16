# 음성 처리 모델 후보와 비교 기준

조사 기준일: 2026-10-16. 대화에서 검토한 모델을 역할별로 정리했다. **엔진은 미확정이며 실제 한국어 녹음 벤치마크와 이 PC의 속도·메모리 측정은 아직 하지 않았다.** 공식 발표·설정·모델 카드와 서드파티 실행 구현을 구분한다.

관련 문서: [Plaud 전처리 조사](2026-10-16-plaud-audio-preprocessing.md), [기존 설계안](../superpowers/specs/2026-10-16-local-conversation-records-design.md), [기존 구현 계획](../superpowers/plans/2026-10-16-local-conversation-records.md).

후속 확인: [맥북·아이폰 웹 적용성](2026-10-16-macbook-iphone-web-feasibility.md). macOS Chrome에서 API와 합성 톤 인코딩을 확인했으며, 실제 마이크·아이폰·모델 추론 검증과 구분한다.

## 1. 제품 조건과 비교 원칙

- 한국어 1:1 인터뷰·상담으로 시작하고 **추후 다대다 대화도 지원**한다.
- 녹음 종료 후 정확한 결과를 받으면 된다. 실시간 자막은 초기 필수가 아니다.
- 충분한 품질과 속도를 확보하면 PC 안에서 끝내고, 부족한 단계에 외부 API를 사용할 수 있다.
- 현재 비교 환경은 Apple M5 Pro·48GB 통합 메모리다. CUDA 결과를 이 환경의 속도로 환산하지 않는다.
- 아래 라이선스는 확인한 코드·가중치의 공개 표기를 기록한다. 변환·양자화 체크포인트를 채택할 때는 그 아티팩트와 구성 모델 조건을 다시 고정한다.

| 작업 | 출력 | 이 작업만으로 해결하지 못하는 것 |
| --- | --- | --- |
| 음성 개선: enhancement | 잡음이 완화된 음성 | 누가 언제 말했는지, 전사가 정확해졌는지 |
| 음원·발화 분리: separation | 소스별 파형 | 출력 번호와 실제 화자의 전역 대응 |
| 화자 구분: diarization | 화자별 시작·종료 시각 | 겹친 음성을 각각 깨끗한 트랙으로 복원 |
| 음성 인식: ASR | 발언 텍스트 | 모든 모델이 화자와 정밀 시각을 제공하는 것은 아님 |
| 강제 정렬: forced alignment | 주어진 텍스트의 발음 시각 | 잘못 인식한 텍스트의 사실성 검증 |
| 대화 분석 | 주제·논의 흐름·합의·후속 작업 | 누락된 원문이나 실제로 없던 결정의 복원 |

**회의 전체 참여자 수와 한 순간의 동시 발화자 수는 다르다.** ‘두 소스 출력’, ‘창 안의 네 화자’, ‘회의 전체 최대 여덟 화자’를 같은 제한으로 비교하지 않는다. 이름이 비슷한 **MossFormer2와 MOSS-Transcribe-Diarize는 서로 다른 모델**이다.

## 2. 전처리·분리 후보

| 후보 | 주된 용도 | 확인한 제한·주의점 | 실행·공개 조건과 출처 |
| --- | --- | --- | --- |
| Demucs / HTDemucs | 음악에서 보컬·드럼·베이스·기타 분리 | 대화 참가자별 분리나 화자 구분 모델이 아니다. BGM이 있는 파일에서만 효과를 평가한다 | 원본 저장소 2025-01-01 보관 처리. 코드 MIT. [공식 저장소](https://github.com/facebookresearch/demucs) |
| BS-RoFormer | 음악 소스 분리 | 음악 SDR 개선을 한국어 ASR 개선으로 해석할 수 없다 | 논문 2023. 구현·가중치는 출처별 구분 필요. [원 논문](https://arxiv.org/abs/2309.02612) |
| Mel-Band RoFormer | 멜 대역을 사용하는 음악 분리 | 보컬 분리 후보이며, 회의의 전역 화자 구분을 제공하지 않는다 | 논문 2023. 사용할 체크포인트·라이선스는 미선정. [원 논문](https://arxiv.org/abs/2310.01809) |
| DeepFilterNet3 | 생활 소음 완화, 음성 개선 | 여러 사람의 신원을 구분하거나 각자 파형으로 분리하는 모델이 아니다 | 저복잡도·실시간 지향. 코드 MIT/Apache-2.0. 이 PC의 처리 속도 미측정. [공식 저장소](https://github.com/Rikorose/DeepFilterNet) |
| MossFormer2_SE_48K | 48kHz 음성 개선 | SS 버전과 용도가 다르다. 발음 손실과 전사 정확도를 확인해야 한다 | ClearerVoice-Studio 실행 경로. [공식 모델·사용법](https://github.com/modelscope/ClearerVoice-Studio/blob/main/clearvoice/README.md) |
| MossFormer2_SS_16K | 섞인 두 음성 파형 분리 | 공개 추론 설정은 `num_spks: 2`. 회의 전체 N명의 신원 유지 기능은 별도다 | 16kHz. 공개 모델 카드 Apache-2.0. [공식 설정](https://github.com/modelscope/ClearerVoice-Studio/blob/main/clearvoice/clearvoice/config/inference/MossFormer2_SS_16K.yaml), [가중치 카드](https://huggingface.co/alibabasglab/MossFormer2_SS_16K) |
| SAM Audio | 텍스트·시간 구간·시각적 단서에 따른 목표 소리 추출 | 목표·잔여 파형을 얻는 모델이며 회의 전체의 화자 신원을 자동 관리하지 않는다 | 2025-12-16 공개. 공식 CUDA 지향, 접근 조건·SAM 라이선스 확인 필요. [공식 저장소](https://github.com/facebookresearch/sam-audio), [공식 발표](https://ai.meta.com/blog/sam-audio/) |
| DialogueSidon | 음성 복원과 두 화자 분리의 결합 | 일반 N명 회의의 전역 화자 구분으로 사용할 수 없다 | 2026-04 논문. 코드 MIT, 공개 가중치 CC-BY-NC-4.0·접근 조건. 연구 비교 후보. [논문](https://arxiv.org/abs/2604.09344), [공식 코드](https://github.com/sarulab-speech/Sidon), [가중치](https://huggingface.co/sarulab-speech/DialogueSidon) |

### Demucs에서 참고할 구현

- 모델을 청크마다 새로 로드하지 않고 재사용한다.
- 겹치는 구간으로 추론한 파형을 가중 overlap-add로 합친다. 경계 설정과 CPU/GPU 버퍼 위치를 분리한다.
- `--two-stems=vocals`도 내부적으로 전체 분리를 수행하므로 계산·메모리가 두 출력만큼 줄어드는 것으로 보지 않는다. `htdemucs_ft`는 README상 기본 HTDemucs보다 약 4배 계산한다.
- 청크 추론을 하더라도 전체 출력 텐서를 보유할 수 있다. 2시간·44.1kHz·스테레오·float32·4출력은 출력만 약 **10.2GB**다. 이는 `7200 × 44100 × 2 × 4 × 4` 바이트 계산이며 실측 메모리가 아니다.
- 공식 API의 자동 장치는 CUDA 또는 CPU다. MPS가 자동 선택된다고 가정하지 않는다. 복소 STFT 관련 CPU 경로도 확인해야 한다.

출처: [공식 사용법](https://github.com/facebookresearch/demucs), [청크·결합 코드](https://github.com/facebookresearch/demucs/blob/main/demucs/apply.py), [장치 선택 API](https://github.com/facebookresearch/demucs/blob/main/demucs/api.py), [STFT 구현](https://github.com/facebookresearch/demucs/blob/main/demucs/spec.py).

## 3. 화자 구분 후보

| 후보 | 회의 전체 인원과 처리 방식 | 로컬 실행 경로 | 공개 조건·판단 |
| --- | --- | --- | --- |
| NVIDIA Sortformer 4spk v2.1 | 최대 4명 모델. 캐시를 유지하며 청크 사이 신원을 연결 | NeMo 및 MLX-Audio 구현. 한국어·장시간 유지 성능 미측정 | NVIDIA Open Model License. 초기 설계의 후보이며 다대다 확장에서는 인원 상한을 명시해야 한다. [공식 모델 카드](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1), [MLX 구현 안내](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/vad/models/sortformer/README.md) |
| NVIDIA Nemotron 3 Diarization | 최대 8명, 100M 파라미터. 오프라인·스트리밍, 화자 캐시 사용 | NeMo, NVIDIA NeMo-Speech.cpp, MLX-Audio. 16kHz 모노 입력 | 2026-09-23 공개. OpenMDW-1.1. 8명 이내 다대다 평가 후보. [공식 모델 카드](https://huggingface.co/nvidia/Nemotron-3-Diarization) |
| pyannote Community-1 | 전체 화자 수 추정·클러스터링. `num_speakers`, `min_speakers`, `max_speakers` 지원 | 다운로드 후 오프라인 실행. 기본 CPU, 공식 CUDA 예시. Mac 속도 미측정 | CC-BY-4.0, 최초 접근 조건 수락·토큰 필요. 가변 인원 기준선. 무제한 정확도를 뜻하지 않는다. [공식 모델 카드](https://huggingface.co/pyannote/speaker-diarization-community-1) |
| pyannote Precision-2 | 상용 화자 구분 파이프라인 | 공식 예시는 pyannoteAI 서버에서 실행 | 로컬 가중치 후보와 구분하는 API 비교 대상. [공식 카드](https://huggingface.co/pyannote/speaker-diarization-precision-2) |
| DiariZen WavLM large s80 md v2 | 로컬 구간의 화자 분할 뒤 전체 클러스터링. 로컬 설정의 화자 수와 전체 인원을 구분 | PyTorch 기반. 다채널 지원 등 업데이트 있음 | 코드 MIT, 해당 가중치 CC-BY-NC-4.0. 연구 비교 후보. [공식 저장소](https://github.com/BUTSpeechFIT/DiariZen), [가중치 카드](https://huggingface.co/BUT-FIT/diarizen-wavlm-large-s80-md-v2) |
| SUPlime | WavLM 분할·화자 임베딩·클러스터링. 공개 설명상 10초 창의 최대 4명·동시 2명 조건 | pyannote.audio 4.x 기반. 실제 Mac 실행 미확인 | 2026-09 공개 자료. 코드 MIT, 가중치 CC-BY-NC-4.0. 연구 비교 후보. [공식 저장소](https://github.com/rewayai/suplime), [모델 카드](https://huggingface.co/rewayai/suplime) |

Nemotron 3의 **30.4초 오프라인 입력 버퍼는 연산 소요 시간 수치가 아니다.** 청크 처리로 긴 파일을 받더라도 화자 8명 제한이 사라지지 않는다. 한국어 회의 성능도 별도 측정해야 한다. [공식 입력 버퍼·출력 설명](https://huggingface.co/nvidia/Nemotron-3-Diarization)

Community-1은 일반 화자 구분 결과와 전사 정렬용 exclusive 결과를 제공한다. exclusive 결과만 저장해 실제 겹침 정보를 지우지 않도록 한다. 또한 입력 채널을 평균해 모노로 만드는 기본 경로가 있으므로, 원본 채널은 그 전에 보존한다. [공식 입출력·exclusive 설명](https://huggingface.co/pyannote/speaker-diarization-community-1)

## 4. 전사·정렬 및 전사와 화자 구분을 결합한 후보

| 후보 | 제공 기능 | 인원·길이 관련 확인 사항 | 로컬 경로·공개 조건 |
| --- | --- | --- | --- |
| Qwen3-ASR 1.7B / 0.6B | 다국어 전사, 한국어 지원 | 전역 화자 구분은 별도 필요 | 2026년 공개. 공식 Apache-2.0, MLX-Audio 구현. [공식 저장소](https://github.com/QwenLM/Qwen3-ASR), [MLX 안내](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/models/qwen3_asr/README.md) |
| Qwen3-ForcedAligner 0.6B | 텍스트와 음성의 시간 정렬 | 공식 안내상 최대 5분 입력. 길면 분할하며 전사 정확도 자체를 검증하는 모델은 아님 | Qwen ASR와 구분해 준비·측정. [공식 안내](https://github.com/QwenLM/Qwen3-ASR) |
| Whisper large-v3 | 한국어를 포함한 전사 | 자체 전역 화자 구분 없음 | MLX Whisper로 비교할 기존 기준선. [공식 모델 카드](https://huggingface.co/openai/whisper-large-v3), [MLX 구현](https://github.com/ml-explore/mlx-examples/blob/main/whisper/README.md) |
| MOSS-Transcribe-Diarize 0.9B | 전사·시각·익명 화자·음향 이벤트를 함께 출력, 용어 힌트 지원 | 공식 최대 90분 단일 패스. 명확한 최대 화자 수는 확인 못함. 2시간 입력에는 분할·화자 연결 검증 필요 | 2026-07-09 공개, Apache-2.0. 공식 PyTorch 및 MLX-Audio 포트. [공식 저장소](https://github.com/OpenMOSS/MOSS-Transcribe-Diarize), [모델 카드](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize) |
| VibeVoice-ASR | 화자·시각·텍스트 통합 출력, 50개 이상 언어와 한국어 지원 | 공식 60분 단일 패스. TTS 모델의 ‘4명’을 ASR의 상한으로 옮기면 안 됨. 최대 화자 수 별도 확인 필요 | 2026-01-21 공개. MIT. CPU용 VibeASR.cpp도 공개. [공식 저장소](https://github.com/microsoft/VibeVoice), [지원 언어](https://github.com/microsoft/VibeVoice/blob/main/docs/vibevoice-asr.md), [CPU 구현](https://github.com/microsoft/VibeASR.cpp) |
| VibeVoice-ASR-Streaming | 입력 도착 중 전사·화자 라벨 출력, 용어 힌트, 한국어 포함 10개 언어 | 최대 화자 수 별도 확인 필요. 배치 MVP에서 스트리밍 기능은 필수 아님 | 2026-09-03 공개, MIT. 모델명에 7B가 있어도 실제 전체 파라미터·메모리를 그 숫자로 단정하지 않는다. [공식 안내](https://github.com/microsoft/VibeVoice/blob/main/docs/vibevoice-asr-streaming.md), [모델 카드](https://huggingface.co/microsoft/VibeVoice-ASR-Streaming-7B) |

MOSS의 한국어를 포함한 다국어 대회 성과는 개발팀 발표다. 자체 표의 CER·cpCER나 다른 언어의 성과를 한국어 상담 정확도로 그대로 바꾸지 않는다. 특히 전사와 화자 구분을 함께 평가하려면 CER 외에 **화자 배정까지 반영한 cpCER**를 비교한다. [공식 평가 설명](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize)

VibeASR.cpp의 1.58GB·CPU 실시간 처리 수치는 발표 환경의 결과다. 이 PC에서의 실행 성공·한국어 품질·처리 시간·피크 메모리는 미측정이다. [공식 CPU 엔진 발표](https://github.com/microsoft/VibeASR.cpp)

## 5. 최근 발표일과 실행 구현의 구분

| 대상 | 확인한 날짜 | 의미 |
| --- | --- | --- |
| Nemotron 3 Diarization | 2026-09-23 | 공식 카드의 모델 공개일 |
| MLX-Audio v0.5.6 | 2026-09-24 | Nemotron 3 지원 추가. 원 모델 공개일과 별개 |
| VibeVoice-ASR-Streaming | 2026-09-03 | 공식 저장소의 공개 발표 |
| MOSS-Transcribe-Diarize 0.9B | 2026-07-09 | 공식 공개 발표. 모델 저장소 생성일·최근 커밋일과 구분 |
| DialogueSidon 논문 | 2026-04 | 논문 시점. 일반 N명 화자 구분 모델이라는 의미는 아님 |

출처: 위 모델별 공식 자료와 [MLX-Audio 릴리스](https://github.com/Blaizzy/mlx-audio/releases/tag/v0.5.6).

Apple Silicon 실행 구현도 다음처럼 구분한다.

- **MLX-Audio:** Qwen3-ASR·Sortformer·Nemotron 3 및 MOSS 등 포트가 존재한다. 포트 존재와 원 구현의 결과 일치·한국어 품질·속도 보장은 다르다. [프로젝트](https://github.com/Blaizzy/mlx-audio), [MOSS 구현](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/models/moss_transcribe_diarize/moss_transcribe_diarize.py)
- **NVIDIA NeMo-Speech.cpp:** Nemotron 3를 로컬에서 실행하는 공식 C++ 경로다. macOS와 CPU·Metal 빌드 경로가 있다. 선택한 모델·정밀도·백엔드에서의 동작과 속도는 직접 확인한다. [공식 런타임](https://github.com/NVIDIA/NeMo-Speech.cpp)
- **VibeASR.cpp:** VibeVoice-ASR용 CPU 경로다. 원 PyTorch·MLX 경로와 각각 정확도·시간을 측정해야 한다.

DiariZen의 업데이트 날짜나 SUPlime 패키지의 배포 날짜를 기반 모델이 새로 학습된 날짜로 기록하지 않는다. 최신이라는 사실만으로 기존 후보보다 우수하다고 판정하지 않는다.

## 6. 외부 API와 대화 분석 후보

| 후보 | 역할 | 현재 위치 |
| --- | --- | --- |
| OpenAI `gpt-4o-transcribe-diarize` | 전사와 화자 구분을 함께 받는 외부 비교 경로 | 기존 설계 후보. `diarized_json`, 파일 25MB 제한과 긴 입력 청크 처리 조건을 확인해야 한다. [공식 음성 문서](https://developers.openai.com/api/docs/guides/speech-to-text) |
| pyannote Precision-2 | 외부 화자 구분 비교 | 로컬 Community-1과 실행 위치를 혼동하지 않는다. [공식 모델 카드](https://huggingface.co/pyannote/speaker-diarization-precision-2) |
| Plaud Transcription API | Plaud의 비공개 전사·화자 구분 파이프라인 | 이번 조사에서 확인한 참고 API. 공개 가중치 모델이 아니며 채택 미정. [공식 개발자 소개](https://dev.plaud.ai/transcription-api/), [클라우드 호출 구조](https://docs.plaud.ai/plaud-embedded/overview) |
| Ollama `gpt-oss:20b` | 텍스트 전사를 주제·논의·합의·후속 작업으로 구조화 | 현재 PC에 설치된 분석 후보. 음성 전처리·ASR 모델이 아니다. 품질 미측정. [공식 모델](https://huggingface.co/openai/gpt-oss-20b) |
| OpenAI `gpt-5-mini` | 근거 발언 ID를 가진 구조화 분석을 받는 외부 경로 | 기존 설계 후보. 모델 사용 가능 여부와 한국어 결과는 실제 연결 시 확인. [공식 모델](https://developers.openai.com/api/docs/models/gpt-5-mini), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) |

참조 화자 음성의 개수 제한은 회의의 최대 화자 수와 별개다. API를 여러 요청으로 분할할 때 반환된 화자 번호가 자동으로 이어진다고 가정하지 않는다.

## 7. 구간별 추론과 전역 화자 연결

| 단계 | 구간별 처리 | 전체 녹음으로 합칠 때 필요한 것 |
| --- | --- | --- |
| 음성 개선·분리 | 모델의 윈도·오버랩에 맞춰 파형 추론 | 파형의 가중 결합, 분리 출력 순열·화자 연결, 파일로 점진 저장 |
| ASR | 발화 경계를 고려한 분할과 일부 중복 | 원본 오프셋, 경계 발언·단어 중복 제거, 텍스트 누락 검사 |
| Sortformer·Nemotron 계열 | 녹음 세션의 캐시를 이어서 사용 | 청크마다 화자 상태를 초기화하지 않기, 재시작 복구 검증 |
| 클러스터링 화자 구분 | 로컬 분할과 임베딩 추출 | 녹음 전체의 화자 클러스터링. 독립 구간의 A/B를 그대로 연결하지 않기 |
| 통합 전사·화자 모델 | 단일 입력 길이 안에서 실행하거나 분할 | 입력 상한·출력 토큰 상한, 청크 간 화자 ID 연결, 긴 침묵·재등장 처리 |
| 대화 분석 | 길면 발언 ID를 보존한 부분 분석 | 대화 전체의 주제 흐름·결정 관계 통합, 원문 근거 검증 |

참고 코드: [Demucs 청크 처리](https://github.com/facebookresearch/demucs/blob/main/demucs/apply.py), [Sortformer MLX 스트리밍](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/vad/models/sortformer/README.md), [Nemotron 화자 캐시](https://huggingface.co/nvidia/Nemotron-3-Diarization).

MossFormer2_SS로 두 사람의 겹침을 풀더라도, 첫 구간의 출력 1과 다음 구간의 출력 1이 같은 사람이라는 보장은 없다. 총 참여자가 세 명 이상인 회의에서는 더욱 별도 연결이 필요하다. 분리를 회의 전체 화자 구분의 대체물로 삼지 않는다.

## 8. 모델을 고르기 전의 평가안

비교를 시작할 소수의 조합을 제안한다. 아래는 제품 채택 순위가 아니다.

| 비교 조합 | 확인하려는 질문 |
| --- | --- |
| Qwen3-ASR 1.7B + ForcedAligner + Nemotron 3 | 전사·정렬·화자 구분을 나눈 경로가 한국어와 3~8명에서 유리한가 |
| Qwen3-ASR 1.7B + ForcedAligner + Community-1 | 가변 화자 수와 긴 대화에서 기준선·대체 경로가 되는가 |
| MOSS-Transcribe-Diarize 0.9B | 통합 모델이 전사와 화자 배정의 결합 오류를 줄이는가 |
| Whisper large-v3 + 동일 화자 구분기 | 기존 전사 기준선 대비 새 ASR가 실제로 나은가 |
| VibeVoice-ASR / VibeASR.cpp | 장시간 입력·CPU 실행에서 추가 비교 가치가 있는가 |

기존 Sortformer v2.1은 초기 설계와의 비교를 위해 남긴다. 전처리는 모든 조합에 무조건 넣지 않고, 기준 입력과 생활 소음 개선본을 먼저 비교한다. 음악·겹침 분리는 문제가 확인된 구간의 후속 실험으로 둔다.

### 데이터 조건

- 깨끗한 한국어 1:1, 에어컨·카페 소음, 먼 거리·잔향을 구분한다.
- 작은 목소리, 짧은 맞장구, 부정 표현, 수치·이름·전문 용어를 포함한다.
- 3~4명, 5~8명 대화를 별도로 평가하고 겹침 비율을 기록한다. 9명 이상 지원을 논의할 때는 별도 검증 세트를 추가한다.
- 장시간 녹음에서 화자가 한동안 말하지 않다가 돌아오는 상황과 청크 경계를 포함한다.
- 정답 전사와 화자 시각을 사람이 확인하고, 설정을 고른 자료와 최종 평가 자료를 구분한다. 초기 30분 주석 자료·별도 60분 장시간 평가라는 기존 계획을 출발점으로 삼는다.

### 결과로 남길 항목

| 지표 | 목적 |
| --- | --- |
| CER, 필요 시 WER | 텍스트 정확도. 한글 정규화·띄어쓰기·기호 처리 규칙을 고정 |
| cpCER | 녹음 전체에서 화자를 최적으로 대응시킨 후 문자 오류 계산. 전사와 화자 배정을 함께 비교 |
| DER | 화자 구분 오류. collar 0, 겹침 포함으로 동일한 평가 조건을 유지 |
| 발언·겹침 누락 및 재등장 오류 | 작은 응답 삭제, 겹친 사람 누락, 청크 뒤 화자 ID 변경 확인 |
| 처리 시간·RTF·피크 메모리 | 로컬로 충분한지 판단. 다운로드·최초 로드·실제 추론을 나눠 기록 |
| 분석의 근거 정확도 | 요약의 발언 ID, 수치·부정·합의·담당자·기한의 일치 확인 |

분리 실험의 SI-SDR·음질 점수는 보조 지표다. 실제 전사와 화자 배정이 나빠지면 기본 전처리로 채택하지 않는다. 실행 환경, 패키지·모델 리비전, 양자화, 청크·캐시 설정과 처리 입력 버전을 결과에 함께 기록한다.

## 9. 결정 상태

- **확정된 제품 조건:** 로컬 웹 우선, 마이크·파일 입력, 한국어 1:1부터 시작, 녹음 후 처리, 다대다 확장 고려, 필요 시 API 허용.
- **미확정:** 기본 ASR·화자 구분·전처리 모델, 소음별 자동 전환 기준, 지원 인원 상한.
- **완료한 조사:** 공개 용도·제약·실행 경로·출처 정리와 Plaud의 공개 전처리 설명 확인.
- **아직 하지 않은 일:** 모델 다운로드·설치, 실제 음성 실행, 한국어 품질·속도·메모리 측정, 제품 구현.

기존 승인 설계안과 구현 계획의 엔진명은 최초 검증 후보의 기록이다. 이 후속 조사만으로 모델을 확정하거나 새 엔진으로 교체한 것은 아니다.
