const BASE = '/api'

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    // Surface the backend's `detail` message (FastAPI: {"detail": "..."})
    // so the UI shows the real reason instead of a bare status code.
    let detail = ''
    try {
      const j = await r.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j)
    } catch {
      try {
        detail = await r.text()
      } catch {
        /* ignore */
      }
    }
    throw new Error(detail || `${method} ${path} -> ${r.status} ${r.statusText}`)
  }
  return r.json() as Promise<T>
}

export const api = {
  get: <T>(p: string) => req<T>('GET', p),
  post: <T>(p: string, body?: unknown) => req<T>('POST', p, body),
  put: <T>(p: string, body?: unknown) => req<T>('PUT', p, body),
  del: <T>(p: string) => req<T>('DELETE', p),
}

/** SSE stream reader for the chat endpoint. Yields decoded `data:` payloads. */
export async function* streamPost(path: string, body: unknown): AsyncGenerator<string> {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok || !r.body) throw new Error(`stream ${path} -> ${r.status} ${r.statusText}`)
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() || ''
    for (const line of lines) {
      const t = line.trim()
      if (t.startsWith('data:')) yield t.slice(5).trim()
    }
  }
}
