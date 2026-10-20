import { useCallback, useEffect, useRef, useState } from "react";
import { AudioLines, FolderOpen, Settings, Upload } from "lucide-react";
import { api, message } from "./lib/api";
import type { RecordingSummary } from "./lib/types";
import { Recorder } from "./features/recordings/Recorder";
import { RecordingList } from "./features/recordings/RecordingList";
import { UploadDialog } from "./features/recordings/UploadDialog";
import { RecordingDetail } from "./features/detail/RecordingDetail";
import { SettingsPage } from "./features/settings/SettingsPage";

export default function App() {
  const [records, setRecords] = useState<RecordingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [upload, setUpload] = useState(false);
  const [route, setRoute] = useState(window.location.hash);
  const [recording, setRecording] = useState(false);
  const recordingRef = useRef(false);
  const captureBusy = useCallback((value: boolean) => {
    recordingRef.current = value;
    setRecording(value);
  }, []);
  const selected = route.startsWith("#record/") ? route.slice(8) : null;
  const settings = route === "#settings";
  const refresh = useCallback(async () => {
    try {
      setRecords(await api.listRecordings());
      setError("");
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const interval = setInterval(() => {
      void refresh();
    }, 3500);
    return () => clearInterval(interval);
  }, [refresh]);
  useEffect(() => {
    const handler = () => {
      if (!recordingRef.current) setRoute(window.location.hash);
      else
        window.history.replaceState(
          null,
          "",
          window.location.pathname + window.location.search,
        );
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  const navigate = (next: string) => {
    if (!recording) {
      window.location.hash = next;
      setRoute(next);
    }
  };
  const saved = (id: string) => {
    setUpload(false);
    captureBusy(false);
    window.location.hash = `record/${id}`;
    setRoute(`#record/${id}`);
    void refresh();
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          disabled={recording}
          onClick={() => navigate("")}
        >
          <span>
            <AudioLines size={23} />
          </span>
          대화록<span className="brand-dot">.</span>
        </button>
        <span className="workspace-label">내 기록</span>
        <nav>
          <button
            disabled={recording}
            className={`nav-item ${!settings ? "active" : ""}`}
            onClick={() => navigate("")}
          >
            <FolderOpen size={18} />
            모든 기록<span>{records.length}</span>
          </button>
          <button
            disabled={recording}
            className={`nav-item ${settings ? "active" : ""}`}
            onClick={() => navigate("#settings")}
          >
            <Settings size={18} />
            처리 설정
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="local-label">
            <span />이 Mac에 보관
          </div>
          <p>녹음·전사·대화 분석</p>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>
            내 기록 <span className="slash">/</span>{" "}
            {settings ? "처리 설정" : selected ? "대화 기록" : "모든 기록"}
          </span>
          <button
            className="local-badge"
            disabled={recording}
            onClick={() => navigate("#settings")}
          >
            저장 위치 · 이 Mac
          </button>
        </header>
        {settings ? (
          <SettingsPage />
        ) : selected ? (
          <RecordingDetail
            key={selected}
            id={selected}
            onBack={() => navigate("")}
            onDeleted={() => {
              navigate("");
              void refresh();
            }}
          />
        ) : (
          <div className="page">
            <div className="page-heading">
              <div>
                <span className="eyebrow">녹음과 전사</span>
                <h1>대화 기록</h1>
                <p>녹음한 내용을 확인하고 수정할 수 있어요.</p>
              </div>
              <button
                className="button secondary"
                disabled={recording}
                onClick={() => setUpload(true)}
              >
                <Upload size={16} /> 파일 가져오기
              </button>
            </div>
            <Recorder onSaved={saved} onBusy={captureBusy} />
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <div inert={recording}>
              <RecordingList
                records={records}
                loading={loading}
                onSelect={(id) => navigate(`#record/${id}`)}
                onUpload={() => setUpload(true)}
              />
            </div>
            <footer className="page-footer">
              <span>발언 시각을 누르면 원본 음성을 들을 수 있어요.</span>
              <button
                className="text-button"
                disabled={recording}
                onClick={() => navigate("#settings")}
              >
                <Settings size={13} /> 처리 설정
              </button>
            </footer>
          </div>
        )}
      </main>
      {upload && (
        <UploadDialog onClose={() => setUpload(false)} onSaved={saved} />
      )}
    </div>
  );
}
