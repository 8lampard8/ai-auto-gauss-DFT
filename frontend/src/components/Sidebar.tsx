import { useStore, activeModelLabel } from '../store'
import { api } from '../api/client'
import type { Settings, Molecule } from '../types'
import type { ViewName } from '../store'

const NAV: { key: ViewName; label: string; ico: string }[] = [
  { key: 'modeling', label: '建模', ico: '🧪' },
  { key: 'editor', label: '编辑', ico: '✏️' },
  { key: 'chat', label: '对话', ico: '💬' },
  { key: 'jobs', label: '任务', ico: '🧮' },
  { key: 'plot', label: '作图', ico: '📊' },
  { key: 'settings', label: '设置', ico: '⚙️' },
]

export function Sidebar() {
  const activeView = useStore((s) => s.activeView)
  const setActiveView = useStore((s) => s.setActiveView)
  const moleculeList = useStore((s) => s.moleculeList)
  const currentMolecule = useStore((s) => s.currentMolecule)
  const setCurrentMolecule = useStore((s) => s.setCurrentMolecule)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const settings = useStore((s) => s.settings)
  const sys = useStore((s) => s.systemInfo)
  const health = useStore((s) => s.health)

  const load = async (id: string) => {
    const m = await api.get<Molecule>(`/molecules/${id}`)
    setCurrentMolecule(m)
  }
  const remove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await api.del(`/molecules/${id}`)
    if (currentMolecule?.id === id) setCurrentMolecule(null)
    refreshMolecules()
  }

  return (
    <aside className="sidebar">
      <div className="logo">
        <span className="dot" />
        ai-auto-gauss-<span style={{ color: 'var(--accent)' }}>DFT</span>
      </div>
      <nav className="nav">
        {NAV.map((n) => (
          <button
            key={n.key}
            className={activeView === n.key ? 'active' : ''}
            onClick={() => setActiveView(n.key)}
          >
            <span className="ico">{n.ico}</span>
            {n.label}
          </button>
        ))}
      </nav>
      <div className="mol-list">
        <div className="title">已保存分子</div>
        {moleculeList.length === 0 && (
          <div className="muted" style={{ padding: '6px 4px' }}>
            (空)
          </div>
        )}
        {moleculeList.map((m) => (
          <div
            key={m.id}
            className={`mol-item ${currentMolecule?.id === m.id ? 'active' : ''}`}
            onClick={() => load(m.id)}
            title={`${m.formula} · ${m.natoms} 原子 · ${m.source}`}
          >
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {m.name || m.id}
            </span>
            <span className="del" onClick={(e) => remove(m.id, e)}>
              ✕
            </span>
          </div>
        ))}
      </div>
      <div className="foot">
        <div className="chip">
          <span className={`health-dot ${health === 'ok' ? 'ok' : health === 'down' ? 'down' : ''}`} />
          {health === 'ok' ? '后端已连接' : health === 'down' ? '未连接' : '…'}
        </div>
        <div className="muted" style={{ marginTop: 4 }}>
          {sys ? `CPU ${sys.cpu_count}c · RAM ${sys.ram_total_gb}GB` : ''}
        </div>
        <div className="muted">{activeModelLabel(settings)}</div>
      </div>
    </aside>
  )
}
