import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Download,
  FileText,
  RefreshCw,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";
import { api, message } from "../../lib/api";
import type { Mode, Transcript, Sentence, FormOption } from "../../lib/types";
import { AudioPlayer, type Player } from "./AudioPlayer";
import { TranscriptPane } from "./TranscriptPane";
import { AnalysisPane } from "./AnalysisPane";
import { SpeakerEditor } from "./SpeakerEditor";
import { AnalysisFormDialog } from "./AnalysisFormDialog";
import { useRecording } from "./useRecording";
import { ProcessingStatus } from "./ProcessingStatus";

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
  const [forms, setForms] = useState<FormOption[]>([]);
  const [chooseForm, setChooseForm] = useState(false);
  const [speakers, setSpeakers] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<Mode>("local_only");
  const [historical, setHistorical] = useState<Transcript | null>(null);
  const [showHistorical, setShowHistorical] = useState(false);
  const [showReview, setShowReview] = useState(false);
  const player = useRef<Player>(null);
  useEffect(() => {
    void api
      .forms()
      .then(setForms)
      .catch((reason) => setActionError(message(reason)));
  }, []);
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
  const seek = (turn: Sentence) => {
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
          <p className="empty-message">대화 기록을 불러오고 있어요.</p>
        )}
      </div>
    );
  const transcript = showHistorical ? historical : detail.transcript;
  const playSentence = (sentence: Sentence) => {
    const sentences = transcript?.turns.flatMap((turn) => turn.sentences) ?? [];
    const next =
      sentences[sentences.findIndex((item) => item.id === sentence.id) + 1];
    const end =
      next && next.start_ms > sentence.start_ms
        ? next.start_ms
        : sentence.end_ms;
    setSelected(sentence.id);
    setTab("transcript");
    player.current?.play(sentence.start_ms, end);
  };
  const evidenceTranscript = detail.analysis_stale
    ? historical
    : detail.transcript;
  const activeJob =
    detail.job &&
    ["running", "queued", "interrupted"].includes(detail.job.state);
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
                {detail.analysis && (
                  <a
                    href={`/api/recordings/${id}/export?format=analysis_markdown&transcript_id=${encodeURIComponent(detail.analysis.transcript_id)}&analysis_id=${encodeURIComponent(detail.analysis.id)}`}
                    download
                  >
                    대화 정리 · Markdown
                  </a>
                )}
                <a
                  href={`/api/recordings/${id}/export?format=markdown${exportQuery}`}
                  download
                >
                  Markdown · 에이전트 전달용
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
        <ProcessingStatus
          job={detail.job!}
          history={detail.processing_history}
          busy={busy}
          onCancel={() => {
            void act(() => api.cancel(detail.job!.id));
          }}
        />
      )}
      {detail.job?.state === "failed" && (
        <div className="error" role="alert">
          {detail.job.error_message ?? "처리하지 못했어요."}
          {detail.transcript
            ? " 전사와 원본 음성은 계속 확인할 수 있어요."
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
          수정 전 전사를 바탕으로 만든 분석이에요. 근거 보기를 켜고 근거를
          누르면 당시 전사를 볼 수 있어요.
          <button
            disabled={busy || !!activeJob || !detail.transcript}
            onClick={() => {
              setChooseForm(true);
            }}
          >
            다시 정리
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
              전사 <small>{transcript?.turns.length ?? 0}개 턴</small>
            </h2>
            {transcript && (
              <button
                className="text-button"
                aria-pressed={showReview}
                onClick={() => setShowReview((visible) => !visible)}
              >
                {showReview ? "검토 정보 숨기기" : "검토 정보 보기"}
              </button>
            )}
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
              selectedSentenceId={selected}
              onSeek={playSentence}
              onRefresh={refresh}
              readOnly={showHistorical}
              showReview={showReview}
            />
          ) : (
            <div className="result-empty">
              <FileText size={28} />
              <h3>아직 전사가 없어요</h3>
              <p>전사가 끝나면 누가 언제 말했는지 확인할 수 있어요.</p>
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
            {detail.analysis && (
              <small>
                {
                  forms.find((option) => option.id === detail.analysis?.form)
                    ?.title
                }
              </small>
            )}
            {detail.transcript?.turns.length ? (
              <button
                className="text-button"
                disabled={busy || !!activeJob}
                onClick={() => {
                  setChooseForm(true);
                }}
              >
                <RefreshCw size={13} />
                {detail.analysis ? "다시 정리" : "대화 정리"}
              </button>
            ) : null}
          </div>
          {detail.analysis ? (
            <AnalysisPane
              key={detail.analysis.id}
              analysis={detail.analysis}
              transcript={evidenceTranscript}
              onEvidence={(turnId) => {
                const turn = evidenceTranscript?.turns
                  .flatMap((item) => item.sentences)
                  .find((item) => item.id === turnId);
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
                  ? "인식된 음성이 없어요"
                  : "아직 분석 결과가 없어요"}
              </h3>
              <p>
                {detail.job?.stage === "no_speech"
                  ? "음성이 있는 파일인지 확인해 주세요."
                  : "대화 정리를 누르고 정리할 양식을 선택해 주세요."}
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
        {detail.processing_history
          .filter(
            (entry) =>
              entry.event !== "speech_progress" &&
              entry.event !== "analysis_progress",
          )
          .map((entry, index) => (
            <p key={index}>
              {entry.stage === "speech" ? "음성 처리" : "대화 분석"} ·{" "}
              {entry.metadata.location === "api"
                ? "외부 API"
                : entry.metadata.location === "local"
                  ? "로컬"
                  : (entry.metadata.provider ?? entry.event)}
              {entry.metadata.attempt
                ? ` · 요청 ${entry.metadata.attempt}`
                : ""}
              {entry.metadata.model ? ` · ${entry.metadata.model}` : ""}
              {entry.metadata.fallback_reason
                ? ` · 전환 사유: ${entry.metadata.fallback_reason}`
                : ""}
              {entry.metadata.duplicate_cost_possible
                ? " · 재시도로 추가 요금이 발생할 수 있음"
                : ""}
            </p>
          ))}
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
      {chooseForm && detail.transcript && (
        <AnalysisFormDialog
          forms={forms}
          initial={detail.analysis?.form ?? "meeting"}
          busy={busy}
          onClose={() => setChooseForm(false)}
          onStart={(form) => {
            void act(async () => {
              await api.analyze(id, detail.transcript!.id, mode, form);
              setChooseForm(false);
            });
          }}
        />
      )}
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
              원본 음성, 전사와 분석을 이 Mac에서 삭제해요. 진행 중인 처리도
              중지돼요.
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
