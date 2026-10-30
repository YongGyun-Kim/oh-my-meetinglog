import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { Headphones } from "lucide-react";

export type Player = {
  seek: (ms: number) => void;
  play: (startMs: number, endMs: number) => void;
};
export const AudioPlayer = forwardRef<Player, { id: string }>(
  function AudioPlayer({ id }, ref) {
    const element = useRef<HTMLAudioElement>(null);
    const [error, setError] = useState(false);
    const [playError, setPlayError] = useState(false);
    const range = useRef<{ start: number; end: number } | null>(null);
    const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const clearTimer = () => {
      clearTimeout(timer.current);
      timer.current = undefined;
    };
    const clearRange = () => {
      clearTimer();
      range.current = null;
    };
    const checkRange = () => {
      clearTimer();
      const audio = element.current;
      if (!audio || !range.current) return;
      const end = range.current.end;
      if (audio.currentTime >= end) {
        clearRange();
        audio.pause();
        audio.currentTime = end;
      } else if (!audio.paused && !audio.seeking && audio.playbackRate > 0) {
        timer.current = setTimeout(
          checkRange,
          ((end - audio.currentTime) / audio.playbackRate) * 1000,
        );
      }
    };
    useEffect(() => clearRange, [id]);
    useImperativeHandle(
      ref,
      () => ({
        seek: (ms) => {
          clearRange();
          if (element.current) element.current.currentTime = ms / 1000;
        },
        play: (startMs, endMs) => {
          const audio = element.current;
          if (!audio) return;
          clearRange();
          setPlayError(false);
          const preview = { start: startMs / 1000, end: endMs / 1000 };
          range.current = preview;
          try {
            audio.currentTime = preview.start;
            void audio.play().catch((reason: unknown) => {
              if (
                range.current !== preview ||
                (reason instanceof DOMException && reason.name === "AbortError")
              )
                return;
              clearRange();
              setPlayError(true);
            });
          } catch {
            clearRange();
            setPlayError(true);
          }
        },
      }),
      [],
    );
    return (
      <div className="audio-player">
        <Headphones size={18} />
        <span>원본 음성</span>
        <audio
          ref={element}
          controls
          preload="metadata"
          src={`/api/recordings/${encodeURIComponent(id)}/audio`}
          aria-label="원본 음성 재생"
          onError={() => {
            clearRange();
            setError(true);
          }}
          onLoadedMetadata={() => setError(false)}
          onPlaying={() => {
            setPlayError(false);
            checkRange();
          }}
          onTimeUpdate={checkRange}
          onSeeked={checkRange}
          onRateChange={checkRange}
          onPause={clearTimer}
          onWaiting={clearTimer}
          onEnded={clearRange}
          onPointerDown={clearRange}
          onKeyDown={clearRange}
          onSeeking={() => {
            clearTimer();
            const audio = element.current;
            if (
              audio &&
              range.current &&
              (audio.currentTime < range.current.start ||
                audio.currentTime > range.current.end)
            )
              clearRange();
          }}
        />
        {error && (
          <span className="audio-error">
            재생용 음성을 준비 중이거나 파일을 읽을 수 없어요.
          </span>
        )}
        {playError && !error && (
          <span className="audio-error" role="alert">
            음성을 재생하지 못했어요. 원본 음성 재생바에서 다시 시도해 주세요.
          </span>
        )}
      </div>
    );
  },
);
