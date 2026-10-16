import { useCallback, useEffect, useRef, useState } from "react";
import { api, message } from "../../lib/api";
import type { RecordingDetail } from "../../lib/types";

export function useRecording(id: string) {
  const [detail, setDetail] = useState<RecordingDetail | null>(null);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    try {
      const next = await api.detail(id, controller.signal);
      if (!controller.signal.aborted) {
        setDetail(next);
        setError("");
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(message(reason));
    }
  }, [id]);
  useEffect(() => {
    setDetail(null);
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, 2500);
    return () => {
      clearInterval(timer);
      request.current?.abort();
    };
  }, [refresh]);
  return { detail, refresh, isLoading: !detail && !error, error };
}
