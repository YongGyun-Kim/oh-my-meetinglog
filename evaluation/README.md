# 한국어 대화 품질 평가

자동 테스트와 실제 음성 품질을 분리한다. 비어 있는 예시는 `insufficient_evidence`를 반환한다. 정답·음성·개인 검토 파일은 `evaluation/private/` 등 Git 제외 경로에 보관한다.

```bash
uv sync --extra speech --extra evaluation
uv run --no-sync meetinglog evaluate --manifest evaluation/corpus.example.json --mode local_only --output data/evaluations/example.json
```

실제 manifest는 `schema.json`을 따르며 경로는 manifest 파일 기준이다.

```json
{
  "schema_version": 1,
  "items": [
    {
      "id": "interview-01",
      "audio_path": "interview.wav",
      "reference_transcript_path": "interview.txt",
      "reference_rttm_path": "interview.rttm",
      "split": "quality",
      "human_review_path": "interview-review.json"
    }
  ]
}
```

`quality` 자료는 최소 30분의 정답 전사와 RTTM이 필요하다. 별도 `performance` 자료는 최소 60분 연속 녹음이다. 첫 실행에는 `human_review_path`를 null로 두고 보고서의 prediction을 직접 검토한다. 이후 검토 JSON에 해당 항목의 `prediction_sha256`, `reviewer`, 아래 boolean 항목을 기록한다. 다시 실행한 결과와 지문이 일치해야 검토를 적용한다. 출력이 바뀌면 다시 검토한다.

```json
{
  "prediction_sha256": "보고서의 해당 지문",
  "reviewer": "실제 검토자",
  "topics_preserved": true,
  "qa_preserved": true,
  "numbers_preserved": true,
  "negation_preserved": true,
  "evidence_valid": true,
  "no_invented_decisions_owners_dates": true
}
```

CER은 NFC 정규화 후 공백·문장부호만 제외하며 숫자와 부정 표현을 유지한다. DER은 최종 전사 발언의 화자/시간 기준으로 계산하며 경계 허용 0초, 겹침을 포함한다. 무음 정답은 CER 분모에서 제외하고 `silence_failure`로 보고한다. 처리 시간에는 디코딩·모델 로드·전사·화자 구분·분석을 포함한다. 업로드·모델 다운로드 시간은 제외한다. 워커와 별도 Ollama 프로세스의 통합 최대 메모리는 아직 측정하지 않아 null이다.

통과 조건은 CER·DER 각 10% 이하, 60분 녹음의 전체 처리 15분 이하, 모든 사람 검토 통과다. 자료나 의존성이 부족하면 통과를 기록하지 않는다. 보고서에 예측 텍스트와 분석이 포함되므로 개인 음성과 같은 위치에서 관리한다. 평가 보고서를 자동 모드의 검증 프로필로 자동 승격하지는 않는다.

기본 Qwen과 같은 자료로 Whisper/API를 비교할 수 있다. Whisper는 선택한 경우만 별도로 준비하며 아직 실제 실행 검증하지 않았다.

```bash
uv run --no-sync meetinglog prepare-models --models whisper
uv run --no-sync meetinglog evaluate --manifest evaluation/private/corpus.json --mode local_only --engine whisper --output data/evaluations/whisper.json
uv run --no-sync meetinglog evaluate --manifest evaluation/private/corpus.json --mode api --output data/evaluations/api.json
```

`api`는 외부 전송과 요금이 발생하며 서버 API 키가 필요하다. 기본값은 `local_only`다. 현재 정답이 있는 실제 대화 자료가 없으므로 어떤 조합도 품질 검증 완료로 표시하지 않는다.
