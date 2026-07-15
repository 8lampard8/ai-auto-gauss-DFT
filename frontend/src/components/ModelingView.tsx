import { useEffect } from 'react'
import { useStore } from '../store'
import { MoleculeViewer } from './MoleculeViewer'
import { ImportPanel } from './ImportPanel'
import { GjfEditor } from './GjfEditor'

export function ModelingView() {
  const molecule = useStore((s) => s.currentMolecule)
  const refreshMolecules = useStore((s) => s.refreshMolecules)

  useEffect(() => { refreshMolecules() }, [refreshMolecules])

  return (
    <div className="grid-2">
      <div className="card" style={{ minHeight: 0 }}>
        <div className="card-head">
          <span>3D 分子查看器</span>
          <div className="spacer" />
          {molecule && <span className="sub">{molecule.charge} {molecule.multiplicity} · {molecule.atoms.length} 原子 · {molecule.source}</span>}
        </div>
        <div className="card-body flush" style={{ display: 'flex', flexDirection: 'column' }}>
          {molecule ? (
            <>
              <div className="viewer-host" style={{ flex: 1 }}>
                <MoleculeViewer molecule={molecule} />
              </div>
              <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', fontSize: 12 }}>
                <b>{molecule.name}</b>
                {molecule.smiles && <span className="muted"> · SMILES: {molecule.smiles}</span>}
                {molecule.route && <div className="muted">Route: {molecule.route}</div>}
              </div>
            </>
          ) : (
            <div className="placeholder">
              <div className="big">🧪</div>
              <div>从右侧导入分子,或在「对话」中描述</div>
              <div className="muted">支持 SMILES / 名称 / 文件 / 绘制</div>
            </div>
          )}
        </div>
      </div>

      <div className="col">
        <ImportPanel />
        <GjfEditor />
      </div>
    </div>
  )
}
