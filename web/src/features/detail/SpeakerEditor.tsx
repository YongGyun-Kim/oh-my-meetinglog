import { useState } from "react";
import { api, message } from "../../lib/api";
import type { Transcript } from "../../lib/types";

export function SpeakerEditor({
  transcript,
  onRefresh,
  onClose,
}: {
  transcript: Transcript;
  onRefresh: () => Promise<void>;
  onClose: () => void;
}) {
  const [opening] = useState(() => structuredClone(transcript));
  const [drafts, setDrafts] = useState(() =>
    opening.speakers.map((item) => ({ ...item })),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const changes = drafts
        .filter(
          (item) =>
            item.role !==
            opening.speakers.find((original) => original.id === item.id)?.role,
        )
        .map((item) => ({ speaker_id: item.id, role: item.role ?? "" }));
      if (changes.length)
        await api.edit(transcript.recording_id, {
          base_version_id: opening.id,
          changes,
        });
      for (const speaker of drafts)
        if (
          speaker.display_name !==
          opening.speakers.find((original) => original.id === speaker.id)
            ?.display_name
        )
          await api.renameSpeaker(
            transcript.recording_id,
            speaker.id,
            speaker.display_name,
          );
      await onRefresh();
      onClose();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="speakers-title"
      >
        <h2 id="speakers-title">화자 정보</h2>
        <p className="muted speaker-help">
          직접 확인한 이름과 역할을 적어 주세요.
        </p>
        {drafts.map((speaker, index) => (
          <div className="speaker-fields" key={speaker.id}>
            <label>
              표시 이름
              <input
                aria-label={`화자 ${index + 1} 이름`}
                value={speaker.display_name}
                maxLength={100}
                onChange={(event) =>
                  setDrafts((items) =>
                    items.map((item) =>
                      item.id === speaker.id
                        ? { ...item, display_name: event.target.value }
                        : item,
                    ),
                  )
                }
              />
            </label>
            <label>
              역할
              <input
                aria-label={`화자 ${index + 1} 역할`}
                placeholder="예: 인터뷰어"
                maxLength={200}
                value={speaker.role ?? ""}
                onChange={(event) =>
                  setDrafts((items) =>
                    items.map((item) =>
                      item.id === speaker.id
                        ? { ...item, role: event.target.value }
                        : item,
                    ),
                  )
                }
              />
            </label>
          </div>
        ))}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="editor-actions">
          <button
            className="button secondary"
            onClick={onClose}
            disabled={busy}
          >
            취소
          </button>
          <button
            className="button primary"
            onClick={() => {
              void save();
            }}
            disabled={busy || drafts.some((item) => !item.display_name.trim())}
          >
            저장
          </button>
        </div>
      </section>
    </div>
  );
}
