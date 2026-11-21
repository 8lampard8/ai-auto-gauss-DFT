import { useEffect } from 'react'
import { useStore } from '../store'
import { useT } from '../i18n'
import { MoleculeViewer } from './MoleculeViewer'
import { ImportPanel } from './ImportPanel'
import { GjfEditor } from './GjfEditor'

export function ModelingView() {
  const molecule = useStore((s) => s.currentMolecule)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const openDescriptors = useStore((s) => s.openDescriptors)
  const { tr } = useT()

  useEffect(() => { refreshMolecules() }, [refreshMolecules])

  return (
    <div className="grid-2">
      <div className="card" style={{ minHeight: 0 }}>
        <div className="card-head">
          <span>{tr('3D 分子查看器', '3D Molecule Viewer')}</span>
          <div className="spacer" />
          {molecule && (
            <>
              <span className="sub">
                {molecule.charge} {molecule.multiplicity} · {molecule.atoms.length} {tr('原子', 'atoms')} · {molecule.source}
              </span>
              <button
                className="ghost sm"
                onClick={() => openDescriptors({ kind: 'molecule', id: molecule.id })}
                title={tr('提取该分子的 RDKit 2D/3D 描述符', 'Extract RDKit 2D/3D descriptors')}
              >
                🧬 {tr('描述符', 'Descriptors')}
              </button>
            </>
          )}
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
              <div>{tr('从右侧导入分子,或在「对话」中描述', 'Import a molecule on the right, or describe it in Chat')}</div>
              <div className="muted">{tr('支持 SMILES / 名称 / 文件 / 绘制', 'Supports SMILES / Name / CAS / File / Draw')}</div>
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
