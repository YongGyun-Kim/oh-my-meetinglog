import { act, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FakeRecorder, renderRecorderWithFakeMedia } from "../../test/media";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("recording lifecycle", () => {
  it("waits for the final audio chunk and ACK before finalizing", async () => {
    const capture = renderRecorderWithFakeMedia();
    await capture.start();
    capture.emitChunk(new Blob(["first"]));
    capture.stop();
    expect(capture.api.finalize).not.toHaveBeenCalled();
    capture.emitChunk(new Blob(["last"]));
    capture.emitStopped();
    await waitFor(() => expect(capture.saved).toHaveBeenCalledWith("rec-1"));
    expect(capture.api.finalize).toHaveBeenCalledWith("rec-1", 1);
    expect(capture.trackStop).toHaveBeenCalled();
  });

  it("keeps failed chunk uploads out of finalization and releases the mic", async () => {
    const capture = renderRecorderWithFakeMedia();
    capture.api.put.mockRejectedValue(new Error("저장 실패"));
    await capture.start();
    capture.emitChunk(new Blob(["first"]));
    await waitFor(() => expect(capture.result.current.state).toBe("error"));
    capture.emitStopped();
    await waitFor(() => expect(capture.trackStop).toHaveBeenCalled());
    expect(capture.api.finalize).not.toHaveBeenCalled();
  });

  it("handles permission denial without creating a recording", async () => {
    const capture = renderRecorderWithFakeMedia();
    capture.getUserMedia.mockRejectedValue(
      new DOMException("Denied", "NotAllowedError"),
    );
    await capture.start();
    expect(capture.result.current.state).toBe("error");
    expect(capture.result.current.error).toMatch(/마이크/);
    expect(capture.api.finalize).not.toHaveBeenCalled();
  });

  it("stops once when stop is pressed repeatedly", async () => {
    const capture = renderRecorderWithFakeMedia();
    await capture.start();
    capture.stop();
    capture.stop();
    expect(FakeRecorder.latest.stop).toHaveBeenCalledTimes(1);
    capture.emitChunk(new Blob(["last"]));
    capture.emitStopped();
    await waitFor(() => expect(capture.saved).toHaveBeenCalled());
  });

  it("does not finalize until the last upload is acknowledged", async () => {
    const capture = renderRecorderWithFakeMedia();
    let acknowledge!: () => void;
    capture.api.put.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          acknowledge = resolve;
        }),
    );
    await capture.start();
    capture.emitChunk(new Blob(["final"]));
    capture.stop();
    capture.emitStopped();
    await waitFor(() => expect(capture.api.put).toHaveBeenCalledTimes(1));
    expect(capture.api.finalize).not.toHaveBeenCalled();
    acknowledge();
    await waitFor(() => expect(capture.saved).toHaveBeenCalled());
  });

  it("automatically stops at the two hour recording limit", async () => {
    vi.useFakeTimers();
    const capture = renderRecorderWithFakeMedia();
    await capture.start();
    act(() => {
      vi.advanceTimersByTime(7_200_001);
    });
    expect(FakeRecorder.latest.stop).toHaveBeenCalledTimes(1);
    capture.unmount();
  });
});
