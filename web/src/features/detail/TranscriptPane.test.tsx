import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { detailFixture } from "../../test/detail";
import { TranscriptPane } from "./TranscriptPane";

const windowed = vi.hoisted(() => ({ index: 0 }));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: () => ({
    getVirtualItems: () => [
      {
        index: windowed.index,
        key: windowed.index,
        start: windowed.index * 126,
      },
    ],
    getTotalSize: () => 4000,
    measureElement: () => {},
    scrollToIndex: () => {},
  }),
}));

it("retains an unsaved edit when its row leaves the virtual viewport", async () => {
  const transcript = structuredClone(detailFixture.transcript!);
  transcript.turns = Array.from({ length: 30 }, (_, index) => ({
    ...transcript.turns[0],
    id: `t${index}`,
    text_original: `원문 ${index}`,
  }));
  const props = {
    transcript,
    selectedTurnId: null,
    onSeek: () => {},
    onRefresh: async () => {},
  };
  const view = render(<TranscriptPane {...props} />);
  await userEvent.click(screen.getByRole("button", { name: "발언 수정" }));
  await userEvent.clear(screen.getByLabelText("발언 내용"));
  await userEvent.type(screen.getByLabelText("발언 내용"), "저장 전 초안");
  windowed.index = 20;
  view.rerender(<TranscriptPane {...props} />);
  expect(screen.queryByLabelText("발언 내용")).not.toBeInTheDocument();
  windowed.index = 0;
  view.rerender(<TranscriptPane {...props} />);
  expect(screen.getByLabelText("발언 내용")).toHaveValue("저장 전 초안");
  view.rerender(<TranscriptPane {...props} readOnly />);
  expect(screen.queryByLabelText("발언 내용")).not.toBeInTheDocument();
  view.rerender(<TranscriptPane {...props} />);
  expect(screen.getByLabelText("발언 내용")).toHaveValue("저장 전 초안");
});
