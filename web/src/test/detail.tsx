import { render } from "@testing-library/react";
import { vi } from "vitest";
import type { RecordingDetail as Detail } from "../lib/types";
import { api } from "../lib/api";
import { RecordingDetail } from "../features/detail/RecordingDetail";

export const detailFixture: Detail = {
  recording: {
    id: "rec-1",
    title: "서비스 인터뷰",
    source: "file",
    input_state: "ready",
    duration_ms: 9000,
    generation: 0,
  },
  transcript: {
    id: "v1",
    recording_id: "rec-1",
    speakers: [{ id: "a", display_name: "화자 A", role: null }],
    turns: [
      {
        id: "t1",
        start_ms: 1250,
        end_ms: 4000,
        text_original: "다음 주에 시작합니다.",
        speaker_id: "a",
        review_flags: [],
        words: [],
      },
    ],
  },
  analysis: {
    id: "analysis-1",
    transcript_id: "v1",
    provider: "local",
    model: "test",
    prompt_version: "v1",
    body: {
      overview: {
        kind: "interview",
        summary: {
          text: "시작 시점을 이야기했습니다.",
          evidence_turn_ids: ["t1"],
        },
        main_topics: [],
      },
      topics: [],
      question_answers: [],
      agreements: [],
      open_questions: [],
      actions: [],
    },
  },
  analysis_stale: false,
  job: null,
};

export function renderDetailWithFixture(
  detail: Detail = structuredClone(detailFixture),
) {
  vi.spyOn(api, "detail").mockResolvedValue(detail);
  vi.spyOn(api, "settings").mockResolvedValue({
    mode: "local_only",
    engines: [],
    api_configured: false,
    media_tools_ready: true,
  });
  const view = render(
    <RecordingDetail id="rec-1" onBack={() => {}} onDeleted={() => {}} />,
  );
  return view;
}
