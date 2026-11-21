import { Component, useEffect, useRef, useState, type ReactNode } from 'react'
import { Editor } from 'ketcher-react'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import 'ketcher-react/dist/index.css'
import { useStore } from '../store'
import { api } from '../api/client'
import { useT } from '../i18n'
import type { Molecule } from '../types'

class KetcherBoundary extends Component<{ children: ReactNode }, { err: string }> {
  state = { err: '' }
  static getDerivedStateFromError(e: any) { return { err: String(e) } }
  render() {
    if (this.state.err) {
      return (
        <div className="placeholder" style={{ height: 520 }}>
          <div className="big">⚠️</div>
          <div>Ketcher load error / 绘制器加载失败</div>
          <div className="muted" style={{ maxWidth: 480 }}>{this.state.err}</div>
          <button className="ghost sm" onClick={() => this.setState({ err: '' })}>Retry / 重试</button>
        </div>
      )
    }
    return this.props.children
  }
}

export function DrawMoleculeDialog() {
  const open = useStore((s) => s.drawOpen)
  const close = () => useStore.getState().setDrawOpen(false)
  const setCurrent = useStore((s) => s.setCurrentMolecule)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const setActiveView = useStore((s) => s.setActiveView)
  const { tr } = useT()
  const ketcherRef = useRef<any>(null)
  const [provider, setProvider] = useState<any>(null)
  const [initErr, setInitErr] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [asMol, setAsMol] = useState(false)

  useEffect(() => {
    if (open && !provider && !initErr) {
      try {
        setProvider(new StandaloneStructServiceProvider())
      } catch (e) {
        setInitErr(e instanceof Error ? e.message : String(e))
      }
    }
  }, [open, provider, initErr])

  if (!open) return null

  const doImport = async () => {
    const k = ketcherRef.current
    if (!k) { setErr(tr('绘制器尚未初始化', 'Drawer not initialized yet')); return }
    setBusy(true); setErr('')
    try {
      let content: string
      let source: 'smiles' | 'mol'
      if (asMol) { content = await k.getMolfile(); source = 'mol' }
      else { content = await k.getSmiles(); source = 'smiles' }
      content = (content || '').trim()
      if (!content || content === 'C' || content === 'M  END') { setErr(tr('请先在画板上绘制一个分子结构', 'Please draw a molecule on the canvas first')); return }
      const mol = await api.post<Molecule>('/molecules/import', { source, content, name: 'drawn' })
      setCurrent(mol)
      await refreshMolecules()
      close()
      setActiveView('modeling')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="overlay" onClick={close}>
      <div className="modal draw-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 1000 }}>
        <div className="modal-head">
          {tr('绘制分子 (Ketcher)', 'Draw Molecule (Ketcher)')}
          <div className="spacer" />
          <button className="ghost" onClick={close}>✕</button>
        </div>
        <div className="modal-body">
          <div className="ketcher-wrap" style={{ height: 520 }}>
            {initErr ? (
              <div className="placeholder"><div className="big">⚠️</div><div>{tr('绘制器后端初始化失败', 'Failed to initialize drawer backend')}</div><div className="muted">{initErr}</div></div>
            ) : provider ? (
              <KetcherBoundary>
                <Editor
                  staticResourcesUrl="/ketcher/"
                  structServiceProvider={provider}
                  errorHandler={(e: any) => console.error('[ketcher]', e)}
                  onInit={(ketcher: any) => { ketcherRef.current = ketcher }}
                />
              </KetcherBoundary>
            ) : (
              <div className="placeholder"><div className="muted">{tr('加载绘制器…', 'Loading drawer…')}</div></div>
            )}
          </div>
          <div className="row">
            <button className="primary" onClick={doImport} disabled={busy || !provider}>
              {busy ? tr('导入中…', 'Importing…') : tr('导入并建模', 'Import & Build 3D')}
            </button>
            <label className="row" style={{ gap: 4 }}>
              <input type="checkbox" checked={asMol} onChange={(e) => setAsMol(e.target.checked)} />
              <span className="muted">{tr('用 MOL 格式(复杂结构/立体更准)', 'Use MOL format (better for stereochemistry)')}</span>
            </label>
            <span className="muted">{tr('默认导出 SMILES;画好后点「导入并建模」', 'Exports SMILES by default; click Import & Build 3D when done')}</span>
          </div>
          {err && <div className="err-text">{err}</div>}
        </div>
      </div>
    </div>
  )
}
