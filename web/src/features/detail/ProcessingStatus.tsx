import { X } from "lucide-react";
import type { Job, RecordingDetail } from "../../lib/types";

const speechSteps = [
  ["normalize", "음성 파일을 준비하고 있어요."],
  ["vad", "대화가 있는 구간을 찾고 있어요."],
  ["asr", "음성을 글로 바꾸고 있어요."],
  ["align", "문장의 재생 위치를 맞추고 있어요."],
  ["diarize", "화자를 구분하고 있어요."],
  ["assemble", "전사 결과를 정리하고 저장하고 있어요."],
];

export function ProcessingStatus({
  job,
  history,
  busy,
  onCancel,
}: {
  job: Job;
  history: RecordingDetail["processing_history"];
  busy: boolean;
  onCancel: () => void;
}) {
  const running = job.state === "running";
  const speech = job.stage === "speech";
  const event = history
    .filter((entry) => entry.job_id === job.id && entry.stage === job.stage)
    .at(-1);
  const step =
    running && speech && event?.event === "speech_progress"
      ? speechSteps.findIndex(([phase]) => phase === event.metadata.phase)
      : -1;
  const label =
    job.state === "queued"
      ? "처리를 기다리고 있어요."
      : job.state === "interrupted"
        ? "처리가 중단됐어요. 워커가 실행되면 다시 시작해요."
        : step >= 0
          ? speechSteps[step][1]
          : speech
            ? "음성을 처리하고 있어요."
            : "대화 내용을 정리하고 있어요.";
  const completed = event?.metadata.completed;
  const total = event?.metadata.total;
  const measured =
    running &&
    (event?.event === "speech_progress" ||
      event?.event === "analysis_progress") &&
    typeof completed === "number" &&
    Number.isInteger(completed) &&
    typeof total === "number" &&
    Number.isInteger(total) &&
    total > 0 &&
    completed >= 0 &&
    completed <= total;

  return (
    <div className="processing-banner" role="status">
      <span className="processing-dot" aria-hidden="true" />
      <div className="processing-content">
        <strong>{label}</strong>
        {step >= 0 && (
          <small className="processing-step">{step + 1}/6 단계</small>
        )}
        <div className="processing-progress">
          <progress
            max={measured ? total : 1}
            value={measured ? completed : undefined}
            aria-label="현재 단계 진행률"
            aria-valuetext={
              measured ? `${Math.round((completed / total) * 100)}%` : label
            }
          />
          {measured && (
            <small>
              {Math.round((completed / total) * 100)}% · {completed}/{total}{" "}
              {speech ? "구간" : "작업"}
            </small>
          )}
        </div>
        <span className="processing-description">
          서버와 워커가 실행 중이면 이 화면을 닫아도 처리가 계속돼요.
        </span>
      </div>
      <button className="text-button" disabled={busy} onClick={onCancel}>
        <X size={13} />
        처리 취소
      </button>
    </div>
  );
}
