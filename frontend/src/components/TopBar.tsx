import { useStore, activeModelLabel } from '../store'
import { api } from '../api/client'
import type { Settings } from '../types'

const TITLES: Record<string, string> = {
  modeling: '分子建模',
  editor: '2D/3D 分子编辑',
  chat: 'AI 对话',
  jobs: '计算任务',
  plot: '结果作图',
  settings: '设置',
}

export function TopBar() {
  const activeView = useStore((s) => s.activeView)
  const settings = useStore((s) => s.settings)
  const refreshSettings = useStore((s) => s.refreshSettings)
  const health = useStore((s) => s.health)

  const setActive = async (providerId: string, model: string) => {
    if (providerId === '__manage__') {
      useStore.getState().setActiveView('settings')
      return
    }
    await api.put('/models/active', { active_provider_id: providerId, active_model: model })
    await refreshSettings()
  }

  const value = settings
    ? `${settings.active_provider_id || 'mock'}|${settings.active_model || ''}`
    : 'mock|'

  return (
    <header className="topbar">
      <div className="title">{TITLES[activeView] || ''}</div>
      <div className="spacer" />
      <select
        className="model-select"
        value={value}
        title="切换 AI 模型"
        onChange={(e) => {
          const [pid, model] = e.target.value.split('|')
          setActive(pid, model)
        }}
      >
        <option value="mock|">Mock(演示,无需密钥)</option>
        {(settings?.providers ?? []).map((p) =>
          (p.models.length ? p.models : ['(默认)']).map((m) => (
            <option key={p.id + m} value={`${p.id}|${m === '(默认)' ? '' : m}`}>
              {p.name} / {m}
            </option>
          )),
        )}
        <option value="__manage__">- 管理设置…</option>
      </select>
      <span className={`health-dot ${health === 'ok' ? 'ok' : health === 'down' ? 'down' : ''}`} />
      <span className="muted">{activeModelLabel(settings)}</span>
    </header>
  )
}
