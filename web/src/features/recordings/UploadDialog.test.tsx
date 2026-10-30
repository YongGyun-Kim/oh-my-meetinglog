import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { UploadDialog } from "./UploadDialog";

it("rejects files above the limit before transmission", async () => {
  const upload = vi.spyOn(api, "upload");
  const file = new File(["audio"], "too-large.wav", { type: "audio/wav" });
  Object.defineProperty(file, "size", { value: 1_000_000_001 });
  render(<UploadDialog onClose={() => {}} onSaved={() => {}} />);
  await userEvent.upload(screen.getByLabelText("녹음 파일"), file);
  expect(await screen.findByRole("alert")).toHaveTextContent("1GB");
  expect(upload).not.toHaveBeenCalled();
});

it("opens the stored recording after an upload", async () => {
  const saved = vi.fn();
  vi.spyOn(api, "upload").mockResolvedValue({
    id: "record",
    title: "인터뷰",
    source: "file",
    input_state: "ready",
    duration_ms: 1000,
    created_at: "2026-10-16T00:00:00Z",
    generation: 0,
  });
  render(<UploadDialog onClose={() => {}} onSaved={saved} />);
  await userEvent.upload(
    screen.getByLabelText("녹음 파일"),
    new File(["audio"], "interview.wav", { type: "audio/wav" }),
  );
  await waitFor(() => expect(saved).toHaveBeenCalledWith("record"));
});
