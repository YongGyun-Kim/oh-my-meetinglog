import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Download,
  FileText,
  RefreshCw,
  Sparkles,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { api, message } from "../../lib/api";
import type { Mode, Transcript, Turn } from "../../lib/types";
import { AudioPlayer, type Player } from "./AudioPlayer";
import { TranscriptPane } from "./TranscriptPane";
import { AnalysisPane } from "./AnalysisPane";
import { SpeakerEditor } from "./SpeakerEditor";
import { useRecording } from "./useRecording";

export function RecordingDetail({
  id,
  onBack,
  onDeleted,
}: {
  id: string;
  onBack: () => void;
  onDeleted: () => void;
}) {
  const { detail, refresh, error } = useRecording(id);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<"transcript" | "analysis">("analysis");
  const [speakers, setSpeakers] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<Mode>("local_only");
  const [historical, setHistorical] = useState<Transcript | null>(null);
  const [showHistorical, setShowHistorical] = useState(false);
  const player = useRef<Player>(null);
  useEffect(() => {
    void api
      .settings()
      .then((settings) => setMode(settings.mode))
      .catch(() => {});
  }, []);
  useEffect(() => {
    let active = true;
    if (detail?.analysis_stale && detail.analysis)
      void api
        .snapshotTranscript(id, detail.analysis.transcript_id)
        .then((transcript) => {
          if (active) setHistorical(transcript);
        })
        .catch(() => {});
    else {
      setHistorical(null);
      setShowHistorical(false);
    }
    return () => {
      active = false;
    };
  }, [id, detail?.analysis?.id, detail?.analysis_stale]);
  const act = async (operation: () => Promise<unknown>) => {
    setBusy(true);
    setActionError("");
    try {
      await operation();
      await refresh();
    } catch (reason) {
      setActionError(message(reason));
    } finally {
      setBusy(false);
    }
  };
  const seek = (turn: Turn) => {
    setSelected(turn.id);
    player.current?.seek(turn.start_ms);
    setTab("transcript");
  };
  if (!detail)
    return (
      <div className="page">
        <button className="back-button" onClick={onBack}>
          <ArrowLeft size={16} />
          모든 기록
        </button>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : (
          <p className="empty-message">대화를 불러오고 있습니다…</p>
        )}
      </div>
    );
  const transcript = showHistorical ? historical : detail.transcript;
  const evidenceTranscript = detail.analysis_stale
    ? historical
    : detail.transcript;
  const activeJob =
    detail.job &&
    ["running", "queued", "interrupted"].includes(detail.job.state);
  const stage =
    detail.job?.stage === "analysis"
      ? "대화 내용을 정리하고 있습니다"
      : "음성을 전사하고 화자를 구분하고 있습니다";
  const exportQuery = detail.transcript
    ? `&transcript_id=${encodeURIComponent(detail.transcript.id)}`
    : "";
  return (
    <div className="detail-page">
      <div className="detail-heading">
        <button className="back-button" onClick={onBack}>
          <ArrowLeft size={16} />
          모든 기록
        </button>
        <div className="detail-actions">
          {detail.transcript && (
            <details className="export-menu">
              <summary>
                <Download size={15} />
                내보내기
              </summary>
              <div>
                <a
                  href={`/api/recordings/${id}/export?format=markdown${exportQuery}`}
                  download
                >
                  Markdown
                </a>
                <a
                  href={`/api/recordings/${id}/export?format=json${exportQuery}`}
                  download
                >
                  JSON · AI 분석용
                </a>
              </div>
            </details>
          )}
          <button
            className="icon-button"
            aria-label="기록 삭제"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 size={16} />
          </button>
        </div>
        <h1>{detail.recording.title}</h1>
        <p className="muted">
          {detail.recording.created_at &&
            new Intl.DateTimeFormat("ko-KR", {
              dateStyle: "long",
              timeStyle: "short",
            }).format(new Date(detail.recording.created_at))}{" "}
          · {detail.recording.source === "file" ? "가져온 파일" : "마이크 녹음"}
        </p>
      </div>
      <AudioPlayer id={id} ref={player} />
      {activeJob && (
        <div className="processing-banner" role="status">
          <span className="processing-dot" />
          <div>
            <strong>
              {detail.job?.state === "queued" ? "처리 대기 중입니다" : stage}
            </strong>
            <span>
              서버와 로컬 작업자를 실행해 두면 이 화면을 닫아도 계속 처리합니다.
            </span>
          </div>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => {
              void act(() => api.cancel(detail.job!.id));
            }}
          >
            <X size={13} />
            처리 취소
          </button>
        </div>
      )}
      {detail.job?.state === "failed" && (
        <div className="error" role="alert">
          {detail.job.error_message ?? "처리에 실패했습니다."}
          {detail.transcript
            ? " 전사와 원본 음성은 계속 확인할 수 있습니다."
            : ""}
        </div>
      )}
      {(error || actionError) && (
        <p className="error" role="alert">
          {actionError || error}
        </p>
      )}
      {detail.analysis_stale && (
        <div className="notice">
          수정 전 전사를 바탕으로 만든 분석입니다. 근거를 누르면 당시의 전사를
          표시합니다.
          <button
            disabled={busy || !!activeJob || !detail.transcript}
            onClick={() => {
              void act(() => api.analyze(id, detail.transcript!.id, mode));
            }}
          >
            다시 분석
          </button>
        </div>
      )}
      <div className="mobile-tabs" role="tablist" aria-label="대화 결과">
        <button
          role="tab"
          aria-selected={tab === "transcript"}
          onClick={() => setTab("transcript")}
        >
          <FileText size={15} />
          전사
        </button>
        <button
          role="tab"
          aria-selected={tab === "analysis"}
          onClick={() => setTab("analysis")}
        >
          <Sparkles size={15} />
          대화 정리
        </button>
      </div>
      <div className={`detail-columns tab-${tab}`}>
        <section className="transcript-panel">
          <div className="panel-heading">
            <h2>
              <FileText size={16} />
              전사 <small>{transcript?.turns.length ?? 0}개 발언</small>
            </h2>
            {transcript && !showHistorical && (
              <button className="text-button" onClick={() => setSpeakers(true)}>
                <Users size={14} />
                화자 정보
              </button>
            )}
          </div>
          {showHistorical && (
            <div className="historical-banner">
              분석 당시 전사 · 읽기 전용
              <button onClick={() => setShowHistorical(false)}>
                최신 전사로 돌아가기
              </button>
            </div>
          )}
          {transcript ? (
            <TranscriptPane
              transcript={transcript}
              selectedTurnId={selected}
              onSeek={seek}
              onRefresh={refresh}
              readOnly={showHistorical}
            />
          ) : (
            <div className="result-empty">
              <FileText size={28} />
              <h3>전사를 준비하고 있습니다</h3>
              <p>처리가 끝나면 화자별 발언을 확인할 수 있습니다.</p>
              {!activeJob && detail.recording.input_state === "ready" && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => {
                    void act(() => api.process(id, mode));
                  }}
                >
                  전사 시작
                </button>
              )}
            </div>
          )}
        </section>
        <section className="analysis-panel">
          <div className="panel-heading">
            <h2>
              <Sparkles size={16} />
              대화 정리
            </h2>
            {detail.transcript?.turns.length ? (
              <button
                className="text-button"
                disabled={busy || !!activeJob}
                onClick={() => {
                  void act(() => api.analyze(id, detail.transcript!.id, mode));
                }}
              >
                <RefreshCw size={13} />
                다시 분석
              </button>
            ) : null}
          </div>
          {detail.analysis ? (
            <AnalysisPane
              analysis={detail.analysis}
              transcript={evidenceTranscript}
              onEvidence={(turnId) => {
                const turn = evidenceTranscript?.turns.find(
                  (item) => item.id === turnId,
                );
                if (turn) {
                  if (detail.analysis_stale) setShowHistorical(true);
                  seek(turn);
                }
              }}
            />
          ) : (
            <div className="result-empty">
              <Sparkles size={28} />
              <h3>
                {detail.job?.stage === "no_speech"
                  ? "인식된 대화가 없습니다"
                  : "대화의 맥락을 정리합니다"}
              </h3>
              <p>
                {detail.job?.stage === "no_speech"
                  ? "음성이 있는 파일인지 확인해 주세요."
                  : "전사를 바탕으로 주제, 질문과 답변, 합의한 내용을 정리합니다."}
              </p>
            </div>
          )}
        </section>
      </div>
      <details className="processing-details">
        <summary>처리 정보</summary>
        <p>
          설정:{" "}
          {
            { local_only: "로컬 전용", auto: "자동 선택", api: "외부 API" }[
              detail.job?.mode ?? mode
            ]
          }{" "}
          · 상태: {detail.job?.state ?? "대기"}
        </p>
        {detail.analysis && (
          <p>
            분석 엔진: {detail.analysis.provider} · {detail.analysis.model} ·{" "}
            {detail.analysis.prompt_version}
          </p>
        )}
        <p>한국어 실대화 정확도: 미검증</p>
        {!activeJob && detail.recording.input_state === "ready" && (
          <button
            className="text-button"
            disabled={busy}
            onClick={() => {
              void act(() => api.process(id, mode));
            }}
          >
            원본에서 다시 전사
          </button>
        )}
      </details>
      {speakers && detail.transcript && (
        <SpeakerEditor
          transcript={detail.transcript}
          onRefresh={refresh}
          onClose={() => setSpeakers(false)}
        />
      )}
      {confirmDelete && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <h2 id="delete-title">이 기록을 삭제할까요?</h2>
            <p className="delete-description">
              원본 음성, 전사와 분석을 이 Mac에서 삭제합니다. 진행 중인 처리는
              중지됩니다.
            </p>
            <div className="editor-actions">
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => setConfirmDelete(false)}
              >
                취소
              </button>
              <button
                className="button danger"
                disabled={busy}
                onClick={() => {
                  void act(async () => {
                    await api.remove(id);
                    onDeleted();
                  });
                }}
              >
                삭제
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
