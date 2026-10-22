import { useEffect, useState } from "react";
import { CheckCircle2, Circle, RefreshCw } from "lucide-react";
import { api, message } from "../../lib/api";
import type { Mode, Readiness } from "../../lib/types";
import { CliConnections } from "./CliConnections";

const modes: { mode: Mode; title: string; text: string }[] = [
  {
    mode: "local_only",
    title: "로컬 전용",
    text: "전사와 대화 분석을 이 Mac에서만 처리해요.",
  },
  {
    mode: "auto",
    title: "자동 선택",
    text: "이 Mac에서 먼저 처리해요. 처리에 실패하거나 품질 평가에서 미달로 확인되면 설정한 외부 API로 전환해요.",
  },
  {
    mode: "api",
    title: "외부 API",
    text: "전사와 분석에 외부 API를 사용해요. 음성과 텍스트가 외부로 전송돼요.",
  },
];
export function SettingsPage() {
  const [settings, setSettings] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const refresh = async () => {
    setRefreshCount((value) => value + 1);
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
          <span className="eyebrow">녹음 처리</span>
          <h1>처리 설정</h1>
          <p>새로 처리하는 대화에 적용돼요.</p>
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
      <CliConnections refreshCount={refreshCount} />
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
                ? "외부 API 키가 서버에 설정돼 있어요. 실제로 연결되는지는 아직 확인하지 않았어요."
                : "외부 API가 설정되지 않았어요. 자동 선택도 이 Mac에서만 처리해요."}
            </p>
          </section>
          <section className="settings-section">
            <h2>로컬 엔진 준비 상태</h2>
            <p className="muted settings-description">
              모델이 준비돼 있어도 정확도를 검증한 것은 아니에요. 실제 한국어
              대화로 평가하기 전까지 정확도 미검증으로 표시해요.
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
                : "음성 파일을 처리하려면 FFmpeg를 설치해 주세요."}
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
              <code>OPENAI_API_KEY</code>를 설정하고 서버와 작업자를 다시 실행해
              주세요. 키는 브라우저에 저장하지 않아요.
            </p>
          </section>
        </>
      ) : (
        !error && <p className="empty-message">설정을 확인하고 있어요.</p>
      )}
    </div>
  );
}
