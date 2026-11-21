import { useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { useT } from '../i18n'
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
  const { tr } = useT()
  const [tab, setTab] = useState<'draw' | 'smiles' | 'cas' | 'name' | 'file'>('draw')
  const [smiles, setSmiles] = useState('')
  const [name, setName] = useState('')
  const [cas, setCas] = useState('')
  const [visionModel, setVisionModel] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [dragOver, setDragOver] = useState(false)

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
  const byCas = async () => {
    if (!cas.trim()) return
    setBusy(true); setErr('')
    try { await finish(await api.post<Molecule>('/molecules/import-by-cas', { cas: cas.trim() })); setCas('') }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const byFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    const source = EXT_MAP[ext]
    if (!source) { setErr(tr(`不支持的文件类型:.${ext}`, `Unsupported file type: .${ext}`)); return }
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

  const TABS: { k: typeof tab; zh: string; en: string }[] = [
    { k: 'draw', zh: '绘制分子', en: 'Draw' },
    { k: 'smiles', zh: 'SMILES', en: 'SMILES' },
    { k: 'cas', zh: 'CAS 号', en: 'CAS' },
    { k: 'name', zh: '按名称', en: 'By Name' },
    { k: 'file', zh: '文件', en: 'File' },
  ]

  return (
    <div className="card">
      <div className="card-head"><span>{tr('导入分子', 'Import Molecule')}</span></div>
      <div className="tabs">
        {TABS.map((t) => <button key={t.k} className={tab === t.k ? 'active' : ''} onClick={() => setTab(t.k)}>{tr(t.zh, t.en)}</button>)}
      </div>
      <div className="card-body">
        {tab === 'draw' && (
          <div className="placeholder" style={{ height: 120 }}>
            <div className="big">✏️</div>
            <button className="primary" onClick={() => setDrawOpen(true)}>{tr('打开 2D 分子绘制器', 'Open 2D Molecule Drawer')}</button>
            <div className="muted">{tr('在画板上画结构,导出 SMILES 后自动建模', 'Draw structure on canvas, auto-build 3D via SMILES')}</div>
          </div>
        )}
        {tab === 'smiles' && (
          <div className="row">
            <input value={smiles} onChange={(e) => setSmiles(e.target.value)} placeholder={tr('如 CCO、c1ccccc1', 'e.g. CCO, c1ccccc1')} onKeyDown={(e) => e.key === 'Enter' && bySmiles()} style={{ flex: 1 }} />
            <button className="primary" onClick={bySmiles} disabled={busy}>{tr('导入', 'Import')}</button>
          </div>
        )}
        {tab === 'cas' && (
          <>
            <div className="row">
              <input value={cas} onChange={(e) => setCas(e.target.value)} placeholder={tr('如 64-17-5(乙醇)、7732-18-5(水)、50-78-2(阿司匹林)', 'e.g. 64-17-5 (ethanol), 7732-18-5 (water), 50-78-2 (aspirin)')} onKeyDown={(e) => e.key === 'Enter' && byCas()} style={{ flex: 1 }} />
              <button className="primary" onClick={byCas} disabled={busy}>{tr('导入', 'Import')}</button>
            </div>
            <div className="muted" style={{ marginTop: 6 }}>{tr('输入 CAS 登录号,自动校验格式+校验位,经 PubChem 检索 SMILES 建模。', 'Validates CAS format & check digit, then resolves SMILES via PubChem.')}</div>
          </>
        )}
        {tab === 'name' && (
          <>
            <div className="row">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder={tr('中英文名称,如 乙醇 / caffeine / 富勒烯', 'CN/EN name, e.g. ethanol / caffeine / fullerene')} onKeyDown={(e) => e.key === 'Enter' && byName()} style={{ flex: 1 }} />
              <button className="primary" onClick={byName} disabled={busy}>{tr('检索', 'Lookup')}</button>
            </div>
            <div className="muted" style={{ marginTop: 6 }}>{tr('PubChem/CIR 检索;也可在对话中直接说「计算乙醇」。', 'Resolves via PubChem/CIR; or simply ask in Chat.')}</div>
          </>
        )}
        {tab === 'file' && (
          <>
            <label
              className={`dropzone ${dragOver ? 'dragover' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const f = e.dataTransfer.files?.[0]
                if (f) byFile(f)
              }}
            >
              <input type="file" accept=".mol,.sdf,.mol2,.gjf,.out,.log,.cdxml,.cdx,.png,.jpg,.jpeg" style={{ display: 'none' }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) byFile(f); e.target.value = '' }} />
              <div className="muted">{tr('点击或拖入:.mol/.sdf/.mol2/.gjf/.out/.log/.cdxml/.png', 'Click or drop: .mol / .sdf / .mol2 / .gjf / .out / .log / .cdxml / .png')}</div>
            </label>
            <label className="field" style={{ marginTop: 8 }}>
              <span className="lbl">{tr('图片识别用模型(仅图片)', 'Vision model (images only)')}</span>
              <select value={visionModel} onChange={(e) => setVisionModel(e.target.value)}>
                {(settings?.providers ?? []).length === 0 && <option value="">{tr('(未配置)', '(Not configured)')}</option>}
                {(settings?.providers ?? []).flatMap((p) => (p.models.length ? p.models : [p.default_model || '(default)']).map((m) => (
                  <option key={p.id + m} value={`${p.id}|${m === '(default)' ? '' : m}`}>{p.name} / {m === '(default)' ? tr('(默认)', '(default)') : m}</option>
                )))}
              </select>
            </label>
          </>
        )}
        {err && <div className="err-text" style={{ marginTop: 8 }}>{err}</div>}
        {busy && <div className="muted" style={{ marginTop: 6 }}>{tr('处理中…', 'Processing…')}</div>}
      </div>
    </div>
  )
}
