import { useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Check, Pencil, Play, X } from "lucide-react";
import { ApiError, api, clock, message } from "../../lib/api";
import type { Transcript, Sentence } from "../../lib/types";

const flags: Record<string, string> = {
  overlap: "발언 겹침 가능",
  unknown_speaker: "화자 확인 필요",
  alignment_uncertain: "시간 정렬 확인",
  boundary_review: "처리 구간 경계",
  speaker_boundary: "화자 전환 구간",
};

type Draft = {
  text: string;
  speaker: string;
  base: string;
  error: string;
  saving: boolean;
};

function SentenceRow({
  turn,
  speakerId,
  transcript,
  selected,
  onSeek,
  onRefresh,
  readOnly,
  showReview,
  draftState,
  updateDraft,
}: {
  turn: Sentence;
  speakerId: string | null | undefined;
  transcript: Transcript;
  selected: boolean;
  onSeek: (turn: Sentence) => void;
  onRefresh: () => Promise<void>;
  readOnly: boolean;
  showReview: boolean;
  draftState?: Draft;
  updateDraft: (patch: Partial<Draft> | null) => void;
}) {
  const element = useRef<HTMLElement>(null);
  useEffect(() => {
    if (selected) element.current?.scrollIntoView?.({ block: "center" });
  }, [selected]);
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
  const reviewFlags = (turn.review_flags ?? []).filter(
    (flag) => flag !== "unknown_speaker" || speakerId != null,
  );
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
          { sentence_id: turn.id, text: draft, speaker_id: speaker || null },
        ],
      });
      updateDraft(null);
      await onRefresh();
    } catch (reason) {
      setError(
        reason instanceof ApiError && reason.status === 409
          ? "최신 전사가 바뀌었어요. 작성한 내용은 유지돼요. 최신 전사를 불러온 뒤 다시 편집해 주세요."
          : message(reason),
      );
    } finally {
      setSaving(false);
    }
  };
  return (
    <article
      ref={element}
      className={`sentence ${selected ? "selected" : ""}`}
      data-testid={`sentence-${turn.id}`}
      aria-current={selected ? "true" : "false"}
    >
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
          <div className="sentence-line">
            <button
              className="turn-text sentence-text"
              onClick={() => onSeek(turn)}
              title={`${clock(turn.start_ms)}부터 듣기`}
            >
              {turn.text_edited ?? turn.text_original}
            </button>
            {!readOnly && (
              <button
                className="icon-button edit-turn"
                aria-label="발언 수정"
                onClick={() => {
                  updateDraft({
                    text: turn.text_edited ?? turn.text_original,
                    speaker: speakerId ?? "",
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
          {showReview && !!reviewFlags.length && (
            <div className="sentence-flags">
              {reviewFlags.map((flag) => (
                <span className="review-flag" key={flag}>
                  {flags[flag] ?? "검토 필요"}
                </span>
              ))}
            </div>
          )}
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
  selectedSentenceId,
  onSeek,
  onRefresh,
  readOnly = false,
  showReview = false,
}: {
  transcript: Transcript;
  selectedSentenceId: string | null;
  onSeek: (sentence: Sentence) => void;
  onRefresh: () => Promise<void>;
  readOnly?: boolean;
  showReview?: boolean;
}) {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const scroll = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: transcript.turns.length,
    getScrollElement: () => scroll.current,
    estimateSize: (index) => 70 + transcript.turns[index].sentences.length * 42,
    overscan: 5,
    useAnimationFrameWithResizeObserver: true,
    initialRect: { width: 600, height: 620 },
  });
  useEffect(() => {
    const index = transcript.turns.findIndex((turn) =>
      turn.sentences.some((sentence) => sentence.id === selectedSentenceId),
    );
    if (index >= 0) virtualizer.scrollToIndex(index, { align: "center" });
  }, [selectedSentenceId, transcript.id]);
  const items = virtualizer.getVirtualItems();
  return (
    <div className="transcript-scroll" ref={scroll}>
      {!transcript.turns.length ? (
        <p className="empty-message">인식된 음성이 없어요.</p>
      ) : (
        <div
          style={{ height: virtualizer.getTotalSize(), position: "relative" }}
        >
          {(items.length
            ? items
            : transcript.turns
                .slice(0, 10)
                .map((_, index) => ({ index, key: index, start: index * 150 }))
          ).map((item) => {
            const turn = transcript.turns[item.index];
            const name =
              transcript.speakers.find(
                (speaker) => speaker.id === turn.speaker_id,
              )?.display_name ?? "미확인 화자";
            return (
              <div
                key={turn.id}
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
                <article className="turn">
                  <div className="turn-meta">
                    <strong>{name}</strong>
                    <button
                      className="turn-play"
                      aria-label={`${clock(turn.sentences[0].start_ms)} ${name} 발언 듣기`}
                      onClick={() => onSeek(turn.sentences[0])}
                    >
                      <Play size={10} fill="currentColor" />
                      <span>{clock(turn.sentences[0].start_ms)}</span>
                    </button>
                    {!showReview &&
                      turn.sentences.some((sentence) =>
                        sentence.review_flags?.includes("alignment_uncertain"),
                      ) && <span className="review-flag">시간 정렬 확인</span>}
                  </div>
                  {turn.sentences.map((sentence) => (
                    <SentenceRow
                      key={sentence.id}
                      turn={sentence}
                      speakerId={turn.speaker_id}
                      transcript={transcript}
                      selected={sentence.id === selectedSentenceId}
                      onSeek={onSeek}
                      onRefresh={onRefresh}
                      readOnly={readOnly}
                      showReview={showReview}
                      draftState={readOnly ? undefined : drafts[sentence.id]}
                      updateDraft={(patch) =>
                        setDrafts((previous) => {
                          const next = { ...previous };
                          if (patch === null) delete next[sentence.id];
                          else if (previous[sentence.id] || patch.base)
                            next[sentence.id] = {
                              ...previous[sentence.id],
                              ...patch,
                            } as Draft;
                          return next;
                        })
                      }
                    />
                  ))}
                </article>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
