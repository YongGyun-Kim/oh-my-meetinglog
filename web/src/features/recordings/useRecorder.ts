import { useCallback, useEffect, useRef, useState } from 'react'
import { api, message } from '../../lib/api'

type State = 'idle' | 'starting' | 'recording' | 'saving' | 'saved' | 'error'
const LIMIT = 7_200_000

export function useRecorder(onSaved: (id: string) => void) {
  const [state, setState] = useState<State>('idle')
  const [elapsedMs, setElapsed] = useState(0)
  const [level, setLevel] = useState(0)
  const [error, setError] = useState('')
  const alive = useRef(true)
  const busy = useRef(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const audio = useRef<AudioContext | null>(null)
  const interval = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const frame = useRef<number | undefined>(undefined)
  const saved = useRef(onSaved); saved.current = onSaved
  const release = useCallback(() => {
    stream.current?.getTracks().forEach(track => track.stop()); stream.current = null
    if (audio.current) { void audio.current.close().catch(() => {}); audio.current = null }
    clearInterval(interval.current)
    if (frame.current !== undefined) cancelAnimationFrame(frame.current)
    if (alive.current) setLevel(0)
  }, [])
  const stop = useCallback(() => {
    if (recorder.current?.state === 'recording') {
      if (alive.current) setState(current => current === 'error' ? current : 'saving')
      recorder.current.stop()
    }
  }, [])
  useEffect(() => {
    alive.current = true
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (busy.current) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => { alive.current = false; stop(); release(); window.removeEventListener('beforeunload', beforeUnload) }
  }, [release, stop])

  const start = useCallback(async () => {
    if (busy.current) return
    busy.current = true; setError(''); setElapsed(0); setState('starting')
    let failed = false
    const fail = (reason: unknown) => {
      failed = true
      if (alive.current) { setError(message(reason)); setState('error') }
      stop(); release(); busy.current = false
    }
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('이 브라우저에서 마이크 녹음을 사용할 수 없습니다. Chrome에서 열거나 녹음 파일을 가져와 주세요.')
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4;codecs=mp4a.40.2', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type))
      if (!mimeType) throw new Error('지원하는 녹음 형식이 없습니다. 녹음 파일을 가져와 주세요.')
      const media = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } })
      stream.current = media
      if (!alive.current) { release(); return }
      const title = `${new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date())} 녹음`
      const draft = await api.createDraft(title)
      if (!alive.current) { release(); return }
      const capture = new MediaRecorder(media, { mimeType })
      recorder.current = capture
      let queue = Promise.resolve(), sequence = 0, pendingBytes = 0
      capture.addEventListener('dataavailable', event => {
        if (!event.data.size || failed) return
        pendingBytes += event.data.size
        if (pendingBytes > 32 * 1024 * 1024) { fail(new Error('녹음 저장이 지연되어 중지했습니다. 서버 연결을 확인한 뒤 다시 녹음해 주세요.')); return }
        const current = sequence++
        queue = queue.then(async () => {
          if (failed) return
          // A repeated sequence is idempotent; retry a transient connection failure once.
          try { await api.putChunk(draft.id, current, event.data) }
          catch { await api.putChunk(draft.id, current, event.data) }
          pendingBytes -= event.data.size
        }).catch(fail)
      })
      capture.addEventListener('error', () => fail(new Error('마이크 녹음이 중단되었습니다. 마이크 연결과 권한을 확인해 주세요.')))
      capture.addEventListener('stop', async () => {
        release()
        await queue
        if (failed) return
        if (!sequence) { fail(new Error('저장된 음성이 없습니다. 마이크를 확인한 뒤 다시 녹음해 주세요.')); return }
        try {
          await api.finalize(draft.id, sequence - 1)
          busy.current = false
          if (alive.current) { setState('saved'); saved.current(draft.id) }
        } catch (reason) { fail(reason) }
      })
      capture.start(5000); setState('recording')
      const started = Date.now()
      interval.current = setInterval(() => {
        const elapsed = Date.now() - started
        if (alive.current) setElapsed(Math.min(elapsed, LIMIT))
        if (elapsed >= LIMIT) stop()
      }, 500)
      if (typeof AudioContext !== 'undefined') {
        try {
          const context = new AudioContext(); audio.current = context
          const analyser = context.createAnalyser(); analyser.fftSize = 256
          context.createMediaStreamSource(media).connect(analyser)
          const values = new Uint8Array(analyser.fftSize)
          const update = () => {
            if (!alive.current || !audio.current) return
            analyser.getByteTimeDomainData(values)
            setLevel(Math.min(1, Math.sqrt(values.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / values.length) * 5))
            frame.current = requestAnimationFrame(update)
          }
          update()
        } catch { /* Recording can continue without the optional level meter. */ }
      }
    } catch (reason) {
      fail(reason instanceof DOMException && reason.name === 'NotAllowedError' ? new Error('마이크 권한이 필요합니다. 주소창의 사이트 권한에서 마이크를 허용해 주세요.') : reason)
    }
  }, [release, stop])
  return { state, elapsedMs, level, error, start, stop }
}
