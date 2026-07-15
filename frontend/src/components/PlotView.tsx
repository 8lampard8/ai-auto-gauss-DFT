import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import type { Recipe, VisualizeResult } from '../types'

export function PlotView() {
  const jobs = useStore((s) => s.jobs)
  const refreshJobs = useStore((s) => s.refreshJobs)
  const [recipes, setRecipes] = useState<Record<string, Recipe>>({})
  const [recipeKey, setRecipeKey] = useState('igmh')
  const [jobId, setJobId] = useState('')
  const [mwInput, setMwInput] = useState('')
  const [vmdScript, setVmdScript] = useState('')
  const [result, setResult] = useState<VisualizeResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get<{ recipes: Record<string, Recipe> }>('/visualize/recipes').then((r) => {
      setRecipes(r.recipes)
      const k = Object.keys(r.recipes)[0] || 'igmh'
      setRecipeKey(k)
      const rc = r.recipes[k]
      if (rc) { setMwInput(rc.multiwfn_input.join('\n')); setVmdScript(rc.vmd_script) }
    }).catch(() => {})
    refreshJobs()
    setResult(null); setErr('')
  }, [refreshJobs])

  const applyRecipe = (key: string, recs: Record<string, Recipe>) => {
    const r = recs[key]
    if (r) { setMwInput(r.multiwfn_input.join('\n')); setVmdScript(r.vmd_script) }
  }

  const eligible = jobs.filter((j) => j.status === 'succeeded' && j.fchk_path)

  const run = async () => {
    if (!jobId) { setErr('请选择一个已成功且有 .fchk 的任务'); return }
    setBusy(true); setErr(''); setResult(null)
    try {
      const r = await api.post<VisualizeResult>('/visualize/run', {
        job_id: jobId, recipe: recipeKey,
        multiwfn_input: mwInput.split('\n').map((s) => s.trim()).filter(Boolean),
        vmd_script: vmdScript,
      })
      setResult(r)
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-head"><span>结果作图 (Multiwfn + VMD)</span><span className="sub">沙箱限目录</span></div>
      <div className="card-body">
        <div className="form-grid">
          <label className="field">
            <span className="lbl">作图类型</span>
            <select value={recipeKey} onChange={(e) => { setRecipeKey(e.target.value); applyRecipe(e.target.value, recipes) }}>
              {Object.entries(recipes).map(([k, r]) => <option key={k} value={k}>{r.label}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="lbl">任务(需有 .fchk)</span>
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">- 选择任务 -</option>
              {eligible.map((j) => <option key={j.id} value={j.id}>{j.molecule_name} · {j.spec_label} ({j.id.slice(0, 12)})</option>)}
            </select>
          </label>
        </div>
        {eligible.length === 0 && <div className="muted">暂无带 .fchk 的成功任务。先成功运行一个 Gaussian 任务。</div>}
        {recipeKey && recipes[recipeKey] && <div className="muted" style={{ marginTop: 6 }}>{recipes[recipeKey].multiwfn_note}</div>}

        <label className="field">
          <span className="lbl">Multiwfn 输入序列(每行一个;.fch 由程序自动前置)</span>
          <textarea className="gjf-text" value={mwInput} onChange={(e) => setMwInput(e.target.value)} rows={4} />
        </label>
        <label className="field">
          <span className="lbl">VMD 脚本(可编辑)</span>
          <textarea className="gjf-text" value={vmdScript} onChange={(e) => setVmdScript(e.target.value)} rows={6} />
        </label>

        <div className="row">
          <button className="primary" onClick={run} disabled={busy}>{busy ? '运行中…' : '运行作图'}</button>
          <span className="muted">仅在配置的 Multiwfn / VMD 目录内写文件</span>
        </div>
        {err && <div className="err-text">{err}</div>}

        {result && (
          <div className="plot-result">
            {result.image_url ? (
              <img src={result.image_url} alt={result.recipe} style={{ maxWidth: '100%', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }} />
            ) : (
              <div className="muted">未生成图像(可能缺少 cube 或渲染失败,见日志)。</div>
            )}
            <pre className="muted" style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{result.instructions}</pre>
            <details><summary className="muted">Multiwfn 日志</summary><pre className="job-log">{result.multiwfn_log || '(空)'}</pre></details>
            <details><summary className="muted">VMD 日志</summary><pre className="job-log">{result.vmd_log || '(空)'}</pre></details>
            <div className="muted">生成 cube:{result.cubes.length ? result.cubes.join(', ') : '(无)'} · 输出目录:{result.vmd_out_dir}</div>
          </div>
        )}
      </div>
    </div>
  )
}
