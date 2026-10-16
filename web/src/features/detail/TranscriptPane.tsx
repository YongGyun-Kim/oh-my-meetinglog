import { useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Check, Pencil, Play, X } from "lucide-react";
import { ApiError, api, clock, message } from "../../lib/api";
import type { Transcript, Turn } from "../../lib/types";

const flags: Record<string, string> = {
  overlap: "겹친 발언",
  unknown_speaker: "화자 확인 필요",
  alignment_uncertain: "시간 정렬 확인",
  boundary_review: "구간 경계 확인",
  speaker_boundary: "화자 경계 확인",
};

type Draft = {
  text: string;
  speaker: string;
  base: string;
  error: string;
  saving: boolean;
};

function TurnRow({
  turn,
  transcript,
  selected,
  onSeek,
  onRefresh,
  readOnly,
  draftState,
  updateDraft,
}: {
  turn: Turn;
  transcript: Transcript;
  selected: boolean;
  onSeek: (turn: Turn) => void;
  onRefresh: () => Promise<void>;
  readOnly: boolean;
  draftState?: Draft;
  updateDraft: (patch: Partial<Draft> | null) => void;
}) {
  const editing = draftState !== undefined;
  const draft = draftState?.text ?? "";
  const speaker = draftState?.speaker ?? "";
  const base = draftState?.base ?? "";
  const error = draftState?.error ?? "";
  const saving = draftState?.saving ?? false;
  const setDraft = (text: string) => updateDraft({ text });
  const setSpeaker = (speaker: string) => updateDraft({ speaker });
  const setError = (error: string) => updateDraft({ error });
  const setSaving = (saving: boolean) => updateDraft({ saving });
  const name =
    transcript.speakers.find((item) => item.id === turn.speaker_id)
      ?.display_name ?? "미확인 화자";
  const save = async () => {
    if (!draft.trim()) {
      setError("발언 내용을 입력해 주세요.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.edit(transcript.recording_id, {
        base_version_id: base,
        changes: [
          { turn_id: turn.id, text: draft, speaker_id: speaker || null },
        ],
      });
      updateDraft(null);
      await onRefresh();
    } catch (reason) {
      setError(
        reason instanceof ApiError && reason.status === 409
          ? "최신 전사가 변경되었습니다. 작성한 내용은 유지됩니다. 최신 전사를 불러온 뒤 다시 편집해 주세요."
          : message(reason),
      );
    } finally {
      setSaving(false);
    }
  };
  return (
    <article
      className={`turn ${selected ? "selected" : ""}`}
      data-testid={`turn-${turn.id}`}
      aria-current={selected ? "true" : "false"}
    >
      <div className="turn-meta">
        <button
          className="turn-play"
          aria-label={`${clock(turn.start_ms)} ${name} 발언 듣기`}
          onClick={() => onSeek(turn)}
        >
          <Play size={10} fill="currentColor" />
          <span>{clock(turn.start_ms)}</span>
        </button>
        <strong>{name}</strong>
        {turn.review_flags?.map((flag) => (
          <span className="review-flag" key={flag}>
            {flags[flag] ?? "검토 필요"}
          </span>
        ))}
        {!readOnly && !editing && (
          <button
            className="icon-button edit-turn"
            aria-label="발언 수정"
            onClick={() => {
              updateDraft({
                text: turn.text_edited ?? turn.text_original,
                speaker: turn.speaker_id ?? "",
                base: transcript.id,
                error: "",
                saving: false,
              });
            }}
          >
            <Pencil size={13} />
          </button>
        )}
      </div>
      {editing ? (
        <div className="turn-editor">
          <label>
            발언 내용
            <textarea
              aria-label="발언 내용"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={4}
            />
          </label>
          <label>
            발언 화자
            <select
              aria-label="발언 화자"
              value={speaker}
              onChange={(event) => setSpeaker(event.target.value)}
            >
              <option value="">미확인 화자</option>
              {transcript.speakers.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          {error && (
            <p className="error" role="alert">
              {error}
              <button
                className="text-button"
                onClick={() => {
                  void onRefresh();
                }}
              >
                최신 전사 불러오기
              </button>
            </p>
          )}
          <div className="editor-actions">
            <button
              className="button secondary"
              disabled={saving}
              onClick={() => updateDraft(null)}
            >
              <X size={13} />
              취소
            </button>
            <button
              className="button primary"
              disabled={saving}
              onClick={() => {
                void save();
              }}
            >
              <Check size={13} />
              수정 저장
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="turn-text">{turn.text_edited ?? turn.text_original}</p>
          {turn.text_edited !== null && turn.text_edited !== undefined && (
            <details className="original-text">
              <summary>수정 전 원문</summary>
              <p>{turn.text_original}</p>
            </details>
          )}
        </>
      )}
    </article>
  );
}

export function TranscriptPane({
  transcript,
  selectedTurnId,
  onSeek,
  onRefresh,
  readOnly = false,
}: {
  transcript: Transcript;
  selectedTurnId: string | null;
  onSeek: (turn: Turn) => void;
  onRefresh: () => Promise<void>;
  readOnly?: boolean;
}) {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const scroll = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: transcript.turns.length,
    getScrollElement: () => scroll.current,
    estimateSize: () => 126,
    overscan: 5,
    useAnimationFrameWithResizeObserver: true,
    initialRect: { width: 600, height: 620 },
  });
  useEffect(() => {
    const index = transcript.turns.findIndex(
      (turn) => turn.id === selectedTurnId,
    );
    if (index >= 0) virtualizer.scrollToIndex(index, { align: "center" });
  }, [selectedTurnId, transcript.id]); // A seek deliberately moves the viewport; passive polls do not.
  const items = virtualizer.getVirtualItems();
  return (
    <div className="transcript-scroll" ref={scroll}>
      {!transcript.turns.length ? (
        <p className="empty-message">인식된 음성이 없습니다.</p>
      ) : (
        <div
          style={{ height: virtualizer.getTotalSize(), position: "relative" }}
        >
          {(items.length
            ? items
            : transcript.turns
                .slice(0, 10)
                .map((_, index) => ({ index, key: index, start: index * 126 }))
          ).map((item) => (
            <div
              key={transcript.turns[item.index].id}
              ref={virtualizer.measureElement}
              data-index={item.index}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${item.start}px)`,
              }}
            >
              <TurnRow
                turn={transcript.turns[item.index]}
                transcript={transcript}
                selected={transcript.turns[item.index].id === selectedTurnId}
                onSeek={onSeek}
                onRefresh={onRefresh}
                readOnly={readOnly}
                draftState={
                  readOnly ? undefined : drafts[transcript.turns[item.index].id]
                }
                updateDraft={(patch) => {
                  const id = transcript.turns[item.index].id;
                  setDrafts((previous) => {
                    const next = { ...previous };
                    if (patch === null) delete next[id];
                    else if (previous[id] || patch.base)
                      next[id] = { ...previous[id], ...patch } as Draft;
                    return next;
                  });
                }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
