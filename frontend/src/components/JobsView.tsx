import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { useT } from '../i18n'

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
  const openDescriptors = useStore((s) => s.openDescriptors)
  const { tr } = useT()
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
    setLogText(r.log || tr('(无日志)', '(No log)')); setLogFor(id)
  }
  const dl = async (id: string, what: 'gjf' | 'log') => {
    const r = await api.get<Record<string, string>>(`/jobs/${id}/${what}`)
    downloadText(`${id}.${what}`, r[what] || '')
  }
  const cancel = async (id: string) => { await api.post(`/jobs/${id}/cancel`); refresh() }
  const remove = async (id: string) => {
    if (confirm(tr('删除任务记录?', 'Delete this job record?'))) {
      await api.del(`/jobs/${id}`)
      refresh()
    }
  }

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-head">
        <span>{tr('计算任务', 'Compute Jobs')}</span>
        <span className="sub">{jobs.length} {tr('个', 'total')}</span>
        <div className="spacer" />
        <button className="ghost sm" onClick={refresh}>{tr('刷新', 'Refresh')}</button>
        <button className="primary" onClick={() => setJobSubmitOpen(true)}>{tr('提交任务', 'Submit Job')}</button>
      </div>
      <div className="card-body">
        {jobs.length === 0 ? (
          <div className="placeholder">
            <div className="big">🧮</div>
            <div>{tr('暂无任务', 'No jobs yet')}</div>
            <div className="muted">{tr('在「建模」中生成 gjf 后点「提交任务」', 'Generate a .gjf in Modeling and click Submit Job')}</div>
          </div>
        ) : (
          <div className="job-list">
            {jobs.map((j) => (
              <div key={j.id} className="job-item">
                <div className="job-row">
                  <span className={`badge ${j.status}`}>{j.status}</span>
                  <b>{j.spec_label}</b>
                  <span className="muted">{j.kind}{j.remote_host ? ` @ ${j.remote_host}` : ''} · {j.nproc}{tr('核', 'c')} {j.mem}</span>
                  <span className="muted" style={{ marginLeft: 'auto' }}>{j.molecule_name}</span>
                </div>
                {(j.message || j.error) && (
                  <div className={j.error ? 'err-text' : 'muted'} style={{ marginTop: 4 }}>{j.error || j.message}</div>
                )}
                {j.summary && Object.keys(j.summary).length > 0 && (
                  <div className="summary-chips">
                    {j.summary.energy !== undefined && <span className="chip-kv">E = {j.summary.energy.toFixed(5)} Ha</span>}
                    {j.summary.gap_ev !== undefined && <span className="chip-kv">Gap = {j.summary.gap_ev.toFixed(3)} eV</span>}
                    {j.summary.dipole_debye !== undefined && <span className="chip-kv">μ = {j.summary.dipole_debye.toFixed(2)} D</span>}
                    {j.summary.gibbs !== undefined && <span className="chip-kv">G = {j.summary.gibbs.toFixed(5)} Ha</span>}
                    {j.summary.n_imag !== undefined && (
                      <span className={`chip-kv ${j.summary.n_imag > 0 ? 'warn' : ''}`}>
                        {tr('虚频', 'Nimag')} = {j.summary.n_imag}
                      </span>
                    )}
                  </div>
                )}
                <div className="row" style={{ marginTop: 6, flexWrap: 'wrap' }}>
                  <button className="ghost sm" onClick={() => showLog(j.id)}>{logFor === j.id ? tr('隐藏日志', 'Hide Log') : tr('日志', 'Log')}</button>
                  {j.log_path && (
                    <button
                      className="ghost sm"
                      onClick={() => openDescriptors({ kind: 'job', id: j.id })}
                    >
                      🧬 {tr('描述符', 'Descriptors')}
                    </button>
                  )}
                  <button className="ghost sm" onClick={() => dl(j.id, 'gjf')}>{tr('下载 gjf', 'Download gjf')}</button>
                  <button className="ghost sm" onClick={() => dl(j.id, 'log')}>{tr('下载日志', 'Download log')}</button>
                  {(j.status === 'running' || j.status === 'queued') && <button className="ghost sm" onClick={() => cancel(j.id)}>{tr('取消', 'Cancel')}</button>}
                  <button className="ghost sm" onClick={() => remove(j.id)}>{tr('删除', 'Delete')}</button>
                </div>
                {logFor === j.id && <pre className="job-log">{logText || tr('(空)', '(empty)')}</pre>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
