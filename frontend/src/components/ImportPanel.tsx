import { useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import type { ImportSource, Molecule } from '../types'

const EXT_MAP: Record<string, ImportSource> = {
  mol: 'mol', sdf: 'mol', mol2: 'mol2', gjf: 'gjf', out: 'out', log: 'out',
  cdxml: 'cdxml', cdx: 'cdxml', png: 'image', jpg: 'image', jpeg: 'image',
}
const readText = (f: File) => new Promise<string>((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.onerror = () => rej(r.error); r.readAsText(f) })
const readURL = (f: File) => new Promise<string>((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.onerror = () => rej(r.error); r.readAsDataURL(f) })

export function ImportPanel() {
  const setCurrent = useStore((s) => s.setCurrentMolecule)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const setDrawOpen = useStore((s) => s.setDrawOpen)
  const settings = useStore((s) => s.settings)
  const [tab, setTab] = useState<'draw' | 'smiles' | 'name' | 'file'>('draw')
  const [smiles, setSmiles] = useState('')
  const [name, setName] = useState('')
  const [visionModel, setVisionModel] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const finish = async (mol: Molecule) => { setCurrent(mol); await refreshMolecules(); setErr('') }
  const bySmiles = async () => {
    if (!smiles.trim()) return
    setBusy(true); setErr('')
    try { await finish(await api.post<Molecule>('/molecules/import', { source: 'smiles', content: smiles.trim() })); setSmiles('') }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const byName = async () => {
    if (!name.trim()) return
    setBusy(true); setErr('')
    try { await finish(await api.post<Molecule>('/molecules/import-by-name', { name: name.trim() })); setName('') }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const byFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    const source = EXT_MAP[ext]
    if (!source) { setErr(`不支持的文件类型:.${ext}`); return }
    setBusy(true); setErr('')
    try {
      if (source === 'image') {
        const url = await readURL(file)
        const [vpid, vmdl] = visionModel.split('|')
        await finish(await api.post<Molecule>('/molecules/import', { source, content: url.split(',')[1] || '', filename: file.name, mime: file.type || 'image/png', provider_id: vpid || '', model: vmdl || '' }))
      } else {
        await finish(await api.post<Molecule>('/molecules/import', { source, content: await readText(file), filename: file.name }))
      }
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }

  const TABS: { k: typeof tab; label: string }[] = [
    { k: 'draw', label: '绘制分子' }, { k: 'smiles', label: 'SMILES' }, { k: 'name', label: '按名称' }, { k: 'file', label: '文件' },
  ]

  return (
    <div className="card">
      <div className="card-head"><span>导入分子</span></div>
      <div className="tabs">
        {TABS.map((t) => <button key={t.k} className={tab === t.k ? 'active' : ''} onClick={() => setTab(t.k)}>{t.label}</button>)}
      </div>
      <div className="card-body">
        {tab === 'draw' && (
          <div className="placeholder" style={{ height: 120 }}>
            <div className="big">✏️</div>
            <button className="primary" onClick={() => setDrawOpen(true)}>打开 2D 分子绘制器</button>
            <div className="muted">在画板上画结构,导出 SMILES 后自动建模</div>
          </div>
        )}
        {tab === 'smiles' && (
          <div className="row">
            <input value={smiles} onChange={(e) => setSmiles(e.target.value)} placeholder="如 CCO、c1ccccc1" onKeyDown={(e) => e.key === 'Enter' && bySmiles()} style={{ flex: 1 }} />
            <button className="primary" onClick={bySmiles} disabled={busy}>导入</button>
          </div>
        )}
        {tab === 'name' && (
          <>
            <div className="row">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="中英文名称,如 乙醇 / caffeine / 富勒烯" onKeyDown={(e) => e.key === 'Enter' && byName()} style={{ flex: 1 }} />
              <button className="primary" onClick={byName} disabled={busy}>检索</button>
            </div>
            <div className="muted" style={{ marginTop: 6 }}>PubChem/CIR 检索;也可在对话中直接说「计算乙醇」。</div>
          </>
        )}
        {tab === 'file' && (
          <>
            <label className="dropzone">
              <input type="file" accept=".mol,.sdf,.mol2,.gjf,.out,.log,.cdxml,.cdx,.png,.jpg,.jpeg" style={{ display: 'none' }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) byFile(f); e.target.value = '' }} />
              <div className="muted">点击或拖入:.mol/.sdf/.mol2/.gjf/.out/.log/.cdxml/.png</div>
            </label>
            <label className="field" style={{ marginTop: 8 }}>
              <span className="lbl">图片识别用模型(仅图片)</span>
              <select value={visionModel} onChange={(e) => setVisionModel(e.target.value)}>
                {(settings?.providers ?? []).length === 0 && <option value="">(未配置)</option>}
                {(settings?.providers ?? []).flatMap((p) => (p.models.length ? p.models : [p.default_model || '(默认)']).map((m) => (
                  <option key={p.id + m} value={`${p.id}|${m === '(默认)' ? '' : m}`}>{p.name} / {m}</option>
                )))}
              </select>
            </label>
          </>
        )}
        {err && <div className="err-text" style={{ marginTop: 8 }}>{err}</div>}
        {busy && <div className="muted" style={{ marginTop: 6 }}>处理中…</div>}
      </div>
    </div>
  )
}
