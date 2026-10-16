import { useRef, useState } from 'react'
import { FileAudio, Upload, X } from 'lucide-react'
import { api, message } from '../../lib/api'

export function UploadDialog({ onClose, onSaved }: { onClose: () => void; onSaved: (id: string) => void }) {
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const busy = useRef(false)
  const upload = async (file?: File) => {
    if (!file || busy.current) return
    setError('')
    if (file.size > 1_000_000_000) { setError('파일은 1GB 이하로 가져올 수 있습니다.'); return }
    if (!file.size) { setError('비어 있는 파일입니다. 다른 녹음 파일을 선택해 주세요.'); return }
    busy.current = true; setName(file.name); setProgress(0)
    try { const record = await api.upload(file, setProgress); onSaved(record.id) }
    catch (reason) { setError(message(reason)); setProgress(null) }
    finally { busy.current = false }
  }
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="upload-title">
    <div className="modal-heading"><div><span className="eyebrow">IMPORT AUDIO</span><h2 id="upload-title">녹음 파일 가져오기</h2></div><button className="icon-button" aria-label="닫기" disabled={progress !== null} onClick={onClose}><X size={20} /></button></div>
    <label className={`dropzone ${progress !== null ? 'busy' : ''}`} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); void upload(event.dataTransfer.files[0]) }}>
      <span className="drop-icon"><FileAudio size={28} strokeWidth={1.6} /></span><strong>{progress === null ? '파일을 선택하거나 여기에 놓으세요' : name}</strong><span>MP3, M4A, WAV, WebM 등 · 최대 2시간 / 1GB</span>
      <input aria-label="녹음 파일" type="file" accept="audio/*,.mp4,.webm,.m4a,.wav,.mp3,.flac,.ogg,.aiff" disabled={progress !== null} onChange={event => { void upload(event.target.files?.[0]); event.target.value = '' }} />
      {progress === null && <span className="button secondary"><Upload size={16} /> 파일 선택</span>}
    </label>
    {progress !== null && <div className="upload-progress"><progress max="1" value={progress} aria-label="파일 전송 진행" /><p>{progress === 1 ? '파일을 확인하고 있습니다…' : `전송 중 ${Math.round(progress * 100)}%`}</p></div>}
    {error && <p className="error" role="alert">{error}</p>}
    <p className="help">원본 파일을 보관하고, 전사와 대화 정리를 순서대로 진행합니다.</p>
  </section></div>
}
