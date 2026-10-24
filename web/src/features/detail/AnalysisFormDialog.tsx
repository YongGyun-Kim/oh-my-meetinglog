import { useEffect, useRef, useState } from "react";
import type { AnalysisForm, FormOption } from "../../lib/types";

export function AnalysisFormDialog({
  forms,
  initial,
  busy,
  onClose,
  onStart,
}: {
  forms: FormOption[];
  initial: AnalysisForm;
  busy: boolean;
  onClose: () => void;
  onStart: (form: AnalysisForm) => void;
}) {
  const [form, setForm] = useState(initial);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLSelectElement>("select")?.focus();
    return () => previous?.focus();
  }, []);
  return (
    <div className="modal-backdrop">
      <section
        ref={panel}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="analysis-form-title"
        onKeyDown={(event) => {
          if (event.key === "Escape" && !busy) onClose();
          if (event.key === "Tab") {
            const controls = panel.current?.querySelectorAll<HTMLElement>(
              "select:not(:disabled), button:not(:disabled)",
            );
            if (!controls?.length) return;
            const first = controls[0],
              last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <h2 id="analysis-form-title">어떤 양식으로 정리할까요?</h2>
        <label className="analysis-form-choice">
          정리 양식
          <select
            aria-label="정리 양식"
            value={form}
            disabled={busy}
            onChange={(event) => setForm(event.target.value as AnalysisForm)}
          >
            {forms.map((option) => (
              <option key={option.id} value={option.id}>
                {option.title}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">
          {forms.find((option) => option.id === form)?.description}
        </p>
        <ol className="form-preview" aria-label="정리할 항목">
          {forms
            .find((option) => option.id === form)
            ?.sections.map((section) => (
              <li key={section}>{section}</li>
            ))}
        </ol>
        <p className="muted">선택한 양식으로 대화 내용을 새로 정리해요.</p>
        <div className="editor-actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={onClose}
          >
            취소
          </button>
          <button
            className="button primary"
            disabled={busy || !forms.some((option) => option.id === form)}
            onClick={() => onStart(form)}
          >
            정리 시작
          </button>
        </div>
      </section>
    </div>
  );
}
