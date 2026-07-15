import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'

function downloadText(name: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export function JobsView() {
  const jobs = useStore((s) => s.jobs)
  const refresh = useStore((s) => s.refreshJobs)
  const setJobSubmitOpen = useStore((s) => s.setJobSubmitOpen)
  const [logFor, setLogFor] = useState<string | null>(null)
  const [logText, setLogText] = useState('')

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const active = jobs.some((j) => j.status === 'running' || j.status === 'queued')
    if (!active) return
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [jobs, refresh])

  const showLog = async (id: string) => {
    if (logFor === id) { setLogFor(null); return }
    const r = await api.get<{ log: string }>(`/jobs/${id}/log`)
    setLogText(r.log || '(无日志)'); setLogFor(id)
  }
  const dl = async (id: string, what: 'gjf' | 'log') => {
    const r = await api.get<Record<string, string>>(`/jobs/${id}/${what}`)
    downloadText(`${id}.${what}`, r[what] || '')
  }
  const cancel = async (id: string) => { await api.post(`/jobs/${id}/cancel`); refresh() }
  const remove = async (id: string) => { if (confirm('删除任务记录?')) { await api.del(`/jobs/${id}`); refresh() } }

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-head">
        <span>计算任务</span>
        <span className="sub">{jobs.length} 个</span>
        <div className="spacer" />
        <button className="ghost sm" onClick={refresh}>刷新</button>
        <button className="primary" onClick={() => setJobSubmitOpen(true)}>提交任务</button>
      </div>
      <div className="card-body">
        {jobs.length === 0 ? (
          <div className="placeholder">
            <div className="big">🧮</div>
            <div>暂无任务</div>
            <div className="muted">在「建模」中生成 gjf 后点「提交任务」</div>
          </div>
        ) : (
          <div className="job-list">
            {jobs.map((j) => (
              <div key={j.id} className="job-item">
                <div className="job-row">
                  <span className={`badge ${j.status}`}>{j.status}</span>
                  <b>{j.spec_label}</b>
                  <span className="muted">{j.kind}{j.remote_host ? ` @ ${j.remote_host}` : ''} · {j.nproc}核 {j.mem}</span>
                  <span className="muted" style={{ marginLeft: 'auto' }}>{j.molecule_name}</span>
                </div>
                {(j.message || j.error) && (
                  <div className={j.error ? 'err-text' : 'muted'} style={{ marginTop: 4 }}>{j.error || j.message}</div>
                )}
                <div className="row" style={{ marginTop: 6, flexWrap: 'wrap' }}>
                  <button className="ghost sm" onClick={() => showLog(j.id)}>{logFor === j.id ? '隐藏日志' : '日志'}</button>
                  <button className="ghost sm" onClick={() => dl(j.id, 'gjf')}>下载 gjf</button>
                  <button className="ghost sm" onClick={() => dl(j.id, 'log')}>下载日志</button>
                  {(j.status === 'running' || j.status === 'queued') && <button className="ghost sm" onClick={() => cancel(j.id)}>取消</button>}
                  <button className="ghost sm" onClick={() => remove(j.id)}>删除</button>
                </div>
                {logFor === j.id && <pre className="job-log">{logText || '(空)'}</pre>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
