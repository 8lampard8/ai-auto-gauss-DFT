import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { TASK_LABELS_EN, useT } from '../i18n'
import type { MethodSpec } from '../types'

const DEFAULT_SPEC: MethodSpec = {
  functional: 'B3LYP', basis: 'def2-TZVP', route: 'opt freq', dispersion: 'em=gd3bj',
  scrf: '', extra: '', charge: 0, multiplicity: 1, memory: '8GB', nproc: 4,
  title: '', label: '', explanation: '',
}

function download(name: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url)
}

export function GjfEditor() {
  const molecule = useStore((s) => s.currentMolecule)
  const gjf = useStore((s) => s.currentGjf)
  const setGjf = useStore((s) => s.setCurrentGjf)
  const catalog = useStore((s) => s.catalog)
  const sys = useStore((s) => s.systemInfo)
  const setPendingSpec = useStore((s) => s.setPendingSpec)
  const setJobSubmitOpen = useStore((s) => s.setJobSubmitOpen)
  const { lang, tr } = useT()
  const [spec, setSpec] = useState<MethodSpec>(DEFAULT_SPEC)
  const [task, setTask] = useState('optfreq')
  const [solvent, setSolvent] = useState('')
  const [accuracy, setAccuracy] = useState<'fast' | 'standard' | 'high'>('standard')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [basisCheck, setBasisCheck] = useState<{ ok: boolean | null; msg: string }>({ ok: null, msg: '' })

  useEffect(() => {
    if (!molecule) return
    setSpec((s) => ({
      ...s,
      charge: molecule.charge,
      multiplicity: molecule.multiplicity,
      title: molecule.name || s.title,
    }))
  }, [molecule?.id])

  useEffect(() => {
    const b = spec.basis.trim()
    if (!b) { setBasisCheck({ ok: null, msg: '' }); return }
    const t = setTimeout(async () => {
      try {
        const r = await api.get<{ valid: boolean; message: string }>(
          `/gjf/basis-sets/validate?basis=${encodeURIComponent(b)}`,
        )
        setBasisCheck({ ok: r.valid, msg: r.message })
      } catch {
        setBasisCheck({ ok: null, msg: '' })
      }
    }, 400)
    return () => clearTimeout(t)
  }, [spec.basis])

  const recommend = async () => {
    if (!molecule) return
    setBusy(true); setErr('')
    try {
      const r = await api.post<MethodSpec>('/gjf/recommend', { molecule_id: molecule.id, task, solvent, accuracy, charge: spec.charge, multiplicity: spec.multiplicity })
      setSpec(r)
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const generate = async () => {
    if (!molecule) return
    setBusy(true); setErr('')
    try { const r = await api.post<{ gjf: string }>('/gjf/generate', { molecule_id: molecule.id, spec }); setGjf(r.gjf) }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }

  return (
    <div className="card" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <div className="card-head">
        <span>{tr('gjf 输入生成', 'gjf Input Generator')}</span>
        <div className="spacer" />
        <span className="sub">{molecule ? molecule.name : tr('未选分子', 'No molecule')}</span>
      </div>
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
        <div className="gjf-form">
          <label className="field"><span className="lbl">{tr('计算类型', 'Task Type')}</span>
            <select value={task} onChange={(e) => setTask(e.target.value)}>
              {(catalog?.tasks || []).map((t) => (
                <option key={t.id} value={t.id}>{lang === 'en' ? (TASK_LABELS_EN[t.id] || t.label) : t.label}</option>
              ))}
            </select>
          </label>
          <label className="field"><span className="lbl">{tr('溶剂', 'Solvent')}</span>
            <select value={solvent} onChange={(e) => setSolvent(e.target.value)}>
              <option value="">{tr('气相', 'Gas phase')}</option>
              {(catalog?.solvents || []).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="field"><span className="lbl">{tr('精度', 'Accuracy')}</span>
            <select value={accuracy} onChange={(e) => setAccuracy(e.target.value as 'fast' | 'standard' | 'high')}>
              <option value="fast">{tr('快速预优化', 'Fast')}</option>
              <option value="standard">{tr('标准', 'Standard')}</option>
              <option value="high">{tr('高精度', 'High')}</option>
            </select>
          </label>
          <label className="field"><span className="lbl">{tr('电荷 / 多重度', 'Charge / Mult')}</span>
            <div className="row"><input type="number" value={spec.charge} onChange={(e) => setSpec({ ...spec, charge: parseInt(e.target.value) || 0 })} style={{ flex: 1 }} /><input type="number" value={spec.multiplicity} onChange={(e) => setSpec({ ...spec, multiplicity: parseInt(e.target.value) || 1 })} style={{ flex: 1 }} /></div>
          </label>
          <label className="field"><span className="lbl">{tr('泛函', 'Functional')}</span><input list="func-list" value={spec.functional} onChange={(e) => setSpec({ ...spec, functional: e.target.value })} /><datalist id="func-list">{(catalog?.functionals || []).map((f) => <option key={f} value={f} />)}</datalist></label>
          <label className="field"><span className="lbl">{tr('基组', 'Basis Set')} {basisCheck.ok === true && <span className="ok-text">✓</span>}{basisCheck.ok === false && <span className="err-text">⚠</span>}</span><input list="basis-list" value={spec.basis} onChange={(e) => setSpec({ ...spec, basis: e.target.value })} /><datalist id="basis-list">{(catalog?.bases || []).map((b) => <option key={b} value={b} />)}</datalist>{basisCheck.ok === false && <div className="err-text" style={{ fontSize: 11 }}>{basisCheck.msg}</div>}</label>
          <label className="field"><span className="lbl">%mem / %nproc</span><div className="row"><input value={spec.memory} onChange={(e) => setSpec({ ...spec, memory: e.target.value })} style={{ flex: 1 }} /><input type="number" value={spec.nproc} onChange={(e) => setSpec({ ...spec, nproc: parseInt(e.target.value) || 1 })} style={{ width: 70 }} /></div></label>
        </div>
        {spec.label && <div className="muted">{spec.label} · {spec.explanation}</div>}
        <div className="row">
          <button onClick={recommend} disabled={busy || !molecule}>{tr('推荐方法', 'Recommend')}</button>
          <button className="primary" onClick={generate} disabled={busy || !molecule}>{tr('生成 gjf', 'Generate gjf')}</button>
          <button onClick={() => { setPendingSpec(spec); setJobSubmitOpen(true) }} disabled={!molecule || !gjf}>{tr('提交任务', 'Submit Job')}</button>
          {gjf && <button onClick={() => download('job.gjf', gjf)}>{tr('下载 .gjf', 'Download .gjf')}</button>}
          {sys && <span className="muted">{tr(`本机建议 nproc=${Math.max(1, sys.cpu_count - 2)}`, `Suggested nproc=${Math.max(1, sys.cpu_count - 2)}`)}</span>}
        </div>
        {err && <div className="err-text">{err}</div>}
        <textarea className="gjf-text" value={gjf} placeholder={tr('生成的 .gjf 内容显示在此,可手动编辑…', 'Generated .gjf input appears here (editable)…')} onChange={(e) => setGjf(e.target.value)} spellCheck={false} style={{ flex: 1, minHeight: 120 }} />
      </div>
    </div>
  )
}
