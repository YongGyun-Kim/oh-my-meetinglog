import { act, renderHook } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../lib/api";
import { useRecorder } from "../features/recordings/useRecorder";

export class FakeRecorder extends EventTarget {
  static latest: FakeRecorder;
  static isTypeSupported = () => true;
  state = "inactive";
  mimeType = "audio/webm;codecs=opus";
  stop = vi.fn(() => {
    this.state = "inactive";
  });
  constructor() {
    super();
    FakeRecorder.latest = this;
  }
  start() {
    this.state = "recording";
  }
  chunk(body: Blob) {
    const event = new Event("dataavailable");
    Object.defineProperty(event, "data", { value: body });
    this.dispatchEvent(event);
  }
  stopped() {
    this.dispatchEvent(new Event("stop"));
  }
}

export function renderRecorderWithFakeMedia() {
  const trackStop = vi.fn();
  const getUserMedia = vi
    .fn()
    .mockResolvedValue({ getTracks: () => [{ stop: trackStop }] });
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  const record = {
    id: "rec-1",
    title: "녹음",
    source: "microphone" as const,
    input_state: "ready" as const,
    created_at: "2026-10-16T00:00:00Z",
    generation: 0,
    duration_ms: 1000,
  };
  vi.spyOn(api, "createDraft").mockResolvedValue({
    ...record,
    input_state: "recording",
  });
  const put = vi.spyOn(api, "putChunk").mockResolvedValue(undefined);
  const finalize = vi.spyOn(api, "finalize").mockResolvedValue(record);
  const saved = vi.fn();
  const hook = renderHook(() => useRecorder(saved));
  return {
    ...hook,
    getUserMedia,
    trackStop,
    saved,
    api: { put, finalize },
    start: () =>
      act(async () => {
        await hook.result.current.start();
      }),
    stop: () =>
      act(() => {
        hook.result.current.stop();
      }),
    emitChunk: (blob: Blob) => act(() => FakeRecorder.latest.chunk(blob)),
    emitStopped: () => act(() => FakeRecorder.latest.stopped()),
  };
}
