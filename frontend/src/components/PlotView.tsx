import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { RECIPE_LABELS_EN, useT } from '../i18n'
import type { Recipe, VisualizeResult } from '../types'

export function PlotView() {
  const jobs = useStore((s) => s.jobs)
  const refreshJobs = useStore((s) => s.refreshJobs)
  const { lang, tr } = useT()
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
    if (!jobId) { setErr(tr('请选择一个已成功且有 .fchk 的任务', 'Select a succeeded job with a .fchk file')); return }
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
      <div className="card-head">
        <span>{tr('结果作图 (Multiwfn + VMD)', 'Result Plotting (Multiwfn + VMD)')}</span>
        <span className="sub">{tr('沙箱限目录', 'Directory-sandboxed')}</span>
      </div>
      <div className="card-body">
        <div className="form-grid">
          <label className="field">
            <span className="lbl">{tr('作图类型', 'Plot Recipe')}</span>
            <select value={recipeKey} onChange={(e) => { setRecipeKey(e.target.value); applyRecipe(e.target.value, recipes) }}>
              {Object.entries(recipes).map(([k, r]) => (
                <option key={k} value={k}>{lang === 'en' ? (RECIPE_LABELS_EN[k] || r.label) : r.label}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="lbl">{tr('任务(需有 .fchk)', 'Job (requires .fchk)')}</span>
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">{tr('- 选择任务 -', '- Select job -')}</option>
              {eligible.map((j) => <option key={j.id} value={j.id}>{j.molecule_name} · {j.spec_label} ({j.id.slice(0, 12)})</option>)}
            </select>
          </label>
        </div>
        {eligible.length === 0 && <div className="muted">{tr('暂无带 .fchk 的成功任务。先成功运行一个 Gaussian 任务。', 'No succeeded jobs with .fchk yet. Run a Gaussian calculation first.')}</div>}
        {recipeKey && recipes[recipeKey] && <div className="muted" style={{ marginTop: 6 }}>{recipes[recipeKey].multiwfn_note}</div>}

        <label className="field">
          <span className="lbl">{tr('Multiwfn 输入序列(每行一个;.fch 由程序自动前置)', 'Multiwfn input sequence (one per line; .fch prepended automatically)')}</span>
          <textarea className="gjf-text" value={mwInput} onChange={(e) => setMwInput(e.target.value)} rows={4} />
        </label>
        <label className="field">
          <span className="lbl">{tr('VMD 脚本(可编辑)', 'VMD script (editable)')}</span>
          <textarea className="gjf-text" value={vmdScript} onChange={(e) => setVmdScript(e.target.value)} rows={6} />
        </label>

        <div className="row">
          <button className="primary" onClick={run} disabled={busy}>{busy ? tr('运行中…', 'Running…') : tr('运行作图', 'Run Plot')}</button>
          <span className="muted">{tr('仅在配置的 Multiwfn / VMD 目录内写文件', 'Writes strictly within configured Multiwfn / VMD directories')}</span>
        </div>
        {err && <div className="err-text">{err}</div>}

        {result && (
          <div className="plot-result">
            {result.image_url ? (
              <img src={result.image_url} alt={result.recipe} style={{ maxWidth: '100%', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }} />
            ) : (
              <div className="muted">{tr('未生成图像(可能缺少 cube 或渲染失败,见日志)。', 'No image generated (missing cube or VMD render failed; check logs).')}</div>
            )}
            <pre className="muted" style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{result.instructions}</pre>
            <details><summary className="muted">{tr('Multiwfn 日志', 'Multiwfn Log')}</summary><pre className="job-log">{result.multiwfn_log || tr('(空)', '(empty)')}</pre></details>
            <details><summary className="muted">{tr('VMD 日志', 'VMD Log')}</summary><pre className="job-log">{result.vmd_log || tr('(空)', '(empty)')}</pre></details>
            <div className="muted">
              {tr('生成 cube:', 'Cubes:')} {result.cubes.length ? result.cubes.join(', ') : tr('(无)', '(none)')} · {tr('输出目录:', 'Output dir:')} {result.vmd_out_dir}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
