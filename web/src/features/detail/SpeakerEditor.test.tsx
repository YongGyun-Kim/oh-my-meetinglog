import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { api, ApiError } from "../../lib/api";
import { detailFixture } from "../../test/detail";
import { SpeakerEditor } from "./SpeakerEditor";

it("keeps the role edit tied to the version that opened the editor", async () => {
  const original = structuredClone(detailFixture.transcript!);
  original.speakers[0].role = "질문자";
  const edit = vi
    .spyOn(api, "edit")
    .mockRejectedValue(new ApiError("다른 창에서 수정되었습니다", 409));
  const refresh = vi.fn().mockResolvedValue(undefined);
  const close = vi.fn();
  const view = render(
    <SpeakerEditor transcript={original} onRefresh={refresh} onClose={close} />,
  );
  await userEvent.clear(screen.getByLabelText("화자 1 역할"));
  await userEvent.type(screen.getByLabelText("화자 1 역할"), "상담자");
  const polled = structuredClone(original);
  polled.id = "v2";
  polled.speakers[0].role = "응답자";
  view.rerender(
    <SpeakerEditor transcript={polled} onRefresh={refresh} onClose={close} />,
  );
  await userEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(edit).toHaveBeenCalledWith("rec-1", {
      base_version_id: "v1",
      changes: [{ speaker_id: "a", role: "상담자" }],
    }),
  );
  expect(screen.getByLabelText("화자 1 역할")).toHaveValue("상담자");
  expect(close).not.toHaveBeenCalled();
});

it("does not revert untouched role or name fields changed by another tab", async () => {
  const original = structuredClone(detailFixture.transcript!);
  const edit = vi.spyOn(api, "edit").mockResolvedValue(original);
  const rename = vi.spyOn(api, "renameSpeaker").mockResolvedValue({});
  const close = vi.fn();
  const view = render(
    <SpeakerEditor
      transcript={original}
      onRefresh={async () => {}}
      onClose={close}
    />,
  );
  const polled = structuredClone(original);
  polled.id = "v2";
  polled.speakers[0].role = "다른 탭의 역할";
  polled.speakers[0].display_name = "다른 탭의 이름";
  view.rerender(
    <SpeakerEditor
      transcript={polled}
      onRefresh={async () => {}}
      onClose={close}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() => expect(close).toHaveBeenCalled());
  expect(edit).not.toHaveBeenCalled();
  expect(rename).not.toHaveBeenCalled();
});
