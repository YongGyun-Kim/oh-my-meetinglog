import { createRef } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AudioPlayer, type Player } from "./AudioPlayer";

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
});

it("ends a sentence preview and leaves the native player free to continue", () => {
  const ref = createRef<Player>();
  const view = render(<AudioPlayer id="sample" ref={ref} />);
  const audio = view.container.querySelector("audio")!;
  act(() => ref.current!.play(1250, 2200));
  expect(audio.currentTime).toBe(1.25);
  expect(audio.play).toHaveBeenCalledOnce();
  audio.currentTime = 2.3;
  fireEvent.timeUpdate(audio);
  expect(audio.pause).toHaveBeenCalledOnce();
  expect(audio.currentTime).toBe(2.2);
  audio.currentTime = 3;
  fireEvent.timeUpdate(audio);
  expect(audio.pause).toHaveBeenCalledOnce();
});

it("replaces the old playback boundary and releases it on ordinary seeking", () => {
  const ref = createRef<Player>();
  const view = render(<AudioPlayer id="sample" ref={ref} />);
  const audio = view.container.querySelector("audio")!;
  act(() => ref.current!.play(1250, 2200));
  act(() => ref.current!.play(3000, 4000));
  fireEvent.timeUpdate(audio);
  expect(audio.pause).not.toHaveBeenCalled();
  act(() => ref.current!.seek(5000));
  fireEvent.timeUpdate(audio);
  expect(audio.currentTime).toBe(5);
  expect(audio.pause).not.toHaveBeenCalled();
});

it("reports playback rejection instead of silently failing", async () => {
  vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValue(
    new Error("blocked"),
  );
  const ref = createRef<Player>();
  render(<AudioPlayer id="sample" ref={ref} />);
  await act(async () => ref.current!.play(1250, 2200));
  expect(await screen.findByRole("alert")).toHaveTextContent("재생");
  fireEvent.playing(screen.getByLabelText("원본 음성 재생"));
  expect(screen.queryByRole("alert")).toBeNull();
});

it.each(["pointerDown", "keyDown"] as const)(
  "releases sentence preview when the native controls receive %s",
  (event) => {
    const ref = createRef<Player>();
    const view = render(<AudioPlayer id="sample" ref={ref} />);
    const audio = view.container.querySelector("audio")!;
    act(() => ref.current!.play(1250, 2200));
    fireEvent[event](audio);
    audio.currentTime = 3;
    fireEvent.timeUpdate(audio);
    expect(audio.currentTime).toBe(3);
    expect(audio.pause).not.toHaveBeenCalled();
  },
);

it("reschedules the stop after pausing or changing speed and clears it on unmount", () => {
  vi.useFakeTimers();
  const ref = createRef<Player>();
  const view = render(<AudioPlayer id="sample" ref={ref} />);
  try {
    const audio = view.container.querySelector("audio")!;
    Object.defineProperty(audio, "paused", {
      configurable: true,
      value: false,
    });
    act(() => ref.current!.play(1000, 2000));
    fireEvent.playing(audio);
    fireEvent.pause(audio);
    act(() => vi.advanceTimersByTime(1500));
    expect(audio.pause).not.toHaveBeenCalled();
    audio.playbackRate = 2;
    fireEvent.playing(audio);
    audio.currentTime = 2.1;
    act(() => vi.advanceTimersByTime(500));
    expect(audio.pause).toHaveBeenCalledOnce();
    expect(audio.currentTime).toBe(2);
    act(() => ref.current!.play(3000, 4000));
    fireEvent.playing(audio);
    audio.currentTime = 4.1;
    view.unmount();
    act(() => vi.runAllTimers());
    expect(audio.pause).toHaveBeenCalledOnce();
  } finally {
    view.unmount();
    vi.useRealTimers();
  }
});
