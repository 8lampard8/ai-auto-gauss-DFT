import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { useT } from '../i18n'
import type { Molecule } from '../types'
import { KetcherEditor } from './KetcherEditor'
import { MoleculeViewer } from './MoleculeViewer'

const GROUPS: { label: string; smi: string }[] = [
  { label: '-OH', smi: 'O' }, { label: '-NH₂', smi: 'N' }, { label: '-COOH', smi: 'OC=O' },
  { label: '-CHO', smi: 'C=O' }, { label: '-CN', smi: 'C#N' }, { label: '-NO₂', smi: 'N(=O)=O' },
  { label: '-OMe', smi: 'OC' }, { label: '-Ac', smi: 'CC(=O)' }, { label: '-Ph', smi: 'c1ccccc1' },
  { label: '-SH', smi: 'S' }, { label: '-SO₃H', smi: 'S(=O)(=O)O' }, { label: '-N₂⁺', smi: '[N+]#N' },
  { label: '-F', smi: 'F' }, { label: '-Cl', smi: 'Cl' }, { label: '-Br', smi: 'Br' }, { label: '-I', smi: 'I' },
]

export function MoleculeEditorView() {
  const molecule = useStore((s) => s.currentMolecule)
  const setCurrentMolecule = useStore((s) => s.setCurrentMolecule)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const { tr } = useT()

  const ketcherRef = useRef<any>(null)
  const loadedIdRef = useRef<string | null>(null)
  const loadingRef = useRef(false)
  const autoSyncRef = useRef(true)
  const syncTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [autoSync, setAutoSync] = useState(true)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')

  const loadIntoKetcher = async (mol: Molecule) => {
    const k = ketcherRef.current
    if (!k) return
    loadingRef.current = true
    try {
      await k.setMolecule(mol.smiles || '')
      loadedIdRef.current = mol.id
    } catch (e) {
      setErr(`${tr('载入失败:', 'Load failed: ')}${e}`)
    } finally {
      loadingRef.current = false
    }
  }

  useEffect(() => {
    if (!molecule) return
    if (loadedIdRef.current === molecule.id) return
    loadIntoKetcher(molecule)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [molecule])

  const syncTo3D = async () => {
    const k = ketcherRef.current
    if (!k || !molecule) return
    setErr(''); setMsg(tr('同步中…', 'Syncing…'))
    try {
      const smi = (await k.getSmiles() || '').trim()
      if (!smi || smi === 'C') { setMsg(tr('画板为空', 'Canvas is empty')); return }
      const updated = await api.put<Molecule>(`/molecules/${molecule.id}`, { smiles: smi })
      loadedIdRef.current = updated.id
      setCurrentMolecule(updated)
      await refreshMolecules()
      setMsg(tr('已同步到 3D', 'Synced to 3D'))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const scheduleSync = () => {
    if (syncTimer.current) clearTimeout(syncTimer.current)
    syncTimer.current = setTimeout(() => { syncTo3D() }, 1200)
  }

  const onInit = (k: any) => {
    ketcherRef.current = k
    k.changeEvent?.subscribe?.(() => {
      if (loadingRef.current || !autoSyncRef.current) return
      scheduleSync()
    })
    if (molecule) loadIntoKetcher(molecule)
  }

  const addGroup = async (smi: string) => {
    const k = ketcherRef.current
    if (!k) return
    try {
      await k.addFragment(smi)
      setMsg(tr(`已插入片段 ${smi},用键连接到主分子`, `Inserted fragment ${smi}; connect it with a bond`))
    } catch (e) { setErr(String(e)) }
  }
  const clearCanvas = async () => {
    const k = ketcherRef.current
    if (!k) return
    loadingRef.current = true
    try { await k.setMolecule(''); loadedIdRef.current = null } catch { /* ignore */ }
    finally { loadingRef.current = false }
  }

  return (
    <div className="grid-2">
      <div className="card" style={{ minHeight: 0 }}>
        <div className="card-head">
          <span>{tr('2D 编辑器 (Ketcher)', '2D Editor (Ketcher)')}</span>
          <div className="spacer" />
          <label className="row" style={{ gap: 4, fontWeight: 400 }}>
            <input type="checkbox" checked={autoSync} onChange={(e) => { setAutoSync(e.target.checked); autoSyncRef.current = e.target.checked }} />
            <span className="muted">{tr('实时同步到 3D', 'Live sync to 3D')}</span>
          </label>
        </div>
        <div className="card-body flush" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="row" style={{ padding: '8px 12px', gap: 6, flexWrap: 'wrap', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
            <button className="sm" onClick={() => molecule && loadIntoKetcher(molecule)} disabled={!molecule}>{tr('载入当前分子', 'Load Active')}</button>
            <button className="primary sm" onClick={syncTo3D} disabled={!molecule}>{tr('同步到 3D', 'Sync to 3D')}</button>
            <button className="ghost sm" onClick={clearCanvas}>{tr('清空', 'Clear')}</button>
            <span className="muted" style={{ marginLeft: 'auto' }}>{tr('插入基团:', 'Insert group:')}</span>
            {GROUPS.map((g) => (
              <button key={g.label} className="ghost sm" title={g.smi} onClick={() => addGroup(g.smi)}>{g.label}</button>
            ))}
          </div>
          <div style={{ flex: 1, minHeight: 460 }}>
            <KetcherEditor onInit={onInit} />
          </div>
          {err && <div className="err-text" style={{ padding: '6px 12px' }}>{err}</div>}
          {msg && <div className="muted" style={{ padding: '6px 12px' }}>{msg}</div>}
        </div>
      </div>

      <div className="card" style={{ minHeight: 0 }}>
        <div className="card-head">
          <span>{tr('3D 视图', '3D View')}</span>
          <div className="spacer" />
          {molecule && <span className="sub">{molecule.atoms.length} {tr('原子', 'atoms')} · {molecule.smiles}</span>}
        </div>
        <div className="card-body flush">
          {molecule ? (
            <div className="viewer-host" style={{ height: '100%' }}>
              <MoleculeViewer molecule={molecule} />
            </div>
          ) : (
            <div className="placeholder"><div className="big">🧪</div><div>{tr('先在「建模」导入或「对话」描述一个分子', 'Import a molecule in Modeling or describe one in Chat first')}</div></div>
          )}
        </div>
      </div>
    </div>
  )
}
