import { Component, useEffect, useState, type ReactNode } from 'react'
import { Editor } from 'ketcher-react'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import 'ketcher-react/dist/index.css'

/** Contain Ketcher errors so a failure never blanks the host view. */
class KetcherBoundary extends Component<{ children: ReactNode }, { err: string }> {
  state = { err: '' }
  static getDerivedStateFromError(e: any) { return { err: String(e) } }
  render() {
    if (this.state.err) {
      return (
        <div className="placeholder" style={{ height: '100%' }}>
          <div className="big">⚠️</div>
          <div>绘制器出错</div>
          <div className="muted" style={{ maxWidth: 460 }}>{this.state.err}</div>
          <button className="ghost sm" onClick={() => this.setState({ err: '' })}>重试</button>
        </div>
      )
    }
    return this.props.children
  }
}

/** Reusable embedded Ketcher 2D editor. Calls onInit with the Ketcher instance. */
export function KetcherEditor({ onInit }: { onInit: (k: any) => void }) {
  const [provider, setProvider] = useState<any>(null)
  const [initErr, setInitErr] = useState('')

  useEffect(() => {
    if (!provider && !initErr) {
      try {
        setProvider(new StandaloneStructServiceProvider())
      } catch (e) {
        setInitErr(e instanceof Error ? e.message : String(e))
      }
    }
  }, [provider, initErr])

  if (initErr) {
    return <div className="placeholder" style={{ height: '100%' }}><div className="big">⚠️</div><div>绘制器后端初始化失败</div><div className="muted">{initErr}</div></div>
  }
  if (!provider) {
    return <div className="placeholder" style={{ height: '100%' }}><div className="muted">加载绘制器(Indigo WASM)…</div></div>
  }
  return (
    <div style={{ height: '100%' }}>
      <KetcherBoundary>
        <Editor
          staticResourcesUrl="/ketcher/"
          structServiceProvider={provider}
          errorHandler={(e: any) => console.error('[ketcher]', e)}
          onInit={onInit}
        />
      </KetcherBoundary>
    </div>
  )
}
