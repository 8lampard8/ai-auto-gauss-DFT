import { lazy, Suspense } from 'react'
import { useStore } from '../store'
import { ModelingView } from './ModelingView'
import { ChatView } from './ChatView'
import { JobsView } from './JobsView'
import { PlotView } from './PlotView'
import { SettingsView } from './SettingsView'

// Ketcher is heavy - lazy-load the editor view.
const MoleculeEditorView = lazy(() =>
  import('./MoleculeEditorView').then((m) => ({ default: m.MoleculeEditorView })),
)

export function Workspace() {
  const view = useStore((s) => s.activeView)
  return (
    <div className="workspace" style={{ display: 'flex' }}>
      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        {view === 'modeling' && <ModelingView />}
        {view === 'editor' && (
          <Suspense fallback={<div className="placeholder"><div className="muted">加载编辑器…</div></div>}>
            <MoleculeEditorView />
          </Suspense>
        )}
        {view === 'chat' && <ChatView />}
        {view === 'jobs' && <JobsView />}
        {view === 'plot' && <PlotView />}
        {view === 'settings' && <SettingsView />}
      </div>
    </div>
  )
}
