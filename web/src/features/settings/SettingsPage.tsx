import { useEffect, useState } from "react";
import { CheckCircle2, Circle, RefreshCw } from "lucide-react";
import { api, message } from "../../lib/api";
import type { Mode, Readiness } from "../../lib/types";

const modes: { mode: Mode; title: string; text: string }[] = [
  {
    mode: "local_only",
    title: "로컬 전용",
    text: "이 Mac에서만 전사와 대화 분석을 처리합니다.",
  },
  {
    mode: "auto",
    title: "자동 선택",
    text: "로컬 처리를 우선합니다. 실패하거나 평가 기준에 미달한 경우 구성된 외부 API로 전환합니다.",
  },
  {
    mode: "api",
    title: "외부 API",
    text: "전사와 분석에 외부 API를 사용합니다. 음성·텍스트가 외부로 전송됩니다.",
  },
];
export function SettingsPage() {
  const [settings, setSettings] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const refresh = async () => {
    try {
      setSettings(await api.settings());
      setError("");
    } catch (reason) {
      setError(message(reason));
    }
  };
  useEffect(() => {
    void refresh();
  }, []);
  const change = async (mode: Mode) => {
    setSaving(true);
    try {
      setSettings(await api.updateMode(mode));
      setError("");
    } catch (reason) {
      setError(message(reason));
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="page settings-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">WORKSPACE SETTINGS</span>
          <h1>처리 설정</h1>
          <p>새로 처리하는 대화에 적용됩니다.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => {
            void refresh();
          }}
        >
          <RefreshCw size={14} />
          새로 확인
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {settings ? (
        <>
          <section className="settings-section">
            <h2>처리 방식</h2>
            <div className="mode-options">
              {modes.map((item) => (
                <label
                  className={`mode-option ${settings.mode === item.mode ? "chosen" : ""}`}
                  key={item.mode}
                >
                  <input
                    type="radio"
                    name="mode"
                    aria-label={item.title}
                    checked={settings.mode === item.mode}
                    disabled={
                      saving ||
                      (!settings.api_configured && item.mode === "api")
                    }
                    onChange={() => {
                      void change(item.mode);
                    }}
                  />
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.text}</p>
                  </div>
                </label>
              ))}
            </div>
            <p className="help left">
              {settings.api_configured
                ? "외부 API 키가 서버에 구성되어 있습니다. 실제 호출 가능 여부는 아직 확인하지 않았습니다."
                : "외부 API가 구성되지 않았습니다. 자동 선택도 로컬에서만 처리합니다."}
            </p>
          </section>
          <section className="settings-section">
            <h2>로컬 엔진 준비 상태</h2>
            <p className="muted settings-description">
              모델 준비와 정확도 검증은 별도입니다. 실제 한국어 대화 평가 전까지
              정확도는 미검증으로 표시합니다.
            </p>
            <div className="engine-list">
              {settings.engines.map((engine) => (
                <div className="engine-row" key={engine.name}>
                  {engine.ready ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    <Circle size={17} />
                  )}
                  <div>
                    <strong>
                      {(
                        {
                          vad: "음성 구간 탐지",
                          asr: "한국어 전사",
                          aligner: "단어 시간 정렬",
                          diarizer: "화자 구분",
                          analysis: "대화 분석",
                        } as Record<string, string>
                      )[engine.name] ?? engine.name}
                    </strong>
                    <small>{engine.repo_id}</small>
                  </div>
                  <span className="status">
                    {engine.ready ? "준비됨" : "준비 필요"}
                  </span>
                  <span className="quality-label">
                    {engine.quality === "passed"
                      ? "평가 통과"
                      : "정확도 미검증"}
                  </span>
                </div>
              ))}
            </div>
            <p className="help left">
              {settings.media_tools_ready
                ? "FFmpeg · FFprobe 준비됨"
                : "음성 파일 처리를 위해 FFmpeg 설치가 필요합니다."}
            </p>
          </section>
          <section className="settings-section">
            <h2>모델과 API 설정</h2>
            <p>
              모델 다운로드:{" "}
              <code>uv run --extra speech meetinglog prepare-models</code>
            </p>
            <p>
              대화 분석: <code>ollama pull gpt-oss:20b</code>
            </p>
            <p>
              외부 API는 프로젝트의 <code>.env</code>에{" "}
              <code>OPENAI_API_KEY</code>를 설정하고 서버와 작업자를 다시
              실행하세요. 키는 브라우저에 저장하지 않습니다.
            </p>
          </section>
        </>
      ) : (
        !error && <p className="empty-message">설정을 확인하고 있습니다…</p>
      )}
    </div>
  );
}
