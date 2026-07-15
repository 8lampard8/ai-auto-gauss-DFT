import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import type { ProviderConfig, ProviderKind } from '../types'

const EMPTY: ProviderConfig = { id: '', name: '', kind: 'openai', base_url: '', api_key: '', models: [], default_model: '' }

export function SettingsView() {
  const settings = useStore((s) => s.settings)
  const catalog = useStore((s) => s.catalog)
  const refresh = useStore((s) => s.refreshSettings)
  const [form, setForm] = useState<ProviderConfig>(EMPTY)
  const [editing, setEditing] = useState(false)
  const [modelsText, setModelsText] = useState('')
  const [test, setTest] = useState<{ id: string; ok: boolean; msg: string } | null>(null)
  const [err, setErr] = useState('')
  const [paths, setPaths] = useState({ gaussian_path: '', multiwfn_path: '', vmd_path: '' })
  const [pathsSaved, setPathsSaved] = useState(false)

  useEffect(() => {
    refresh()
    setForm(EMPTY); setEditing(false); setModelsText(''); setErr(''); setTest(null); setPathsSaved(false)
  }, [refresh])
  useEffect(() => {
    if (settings) setPaths({ gaussian_path: settings.gaussian_path, multiwfn_path: settings.multiwfn_path, vmd_path: settings.vmd_path })
  }, [settings])

  const edit = (p: ProviderConfig) => { setForm({ ...p }); setEditing(true); setModelsText(p.models.join('\n')); setErr(''); setTest(null) }
  const reset = () => { setForm(EMPTY); setEditing(false); setModelsText(''); setErr('') }
  const applyPreset = (preset: Partial<ProviderConfig>) => {
    const name = preset.name || ''
    const id = form.id || name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'prov-' + Math.random().toString(36).slice(2, 6)
    setForm((f) => ({ ...f, ...preset, id }))
    setModelsText((preset.models || []).join('\n'))
  }
  const save = async () => {
    setErr('')
    const id = form.id.trim()
    if (!id) { setErr('需要 Provider ID'); return }
    const models = modelsText.split('\n').map((s) => s.trim()).filter(Boolean)
    const payload: ProviderConfig = { ...form, id, models, default_model: form.default_model || models[0] || '' }
    try {
      if (editing) await api.put(`/models/providers/${id}`, payload)
      else await api.post('/models/providers', payload)
      await refresh(); reset()
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)) }
  }
  const remove = async (id: string) => { if (confirm(`删除 provider "${id}"?`)) { await api.del(`/models/providers/${id}`); await refresh(); if (form.id === id) reset() } }
  const testConn = async (id: string) => {
    setTest({ id, ok: false, msg: '测试中…' })
    try { const r = await api.post<{ ok: boolean; message: string }>(`/models/providers/${id}/test`); setTest({ id, ok: r.ok, msg: r.message }) }
    catch (e) { setTest({ id, ok: false, msg: e instanceof Error ? e.message : String(e) }) }
  }
  const setActive = async (p: ProviderConfig) => { await api.put('/models/active', { active_provider_id: p.id, active_model: p.default_model || p.models[0] || '' }); await refresh() }
  const savePaths = async () => { await api.put('/models/paths', paths); await refresh(); setPathsSaved(true) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%', overflow: 'auto' }}>
      <div className="card">
        <div className="card-head"><span>AI Provider</span></div>
        <div className="card-body">
          <div className="section-title">{editing ? '编辑 Provider' : '新增 Provider'}</div>
          <div className="row" style={{ flexWrap: 'wrap', marginBottom: 8 }}>
            <span className="muted">预设:</span>
            {(catalog?.presets || []).map((p, i) => <button key={i} className="ghost sm" onClick={() => applyPreset(p)}>{p.name}</button>)}
          </div>
          <div className="form-grid">
            <label className="field"><span className="lbl">ID</span><input value={form.id} disabled={editing} onChange={(e) => setForm({ ...form, id: e.target.value })} placeholder="my-openai" /></label>
            <label className="field"><span className="lbl">名称</span><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label className="field"><span className="lbl">类型</span>
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as ProviderKind })}>
                <option value="openai">openai(OpenAI 协议)</option>
                <option value="custom">custom(OpenAI 兼容)</option>
                <option value="anthropic">anthropic(Claude)</option>
                <option value="mock">mock(演示)</option>
              </select>
            </label>
            <label className="field"><span className="lbl">Base URL</span><input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} /></label>
            <label className="field"><span className="lbl">API Key{editing ? '(留空保持)' : ''}</span><input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} /></label>
            <label className="field"><span className="lbl">默认模型</span><input value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} /></label>
            <label className="field" style={{ gridColumn: '1 / -1' }}><span className="lbl">模型列表(每行一个)</span><textarea value={modelsText} onChange={(e) => setModelsText(e.target.value)} rows={3} /></label>
          </div>
          {err && <div className="err-text">{err}</div>}
          <div className="row" style={{ marginTop: 8 }}>
            <button className="primary" onClick={save}>{editing ? '保存修改' : '添加'}</button>
            {editing && <button onClick={reset}>取消编辑</button>}
          </div>

          <div className="section-title" style={{ marginTop: 16 }}>已配置</div>
          <div className="prov-list">
            {(settings?.providers || []).map((p) => (
              <div key={p.id} className="prov-item">
                <div>
                  <b>{p.name || p.id}</b> <span className="muted">[{p.kind}] · {p.models.length} 模型 · key {p.api_key || '(空)'}</span>
                  {settings?.active_provider_id === p.id && <span className="ok-text"> · 活跃</span>}
                  {test?.id === p.id && <span className={test.ok ? 'ok-text' : 'err-text'}> - {test.msg}</span>}
                </div>
                <div className="row">
                  <button className="ghost sm" onClick={() => setActive(p)}>设为活跃</button>
                  <button className="ghost sm" onClick={() => testConn(p.id)}>测试</button>
                  <button className="ghost sm" onClick={() => edit(p)}>编辑</button>
                  <button className="ghost sm" onClick={() => remove(p.id)}>删除</button>
                </div>
              </div>
            ))}
            {(settings?.providers || []).length === 0 && <div className="muted">尚未配置。</div>}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><span>外部工具路径</span></div>
        <div className="card-body">
          <div className="form-grid">
            <label className="field"><span className="lbl">Gaussian (g16 / g09w.exe)</span><input value={paths.gaussian_path} onChange={(e) => setPaths({ ...paths, gaussian_path: e.target.value })} placeholder="D:\gauss\G09W\g09w.exe" /></label>
            <label className="field"><span className="lbl">Multiwfn</span><input value={paths.multiwfn_path} onChange={(e) => setPaths({ ...paths, multiwfn_path: e.target.value })} placeholder="D:\Multiwfn...\Multiwfn.exe" /></label>
            <label className="field"><span className="lbl">VMD</span><input value={paths.vmd_path} onChange={(e) => setPaths({ ...paths, vmd_path: e.target.value })} placeholder="D:\VMD\vmd.exe" /></label>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button onClick={savePaths}>保存路径</button>
            {pathsSaved && <span className="ok-text">已保存</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
