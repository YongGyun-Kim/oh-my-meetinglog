import { useEffect, useState } from "react";
import { CheckCircle2, Circle, RefreshCw } from "lucide-react";
import { api, message } from "../../lib/api";
import type { Readiness } from "../../lib/types";
import { CliConnections } from "./CliConnections";

const engineNames: Record<string, string> = {
  vad: "음성 구간 탐지",
  asr: "한국어 전사",
  aligner: "발언 시간 정렬",
  diarizer: "화자 구분",
  analysis: "대화 분석",
};
export function SettingsPage() {
  const [settings, setSettings] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
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
  return (
    <div className="page settings-page">
      <div className="page-heading">
        <div>
          <h1>설정</h1>
        </div>
        <button
          className="button secondary"
          onClick={() => {
            void refresh();
          }}
        >
          <RefreshCw size={14} />
          새로 고침
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <CliConnections refreshCount={refreshCount} />
      {settings ? (
        <section className="settings-section">
          <h2>로컬 엔진 준비 상태</h2>
          <p className="muted settings-description">
            모델 이름을 누르면 다운로드 페이지로 이동해요. 설치 명령은 서버
            컴퓨터의 프로젝트 폴더에서 실행해 주세요.
          </p>
          <div className="engine-list">
            {settings.engines.map((engine) => {
              const name = engineNames[engine.name] ?? engine.name;
              const analysis = engine.name === "analysis";
              return (
                <div
                  className="engine-row"
                  role="group"
                  aria-label={name}
                  key={engine.name}
                >
                  {engine.ready ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    <Circle size={17} />
                  )}
                  <div>
                    <strong>{name}</strong>
                    <small>
                      <a
                        href={
                          analysis
                            ? `https://ollama.com/library/${engine.repo_id.split(":")[0]}`
                            : `https://huggingface.co/${engine.repo_id}`
                        }
                        target="_blank"
                        rel="noreferrer"
                      >
                        {engine.repo_id}
                      </a>
                    </small>
                    {!engine.ready && (
                      <div className="model-guide">
                        {analysis && (
                          <small>
                            Ollama를 실행한 뒤 모델을 다운로드해 주세요.{" "}
                            <a
                              href="https://ollama.com/download"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Ollama 설치
                            </a>
                          </small>
                        )}
                        <code>
                          {analysis
                            ? `ollama pull ${engine.repo_id}`
                            : `uv run --extra speech meetinglog prepare-models --models ${engine.name}`}
                        </code>
                      </div>
                    )}
                  </div>
                  <span className="status">
                    {engine.ready ? "준비됨" : "준비 필요"}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="help left">
            {settings.media_tools_ready
              ? "FFmpeg · FFprobe 준비됨"
              : "음성 파일을 처리하려면 FFmpeg를 설치해 주세요."}
          </p>
          {!settings.media_tools_ready && (
            <div className="model-guide">
              <a
                href="https://formulae.brew.sh/formula/ffmpeg"
                target="_blank"
                rel="noreferrer"
              >
                FFmpeg 설치 안내
              </a>
              <code>brew install ffmpeg</code>
            </div>
          )}
        </section>
      ) : (
        !error && <p className="empty-message">설정을 확인하고 있어요.</p>
      )}
    </div>
  );
}
