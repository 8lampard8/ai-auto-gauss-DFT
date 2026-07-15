import { create } from 'zustand'
import { api } from './api/client'
import type { Catalog, ChatMsg, Job, MethodSpec, Molecule, MoleculeSummary, Settings, SshProfile, SystemInfo } from './types'

export type Health = 'unknown' | 'ok' | 'down'
export type RightTab = 'chat' | 'jobs'
export type ViewName = 'modeling' | 'editor' | 'chat' | 'jobs' | 'plot' | 'settings'

interface AppState {
  health: Health
  systemInfo: SystemInfo | null
  settings: Settings | null
  catalog: Catalog | null
  settingsOpen: boolean
  chat: ChatMsg[]
  chatStreaming: boolean
  // molecules
  currentMolecule: Molecule | null
  moleculeList: MoleculeSummary[]
  importOpen: boolean
  // gjf
  currentGjf: string
  gjfEditorOpen: boolean
  pendingSpec: MethodSpec | null
  // jobs
  jobs: Job[]
  jobSubmitOpen: boolean
  rightTab: RightTab
  activeView: ViewName
  // visualize
  plotOpen: boolean
  drawOpen: boolean
  // setters / actions
  setActiveView: (v: ViewName) => void
  setPlotOpen: (b: boolean) => void
  setDrawOpen: (b: boolean) => void
  setHealth: (h: Health) => void
  setSystemInfo: (s: SystemInfo | null) => void
  openSettings: () => void
  closeSettings: () => void
  refreshSettings: () => Promise<void>
  refreshCatalog: () => Promise<void>
  addChat: (m: ChatMsg) => void
  appendChat: (content: string) => void
  setChatStreaming: (b: boolean) => void
  clearChat: () => void
  setCurrentMolecule: (m: Molecule | null) => void
  setImportOpen: (b: boolean) => void
  refreshMolecules: () => Promise<void>
  setCurrentGjf: (g: string) => void
  setGjfEditorOpen: (b: boolean) => void
  setPendingSpec: (s: MethodSpec | null) => void
  setJobSubmitOpen: (b: boolean) => void
  setRightTab: (t: RightTab) => void
  refreshJobs: () => Promise<void>
}

export const useStore = create<AppState>((set, get) => ({
  health: 'unknown',
  systemInfo: null,
  settings: null,
  catalog: null,
  settingsOpen: false,
  chat: [
    {
      role: 'assistant',
      content:
        '你好!我是 Gaussian 量化计算助手。先在左侧「导入分子」载入结构,然后描述计算需求(如「优化+频率」「过渡态」「激发态」「溶剂效应」「IGMH 作图」),我会推荐方法并生成 gjf。\n\n当前若未配置 AI,将以 Mock 演示模式回复;在右上角「设置」中配置真实模型后即可获得完整智能。',
    },
  ],
  chatStreaming: false,
  currentMolecule: null,
  moleculeList: [],
  importOpen: false,
  currentGjf: '',
  gjfEditorOpen: false,
  pendingSpec: null,
  jobs: [],
  jobSubmitOpen: false,
  rightTab: 'chat',
  activeView: 'modeling',
  plotOpen: false,
  drawOpen: false,
  setHealth: (health) => set({ health }),
  setSystemInfo: (systemInfo) => set({ systemInfo }),
  openSettings: () => set({ settingsOpen: true }),
  closeSettings: () => set({ settingsOpen: false }),
  refreshSettings: async () => {
    try {
      const s = await api.get<Settings>('/models/providers')
      set({ settings: s })
    } catch {
      /* ignore */
    }
  },
  refreshCatalog: async () => {
    try {
      const c = await api.get<Catalog>('/models/catalog')
      set({ catalog: c })
    } catch {
      /* ignore */
    }
  },
  addChat: (m) => set((st) => ({ chat: [...st.chat, m] })),
  appendChat: (content) =>
    set((st) => {
      const chat = [...st.chat]
      const last = chat[chat.length - 1]
      if (last && last.role === 'assistant') {
        chat[chat.length - 1] = { ...last, content: last.content + content }
      } else {
        chat.push({ role: 'assistant', content })
      }
      return { chat }
    }),
  setChatStreaming: (chatStreaming) => set({ chatStreaming }),
  clearChat: () =>
    set({
      chat: [{ role: 'assistant', content: '对话已清空。请描述你的计算需求。' }],
    }),
  setCurrentMolecule: (currentMolecule) => set({ currentMolecule }),
  setImportOpen: (importOpen) => set({ importOpen }),
  refreshMolecules: async () => {
    try {
      const r = await api.get<{ molecules: MoleculeSummary[] }>('/molecules')
      set({ moleculeList: r.molecules })
    } catch {
      /* ignore */
    }
  },
  setCurrentGjf: (currentGjf) => set({ currentGjf, gjfEditorOpen: true }),
  setGjfEditorOpen: (gjfEditorOpen) => set({ gjfEditorOpen }),
  setPendingSpec: (pendingSpec) => set({ pendingSpec }),
  setJobSubmitOpen: (jobSubmitOpen) => set({ jobSubmitOpen }),
  setRightTab: (rightTab) => set({ rightTab }),
  setActiveView: (activeView) => set({ activeView }),
  setPlotOpen: (plotOpen) => set({ plotOpen }),
  setDrawOpen: (drawOpen) => set({ drawOpen }),
  refreshJobs: async () => {
    try {
      const r = await api.get<{ jobs: Job[] }>('/jobs')
      set({ jobs: r.jobs })
    } catch {
      /* ignore */
    }
  },
}))

export function activeModelLabel(s: Settings | null): string {
  if (!s) return '未配置'
  const pid = s.active_provider_id || 'mock'
  const p = s.providers.find((x) => x.id === pid)
  const name = pid === 'mock' ? 'Mock' : p?.name || pid
  const model = s.active_model || p?.default_model || '—'
  return `${name} / ${model}`
}
