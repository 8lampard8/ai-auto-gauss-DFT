import { useEffect, lazy, Suspense } from 'react'
import { api } from './api/client'
import { useStore } from './store'
import type { SystemInfo } from './types'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { Workspace } from './components/Workspace'
import { JobSubmitDialog } from './components/JobSubmitDialog'

// Ketcher is heavy (~20MB, Indigo WASM) - lazy-load so it only ships when the
// draw dialog is opened.
const DrawMoleculeDialog = lazy(() =>
  import('./components/DrawMoleculeDialog').then((m) => ({ default: m.DrawMoleculeDialog })),
)

export default function App() {
  const setHealth = useStore((s) => s.setHealth)
  const setSystemInfo = useStore((s) => s.setSystemInfo)
  const refreshSettings = useStore((s) => s.refreshSettings)
  const refreshCatalog = useStore((s) => s.refreshCatalog)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const refreshJobs = useStore((s) => s.refreshJobs)
  const drawOpen = useStore((s) => s.drawOpen)

  useEffect(() => {
    api.get('/health').then(() => setHealth('ok')).catch(() => setHealth('down'))
    api.get<SystemInfo>('/system/info').then(setSystemInfo).catch(() => {})
    refreshSettings(); refreshCatalog(); refreshMolecules(); refreshJobs()
  }, [setHealth, setSystemInfo, refreshSettings, refreshCatalog, refreshMolecules, refreshJobs])

  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <TopBar />
        <Workspace />
      </div>
      <JobSubmitDialog />
      {drawOpen && (
        <Suspense fallback={<div className="overlay"><div className="modal draw-modal"><div className="modal-body"><div className="muted">加载绘制器…</div></div></div></div>}>
          <DrawMoleculeDialog />
        </Suspense>
      )}
    </div>
  )
}
