import { useStore, activeModelLabel } from '../store'
import { api } from '../api/client'
import { useT } from '../i18n'

const TITLES: Record<string, [string, string]> = {
  modeling: ['分子建模', 'Molecular Modeling'],
  editor: ['2D/3D 分子编辑', '2D/3D Molecule Editor'],
  chat: ['AI 对话', 'AI Chat'],
  jobs: ['计算任务', 'Compute Jobs'],
  descriptors: ['分子描述符', 'Molecular Descriptors'],
  plot: ['结果作图', 'Result Plotting'],
  settings: ['设置', 'Settings'],
}

export function TopBar() {
  const activeView = useStore((s) => s.activeView)
  const settings = useStore((s) => s.settings)
  const refreshSettings = useStore((s) => s.refreshSettings)
  const health = useStore((s) => s.health)
  const { lang, setLang, tr } = useT()

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

  const titlePair = TITLES[activeView]

  return (
    <header className="topbar">
      <div className="title">{titlePair ? tr(titlePair[0], titlePair[1]) : ''}</div>
      <div className="spacer" />
      <div className="lang-switch" role="group" aria-label={tr('语言切换', 'Language')}>
        <button
          type="button"
          className={lang === 'zh' ? 'active' : ''}
          onClick={() => setLang('zh')}
        >
          中文
        </button>
        <button
          type="button"
          className={lang === 'en' ? 'active' : ''}
          onClick={() => setLang('en')}
        >
          EN
        </button>
      </div>
      <select
        className="model-select"
        value={value}
        title={tr('切换 AI 模型', 'Switch AI Model')}
        onChange={(e) => {
          const [pid, model] = e.target.value.split('|')
          setActive(pid, model)
        }}
      >
        <option value="mock|">{tr('Mock(演示,无需密钥)', 'Mock (Demo, no API key)')}</option>
        {(settings?.providers ?? []).map((p) =>
          (p.models.length ? p.models : ['(default)']).map((m) => (
            <option key={p.id + m} value={`${p.id}|${m === '(default)' ? '' : m}`}>
              {p.name} / {m === '(default)' ? tr('(默认)', '(default)') : m}
            </option>
          )),
        )}
        <option value="__manage__">{tr('- 管理设置…', '- Manage Settings…')}</option>
      </select>
      <span className={`health-dot ${health === 'ok' ? 'ok' : health === 'down' ? 'down' : ''}`} />
      <span className="muted">{activeModelLabel(settings, lang)}</span>
    </header>
  )
}
