import { Component, type ReactNode } from 'react'

/** Top-level error boundary: shows the error instead of a blank screen, so
 *  runtime crashes are diagnosable. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { err: string | null }> {
  state = { err: null as string | null }
  static getDerivedStateFromError(e: any) {
    return { err: e instanceof Error ? `${e.message}\n\n${e.stack || ''}` : String(e) }
  }
  componentDidCatch(e: any) {
    console.error('[app crash]', e)
  }
  render() {
    if (this.state.err) {
      return (
        <div style={{ padding: 24, fontFamily: 'monospace', fontSize: 12, color: '#dc2626', whiteSpace: 'pre-wrap', background: '#fff', minHeight: '100%' }}>
          <div style={{ fontSize: 15, marginBottom: 8 }}>应用运行时出错:</div>
          {this.state.err}
          <div style={{ marginTop: 12 }}>
            <button onClick={() => { this.setState({ err: null }); location.reload() }} style={{ padding: '6px 12px' }}>刷新重试</button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
