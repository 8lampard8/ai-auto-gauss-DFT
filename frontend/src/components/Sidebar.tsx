import { useStore, activeModelLabel } from '../store'
import { api } from '../api/client'
import { useT } from '../i18n'
import type { Molecule } from '../types'
import type { ViewName } from '../store'

const NAV: { key: ViewName; zh: string; en: string; ico: string }[] = [
  { key: 'modeling', zh: '建模', en: 'Modeling', ico: '🧪' },
  { key: 'editor', zh: '编辑', en: 'Editor', ico: '✏️' },
  { key: 'chat', zh: '对话', en: 'Chat', ico: '💬' },
  { key: 'jobs', zh: '任务', en: 'Jobs', ico: '🧮' },
  { key: 'descriptors', zh: '描述符', en: 'Descriptors', ico: '🧬' },
  { key: 'plot', zh: '作图', en: 'Plot', ico: '📊' },
  { key: 'settings', zh: '设置', en: 'Settings', ico: '⚙️' },
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
  const { lang, tr } = useT()

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
            {tr(n.zh, n.en)}
          </button>
        ))}
      </nav>
      <div className="mol-list">
        <div className="title">{tr('已保存分子', 'Saved Molecules')}</div>
        {moleculeList.length === 0 && (
          <div className="muted" style={{ padding: '6px 4px' }}>
            {tr('(空)', '(empty)')}
          </div>
        )}
        {moleculeList.map((m) => (
          <div
            key={m.id}
            className={`mol-item ${currentMolecule?.id === m.id ? 'active' : ''}`}
            onClick={() => load(m.id)}
            title={`${m.formula} · ${m.natoms} ${tr('原子', 'atoms')} · ${m.source}`}
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
          {health === 'ok'
            ? tr('后端已连接', 'Backend connected')
            : health === 'down'
              ? tr('未连接', 'Disconnected')
              : '…'}
        </div>
        <div className="muted" style={{ marginTop: 4 }}>
          {sys ? `CPU ${sys.cpu_count}c · RAM ${sys.ram_total_gb}GB` : ''}
        </div>
        <div className="muted">{activeModelLabel(settings, lang)}</div>
      </div>
    </aside>
  )
}
