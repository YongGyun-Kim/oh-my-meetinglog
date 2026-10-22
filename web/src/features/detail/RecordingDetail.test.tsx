import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { detailFixture, renderDetailWithFixture } from "../../test/detail";
import { ApiError, api } from "../../lib/api";

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
});

it("seeks audio and selects the original cited turn", async () => {
  const view = renderDetailWithFixture();
  await userEvent.click(
    await screen.findByRole("button", { name: "근거 보기" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "근거 문장 t1" }),
  );
  expect(view.getByTestId("sentence-t1")).toHaveAttribute(
    "aria-current",
    "true",
  );
  expect(view.container.querySelector("audio")?.currentTime).toBe(1.25);
  expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
  view.container.querySelector("audio")!.currentTime = 0;
  await userEvent.click(
    screen.getByRole("button", { name: "00:01 화자 A 발언 듣기" }),
  );
  expect(view.container.querySelector("audio")?.currentTime).toBe(1.25);
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
});

it("labels previous analysis after transcript edits", async () => {
  const detail = structuredClone(detailFixture);
  detail.analysis_stale = true;
  renderDetailWithFixture(detail);
  expect(
    await screen.findByText(/수정 전 전사를 바탕으로/),
  ).toBeInTheDocument();
});

it("preserves an edit draft after a version conflict", async () => {
  vi.spyOn(api, "edit").mockRejectedValue(
    new ApiError("다른 창에서 수정되었습니다", 409, "version_conflict"),
  );
  renderDetailWithFixture();
  await userEvent.click(
    await screen.findByRole("button", { name: "발언 수정" }),
  );
  const editor = screen.getByLabelText("발언 내용");
  await userEvent.clear(editor);
  await userEvent.type(editor, "수정한 문장입니다.");
  await userEvent.click(screen.getByRole("button", { name: "수정 저장" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("최신 전사");
  expect(editor).toHaveValue("수정한 문장입니다.");
  expect(api.edit).toHaveBeenCalledWith(
    "rec-1",
    expect.objectContaining({ base_version_id: "v1" }),
  );
});

it("renders model content as text and leaves absent facts absent", async () => {
  const detail = structuredClone(detailFixture);
  detail.analysis!.body.overview.summary.text = "<img src=x onerror=alert(1)>";
  const view = renderDetailWithFixture(detail);
  await waitFor(() =>
    expect(
      screen.getByText("<img src=x onerror=alert(1)>"),
    ).toBeInTheDocument(),
  );
  expect(view.container.querySelector("img")).toBeNull();
  expect(screen.queryByText("담당자 미정")).not.toBeInTheDocument();
});

it("opens form selection without analysis and submits the chosen form", async () => {
  vi.spyOn(api, "analyze").mockResolvedValue({} as never);
  renderDetailWithFixture();
  await userEvent.click(
    await screen.findByRole("button", { name: "다시 정리" }),
  );
  expect(api.analyze).not.toHaveBeenCalled();
  const choice = await screen.findByLabelText("정리 폼");
  await userEvent.selectOptions(choice, "project");
  expect(api.analyze).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "정리 시작" }));
  await waitFor(() =>
    expect(api.analyze).toHaveBeenCalledWith(
      "rec-1",
      "v1",
      "local_only",
      "project",
    ),
  );
});

it("seeks the clicked sentence inside a shared speaker turn", async () => {
  const detail = structuredClone(detailFixture);
  detail.transcript!.turns[0].sentences.push({
    id: "second",
    start_ms: 2800,
    end_ms: 3500,
    text_original: "두 번째 문장입니다.",
  });
  const view = renderDetailWithFixture(detail);
  await userEvent.click(
    await screen.findByRole("button", { name: "두 번째 문장입니다." }),
  );
  expect(view.container.querySelector("audio")?.currentTime).toBe(2.8);
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
  expect(view.getByTestId("sentence-second")).toHaveAttribute(
    "aria-current",
    "true",
  );
});

it("hides evidence by default and toggles it without calling the model", async () => {
  const analyze = vi.spyOn(api, "analyze");
  renderDetailWithFixture();
  const toggle = await screen.findByRole("button", { name: "근거 보기" });
  expect(screen.queryByRole("button", { name: "근거 문장 t1" })).toBeNull();
  await userEvent.click(toggle);
  expect(screen.getByRole("button", { name: "근거 문장 t1" })).toBeVisible();
  expect(toggle).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "근거 숨기기" }));
  expect(screen.queryByRole("button", { name: "근거 문장 t1" })).toBeNull();
  expect(analyze).not.toHaveBeenCalled();
});

it("groups sentence lines under one speaker and stops at the next sentence", async () => {
  const detail = structuredClone(detailFixture);
  detail.transcript!.turns[0].sentences.push({
    id: "second",
    start_ms: 4500,
    end_ms: 5000,
    text_original: "두 번째 문장입니다.",
  });
  const view = renderDetailWithFixture(detail);
  const first = await screen.findByRole("button", {
    name: "다음 주에 시작합니다.",
  });
  expect(view.container.querySelectorAll(".turn")).toHaveLength(1);
  expect(view.container.querySelectorAll(".turn-play")).toHaveLength(1);
  expect(screen.getAllByRole("button", { name: "발언 수정" })).toHaveLength(2);
  await userEvent.click(first);
  const audio = view.container.querySelector("audio")!;
  expect(audio.currentTime).toBe(1.25);
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
  audio.currentTime = 4.6;
  fireEvent.timeUpdate(audio);
  expect(HTMLMediaElement.prototype.pause).toHaveBeenCalledOnce();
  expect(audio.currentTime).toBe(4.5);
});

it("keeps review reasons optional and avoids duplicate unknown-speaker warnings", async () => {
  const detail = structuredClone(detailFixture);
  detail.transcript!.turns[0].sentences[0].review_flags = [
    "speaker_boundary",
    "alignment_uncertain",
  ];
  detail.transcript!.turns[0].sentences.push({
    id: "second",
    start_ms: 4500,
    end_ms: 5000,
    text_original: "둘째 문장",
    review_flags: ["alignment_uncertain", "boundary_review"],
  });
  detail.transcript!.turns.push({
    id: "unknown",
    speaker_id: null,
    sentences: [
      {
        id: "third",
        start_ms: 5000,
        end_ms: 6000,
        text_original: "짧은 응답",
        review_flags: ["overlap", "unknown_speaker"],
      },
    ],
  });
  const analyze = vi.spyOn(api, "analyze");
  const edit = vi.spyOn(api, "edit");
  const view = renderDetailWithFixture(detail);
  const toggle = await screen.findByRole("button", { name: "검토 정보 보기" });
  expect(screen.getByText("미확인 화자")).toBeVisible();
  expect(view.container.querySelectorAll(".review-flag")).toHaveLength(1);
  expect(screen.queryByText("화자 전환 구간")).toBeNull();
  expect(screen.queryByText("발언 겹침 가능")).toBeNull();
  await userEvent.click(toggle);
  expect(screen.getByText("화자 전환 구간")).toBeVisible();
  expect(screen.getByText("발언 겹침 가능")).toBeVisible();
  expect(screen.queryByText("화자 확인 필요")).toBeNull();
  expect(toggle).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(
    screen.getByRole("button", { name: "검토 정보 숨기기" }),
  );
  expect(view.container.querySelectorAll(".review-flag")).toHaveLength(1);
  expect(analyze).not.toHaveBeenCalled();
  expect(edit).not.toHaveBeenCalled();
});
