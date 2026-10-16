import { useCallback, useEffect, useState } from 'react'
import { AudioLines, FolderOpen, Settings, Upload } from 'lucide-react'
import { api, message } from './lib/api'
import type { RecordingSummary } from './lib/types'
import { Recorder } from './features/recordings/Recorder'
import { RecordingList } from './features/recordings/RecordingList'
import { UploadDialog } from './features/recordings/UploadDialog'

export default function App() {
  const [records, setRecords] = useState<RecordingSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [upload, setUpload] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const refresh = useCallback(async () => {
    try { setRecords(await api.listRecordings()); setError('') } catch (reason) { setError(message(reason)) } finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh(); const interval = setInterval(() => { void refresh() }, 3500); return () => clearInterval(interval) }, [refresh])
  const saved = (id: string) => { setUpload(false); setSelected(id); void refresh() }
  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#" onClick={() => setSelected(null)}><span><AudioLines size={23} /></span>대화록<span className="brand-dot">.</span></a><span className="workspace-label">PERSONAL WORKSPACE</span><nav><button className="nav-item active" onClick={() => setSelected(null)}><FolderOpen size={18} />모든 기록<span>{records.length}</span></button></nav><div className="sidebar-bottom"><div className="local-label"><span />이 Mac에 보관</div><p>대화의 맥락까지,<br />차분히 기록하는 공간.</p></div></aside>
    <main className="main"><header className="topbar"><span>내 워크스페이스 <span className="slash">/</span> 모든 기록</span><span className="local-badge">MAC · LOCAL</span></header><div className="page"><div className="page-heading"><div><span className="eyebrow">CONVERSATION ARCHIVE</span><h1>대화의 다음 페이지</h1><p>흘러간 대화를 다시 찾을 수 있는 기록으로.</p></div><button className="button secondary" onClick={() => setUpload(true)}><Upload size={16} /> 파일 가져오기</button></div>
      <Recorder onSaved={saved} />{error && <p className="error" role="alert">{error}</p>}
      {selected && <div className="notice">기록을 저장했습니다. 전사·대화 정리는 로컬 작업자에서 이어집니다. <button onClick={() => setSelected(null)}>목록 보기</button></div>}
      <RecordingList records={records} loading={loading} onSelect={setSelected} onUpload={() => setUpload(true)} />
      <footer className="page-footer"><span>원본 음성에서 시작하는 대화 기록</span><span><Settings size={13} /> 로컬 전용 모드</span></footer>
    </div></main>{upload && <UploadDialog onClose={() => setUpload(false)} onSaved={saved} />}
  </div>
}
