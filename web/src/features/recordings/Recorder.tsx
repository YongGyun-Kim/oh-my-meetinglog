import { AudioLines, Mic, Square } from "lucide-react";
import { useEffect } from "react";
import { clock } from "../../lib/api";
import { useRecorder } from "./useRecorder";

export function Recorder({
  onSaved,
  onBusy,
}: {
  onSaved: (id: string) => void;
  onBusy?: (busy: boolean) => void;
}) {
  const capture = useRecorder((id) => {
    onBusy?.(false);
    onSaved(id);
  });
  const active = ["starting", "recording", "saving"].includes(capture.state);
  useEffect(() => {
    onBusy?.(active);
  }, [active, onBusy]);
  return (
    <section
      className={`capture-panel ${active ? "is-recording" : ""}`}
      aria-label="마이크 녹음"
    >
      <div className="capture-icon">
        {active ? <AudioLines size={26} /> : <Mic size={26} />}
      </div>
      <div className="capture-copy">
        <h2>
          {capture.state === "recording"
            ? "대화를 녹음하고 있어요"
            : capture.state === "saving"
              ? "마지막 음성을 저장하고 있어요"
              : "마이크로 녹음하기"}
        </h2>
        <p>
          {active
            ? "녹음과 저장이 끝날 때까지 이 창을 열어 두세요."
            : "녹음 시작을 누르면 마이크로 녹음할 수 있어요."}
        </p>
        {capture.state === "recording" && (
          <div className="live-meter">
            <span className="live-dot" />
            <span className="time">{clock(capture.elapsedMs)}</span>
            <span className="meter">
              <i style={{ width: `${Math.max(3, capture.level * 100)}%` }} />
            </span>
            <span>마이크 입력</span>
          </div>
        )}
        {capture.elapsedMs >= 7_140_000 && (
          <p className="warning">
            1분 뒤 2시간 제한에 도달하면 녹음이 자동으로 끝나요.
          </p>
        )}
        {capture.error && (
          <p className="error" role="alert">
            {capture.error}
          </p>
        )}
      </div>
      {capture.state === "recording" ? (
        <button className="button danger" onClick={capture.stop}>
          <Square size={15} fill="currentColor" /> 녹음 종료
        </button>
      ) : (
        <button
          className="button primary"
          disabled={active}
          onClick={() => {
            void capture.start();
          }}
        >
          <Mic size={16} />
          {capture.state === "starting"
            ? "마이크 연결 중…"
            : capture.state === "saving"
              ? "저장 중…"
              : "녹음 시작"}
        </button>
      )}
    </section>
  );
}
