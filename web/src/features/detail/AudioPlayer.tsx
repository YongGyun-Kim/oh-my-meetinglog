import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Headphones } from "lucide-react";

export type Player = { seek: (ms: number) => void };
export const AudioPlayer = forwardRef<Player, { id: string }>(
  function AudioPlayer({ id }, ref) {
    const element = useRef<HTMLAudioElement>(null);
    const [error, setError] = useState(false);
    useImperativeHandle(
      ref,
      () => ({
        seek: (ms) => {
          if (element.current) element.current.currentTime = ms / 1000;
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
          onError={() => setError(true)}
          onLoadedMetadata={() => setError(false)}
        />
        {error && (
          <span className="audio-error">
            재생용 음성을 준비 중이거나 파일을 읽을 수 없습니다.
          </span>
        )}
      </div>
    );
  },
);
