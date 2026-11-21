import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, downloadPost } from '../api/client'
import { DESC_HINTS_EN, DESC_LABELS_EN, GROUP_LABELS_EN, useT } from '../i18n'
import { useStore } from '../store'
import type {
  BatchDescriptorResult,
  DescriptorGroup,
  DescriptorItem,
  DescriptorResponse,
} from '../types'

function formatValue(v: DescriptorItem['value'], en: boolean): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? (en ? 'Yes' : '是') : (en ? 'No' : '否')
  return String(v)
}

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function csvCell(v: unknown): string {
  if (v === null || v === undefined) return ''
  const s = String(v)
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function readFileText(file: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload = () => res(String(r.result || ''))
    r.onerror = () => rej(r.error)
    r.readAsText(file)
  })
}

export function DescriptorsView() {
  const moleculeList = useStore((s) => s.moleculeList)
  const currentMolecule = useStore((s) => s.currentMolecule)
  const jobs = useStore((s) => s.jobs)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const refreshJobs = useStore((s) => s.refreshJobs)
  const descriptorTarget = useStore((s) => s.descriptorTarget)
  const openDescriptors = useStore((s) => s.openDescriptors)
  const { lang, tr } = useT()
  const isEn = lang === 'en'

  const [mode, setMode] = useState<'single' | 'batch'>('single')

  // --- Single extraction state ---
  const [molId, setMolId] = useState('')
  const [jobId, setJobId] = useState('')
  const [includeAll, setIncludeAll] = useState(false)
  const [filterText, setFilterText] = useState('')
  const [result, setResult] = useState<DescriptorResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [copiedKey, setCopiedKey] = useState('')
  const [dragOver, setDragOver] = useState(false)

  // --- Batch extraction state ---
  const [selMols, setSelMols] = useState<string[]>([])
  const [selJobs, setSelJobs] = useState<string[]>([])
  const [smilesText, setSmilesText] = useState('')
  const [batchAll, setBatchAll] = useState(false)
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchErr, setBatchErr] = useState('')
  const [batchRes, setBatchRes] = useState<BatchDescriptorResult | null>(null)

  const jobsWithLog = useMemo(() => jobs.filter((j) => Boolean(j.log_path)), [jobs])

  const groupLabel = (g: DescriptorGroup) =>
    isEn ? (GROUP_LABELS_EN[g.id] || g.label) : g.label
  const itemLabel = (it: DescriptorItem) =>
    isEn ? (DESC_LABELS_EN[it.key] || it.label) : it.label

  const fetchMolecule = useCallback(async (id: string, full: boolean) => {
    if (!id) return
    setBusy(true); setErr('')
    try {
      const r = await api.get<DescriptorResponse>(`/descriptors/molecule/${id}?full=${full}`)
      setResult(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }, [])

  const fetchJob = useCallback(async (id: string, full: boolean) => {
    if (!id) return
    setBusy(true); setErr('')
    try {
      const r = await api.get<DescriptorResponse>(`/descriptors/job/${id}?full=${full}`)
      setResult(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }, [])

  const parseLogFile = async (file: File) => {
    setBusy(true); setErr('')
    try {
      const text = await readFileText(file)
      const r = await api.post<DescriptorResponse>('/descriptors/parse-log', {
        content: text,
        filename: file.name,
        full: includeAll,
        include_rdkit: true,
      })
      setResult(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    refreshMolecules()
    refreshJobs()
  }, [refreshMolecules, refreshJobs])

  useEffect(() => {
    if (descriptorTarget) {
      setMode('single')
      if (descriptorTarget.kind === 'molecule') {
        setMolId(descriptorTarget.id)
        fetchMolecule(descriptorTarget.id, includeAll)
      } else {
        setJobId(descriptorTarget.id)
        fetchJob(descriptorTarget.id, includeAll)
      }
      openDescriptors(null)
    } else if (!result && currentMolecule && !molId) {
      setMolId(currentMolecule.id)
      fetchMolecule(currentMolecule.id, includeAll)
    }
  }, [descriptorTarget, currentMolecule, molId, result, includeAll, fetchMolecule, fetchJob, openDescriptors])

  const onToggleAll = (checked: boolean) => {
    setIncludeAll(checked)
    if (result?.kind === 'molecule') fetchMolecule(result.id, checked)
    else if (result?.kind === 'job') fetchJob(result.id, checked)
  }

  const copyValue = (key: string, val: string) => {
    navigator.clipboard?.writeText(val)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey((cur) => (cur === key ? '' : cur)), 1200)
  }

  const exportSingleCsv = () => {
    if (!result) return
    const lines = ['key,label,value,unit,category']
    const pushGroups = (groups: DescriptorGroup[] | undefined, cat: string) => {
      for (const g of groups || []) {
        for (const it of g.items) {
          lines.push(
            [it.key, itemLabel(it), it.value ?? '', it.unit, `${cat}/${groupLabel(g)}`].map(csvCell).join(','),
          )
        }
      }
    }
    pushGroups(result.quantum?.groups, 'DFT')
    pushGroups(result.structure?.groups, 'RDKit')
    if (result.structure?.all) {
      for (const [k, v] of Object.entries(result.structure.all)) {
        lines.push([`rdkit_${k}`, k, v ?? '', '', 'RDKit_All2D'].map(csvCell).join(','))
      }
    }
    const safeName = (result.name || result.id).replace(/[^A-Za-z0-9_\u4e00-\u9fa5-]+/g, '_')
    downloadBlob(`${safeName}_descriptors.csv`, '\ufeff' + lines.join('\n'), 'text/csv;charset=utf-8')
  }

  const exportSingleJson = () => {
    if (!result) return
    const safeName = (result.name || result.id).replace(/[^A-Za-z0-9_\u4e00-\u9fa5-]+/g, '_')
    downloadBlob(
      `${safeName}_descriptors.json`,
      JSON.stringify(result, null, 2),
      'application/json;charset=utf-8',
    )
  }

  const q = filterText.trim().toLowerCase()
  const filterGroups = (groups: DescriptorGroup[] | undefined): DescriptorGroup[] => {
    if (!groups) return []
    if (!q) return groups
    return groups
      .map((g) => ({
        ...g,
        items: g.items.filter(
          (it) =>
            it.label.toLowerCase().includes(q) ||
            (DESC_LABELS_EN[it.key] || '').toLowerCase().includes(q) ||
            it.key.toLowerCase().includes(q) ||
            String(it.value ?? '').toLowerCase().includes(q),
        ),
      }))
      .filter((g) => g.items.length > 0)
  }

  const quantumGroups = filterGroups(result?.quantum?.groups)
  const structureGroups = filterGroups(result?.structure?.groups)
  const allRdkitEntries = useMemo(() => {
    const all = result?.structure?.all
    if (!all) return []
    const entries = Object.entries(all)
    if (!q) return entries
    return entries.filter(([k]) => k.toLowerCase().includes(q))
  }, [result, q])

  const kpis = useMemo(() => {
    if (!result) return []
    const f = result.flat || {}
    const out: { label: string; value: string; unit?: string }[] = []
    if (f.formula) out.push({ label: tr('分子式', 'Formula'), value: String(f.formula) })
    if (f.mol_wt !== undefined) out.push({ label: tr('分子量', 'Mol. Weight'), value: String(f.mol_wt), unit: 'g/mol' })
    if (f.logp !== undefined) out.push({ label: 'logP', value: String(f.logp) })
    if (f.tpsa !== undefined) out.push({ label: 'TPSA', value: String(f.tpsa), unit: 'Å²' })
    if (f.scf_energy !== undefined) out.push({ label: tr('SCF 能量', 'SCF Energy'), value: String(f.scf_energy), unit: 'Ha' })
    if (f.homo !== undefined) out.push({ label: 'HOMO', value: String(f.homo), unit: 'eV' })
    if (f.lumo !== undefined) out.push({ label: 'LUMO', value: String(f.lumo), unit: 'eV' })
    if (f.gap !== undefined) out.push({ label: tr('能隙 Gap', 'HOMO-LUMO Gap'), value: String(f.gap), unit: 'eV' })
    if (f.dipole !== undefined) out.push({ label: tr('偶极矩', 'Dipole'), value: String(f.dipole), unit: 'D' })
    if (f.n_imag !== undefined) out.push({ label: tr('虚频数', 'Imag. Freqs'), value: String(f.n_imag) })
    return out
  }, [result, lang])

  const buildBatchPayload = () => ({
    molecule_ids: selMols,
    job_ids: selJobs,
    smiles_list: smilesText
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s && !s.startsWith('#')),
    include_all_rdkit: batchAll,
  })

  const runBatch = async () => {
    setBatchBusy(true); setBatchErr('')
    try {
      const r = await api.post<BatchDescriptorResult>('/descriptors/batch', buildBatchPayload())
      setBatchRes(r)
    } catch (e) {
      setBatchErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBatchBusy(false)
    }
  }

  const exportBatch = async (format: 'csv' | 'json') => {
    setBatchBusy(true); setBatchErr('')
    try {
      await downloadPost(
        '/descriptors/export',
        { ...buildBatchPayload(), format },
        `descriptors.${format}`,
      )
    } catch (e) {
      setBatchErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBatchBusy(false)
    }
  }

  const toggleId = (list: string[], id: string, setter: (v: string[]) => void) => {
    setter(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])
  }

  const renderGroup = (g: DescriptorGroup) => (
    <div key={g.id} className="desc-card">
      <div className="desc-card-head">
        <span>{groupLabel(g)}</span>
        <span className="muted">{g.items.length} {tr('项', 'items')}</span>
      </div>
      <div className="desc-items">
        {g.items.map((it) => {
          const valStr = formatValue(it.value, isEn)
          const copyText = it.unit ? `${valStr} ${it.unit}` : valStr
          const hintText = isEn ? (DESC_HINTS_EN[it.key] || it.hint) : it.hint
          return (
            <div
              key={it.key}
              className="desc-row"
              title={hintText ? `${hintText} (${tr('点击复制', 'click to copy')})` : tr('点击复制数值', 'Click to copy')}
              onClick={() => copyValue(it.key, copyText)}
            >
              <span className="desc-lbl">{itemLabel(it)}</span>
              <span className="desc-val">
                {copiedKey === it.key ? (
                  <span className="ok-text">{tr('已复制', 'Copied')}</span>
                ) : (
                  <>
                    <span className="mono">{valStr}</span>
                    {it.unit && <span className="desc-unit">{it.unit}</span>}
                  </>
                )}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )

  const schemes = result?.quantum?.charge_schemes || []
  const hasSpin = Boolean(result?.quantum?.atom_charges?.some((a) => a.mulliken_spin !== undefined))

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-head">
        <span>{tr('分子描述符提取', 'Molecular Descriptor Extraction')}</span>
        <span className="sub">{tr('RDKit 2D/3D 结构描述符 + Gaussian DFT 量化描述符', 'RDKit 2D/3D Structure + Gaussian DFT Quantum Descriptors')}</span>
      </div>
      <div className="tabs">
        <button className={mode === 'single' ? 'active' : ''} onClick={() => setMode('single')}>
          {tr('单分子 / 任务提取', 'Single Molecule / Job')}
        </button>
        <button className={mode === 'batch' ? 'active' : ''} onClick={() => setMode('batch')}>
          {tr('批量提取与导出 (QSAR/ML)', 'Batch Extract & Export (QSAR/ML)')}
        </button>
      </div>

      {mode === 'single' ? (
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="desc-toolbar">
            <div className="row" style={{ flex: '1 1 260px' }}>
              <select
                value={molId}
                onChange={(e) => setMolId(e.target.value)}
                style={{ flex: 1 }}
              >
                <option value="">{tr('- 选择已保存分子 -', '- Select saved molecule -')}</option>
                {moleculeList.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name || m.id} ({m.formula} · {m.natoms}{tr('原子', ' atoms')})
                  </option>
                ))}
              </select>
              <button
                className="primary sm"
                disabled={busy || !molId}
                onClick={() => fetchMolecule(molId, includeAll)}
              >
                {tr('提取结构', 'Extract 2D/3D')}
              </button>
            </div>

            <div className="row" style={{ flex: '1 1 280px' }}>
              <select
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                style={{ flex: 1 }}
              >
                <option value="">{tr('- 选择含日志的计算任务 -', '- Select job with log -')}</option>
                {jobsWithLog.map((j) => (
                  <option key={j.id} value={j.id}>
                    [{j.status}] {j.molecule_name} · {j.spec_label}
                  </option>
                ))}
              </select>
              <button
                className="primary sm"
                disabled={busy || !jobId}
                onClick={() => fetchJob(jobId, includeAll)}
              >
                {tr('提取量化+结构', 'Extract DFT + 2D/3D')}
              </button>
            </div>

            <label
              className={`desc-upload ${dragOver ? 'dragover' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const f = e.dataTransfer.files?.[0]
                if (f) parseLogFile(f)
              }}
            >
              <input
                type="file"
                accept=".log,.out,.txt"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) parseLogFile(f)
                  e.target.value = ''
                }}
              />
              📄 {tr('上传/拖入 .log/.out 直接解析', 'Upload / Drop .log/.out to parse')}
            </label>
          </div>

          <div className="row" style={{ flexWrap: 'wrap', gap: 10 }}>
            <input
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder={tr(
                '筛选描述符（如 HOMO / gap / logP / TPSA / Gibbs / 硬度 / 偶极）…',
                'Filter descriptors (e.g. HOMO / gap / logP / TPSA / Gibbs / hardness / dipole)…',
              )}
              style={{ flex: '1 1 240px', padding: '6px 10px', fontSize: 13 }}
            />
            <label className="row" style={{ fontSize: 12, color: 'var(--text-dim)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={includeAll}
                onChange={(e) => onToggleAll(e.target.checked)}
                style={{ width: 14, height: 14 }}
              />
              {tr('包含全部 RDKit 2D (~217 项)', 'Include all RDKit 2D (~217)')}
            </label>
            <div className="spacer" />
            {result && (
              <>
                <button className="sm" onClick={exportSingleCsv}>{tr('导出 CSV', 'Export CSV')}</button>
                <button className="sm" onClick={exportSingleJson}>{tr('导出 JSON', 'Export JSON')}</button>
                <button
                  className="ghost sm"
                  onClick={() => copyValue('__json__', JSON.stringify(result.flat, null, 2))}
                >
                  {copiedKey === '__json__'
                    ? tr('✓ 已复制 JSON', '✓ Copied JSON')
                    : tr('复制扁平 JSON', 'Copy flat JSON')}
                </button>
              </>
            )}
          </div>

          {err && <div className="err-text">{err}</div>}
          {busy && <div className="muted">{tr('正在计算与解析分子描述符…', 'Computing & parsing molecular descriptors…')}</div>}

          {!result && !busy && (
            <div className="placeholder">
              <div className="big">🧬</div>
              <div>{tr('选择分子、计算任务，或直接拖入 Gaussian .log / .out 文件', 'Select a molecule or job, or drop a Gaussian .log / .out file')}</div>
              <div className="muted">
                {tr(
                  '支持 RDKit 理化/类药性/拓扑/3D 形状描述符，以及 DFT 能量、HOMO/LUMO、概念 DFT 反应性指数、偶极矩、极化率、热力学、TD-DFT 激发态与原子电荷',
                  'Extracts RDKit physicochemical/topological/3D shape descriptors plus DFT energies, HOMO/LUMO, conceptual DFT reactivity indices, dipole, polarizability, thermochemistry, TD-DFT states & atomic charges',
                )}
              </div>
            </div>
          )}

          {result && (
            <>
              <div className="row" style={{ flexWrap: 'wrap' }}>
                <b style={{ fontSize: 15 }}>{result.name}</b>
                {result.spec_label && <span className="badge">{result.spec_label}</span>}
                {result.quantum && <span className="badge succeeded">{tr('DFT 量化描述符', 'DFT Quantum')}</span>}
                {result.structure && (
                  <span className="badge">RDKit ({result.structure.perception})</span>
                )}
                <span className="muted" style={{ marginLeft: 'auto' }}>
                  {tr(
                    `共 ${Object.keys(result.flat || {}).length} 项核心描述符${result.structure?.all ? ` + ${Object.keys(result.structure.all).length} 项全量 2D` : ''} · 点击任意项可复制`,
                    `${Object.keys(result.flat || {}).length} core descriptors${result.structure?.all ? ` + ${Object.keys(result.structure.all).length} full 2D` : ''} · click any row to copy`,
                  )}
                </span>
              </div>

              {result.warnings.length > 0 && (
                <div className="desc-warn">
                  {result.warnings.map((w, i) => (
                    <div key={i}>⚠ {w}</div>
                  ))}
                </div>
              )}

              {kpis.length > 0 && (
                <div className="desc-kpi-row">
                  {kpis.map((k) => (
                    <div key={k.label} className="desc-kpi">
                      <div className="k">{k.label}</div>
                      <div className="v">
                        {k.value}
                        {k.unit && <span className="u">{k.unit}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {quantumGroups.length > 0 && (
                <>
                  <div className="section-title">{tr('量子化学描述符 (Gaussian DFT)', 'Quantum-Chemical Descriptors (Gaussian DFT)')}</div>
                  <div className="desc-grid">{quantumGroups.map(renderGroup)}</div>
                </>
              )}

              {result.quantum && result.quantum.atom_charges.length > 0 && (
                <div>
                  <div className="section-title">
                    {tr('原子电荷分布', 'Atomic Charges')} ({schemes.map((s) => s.toUpperCase()).join(' / ')})
                  </div>
                  <div className="desc-table-wrap">
                    <table className="desc-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>{tr('元素', 'Elem')}</th>
                          {schemes.includes('mulliken') && <th>Mulliken</th>}
                          {hasSpin && <th>{tr('自旋密度', 'Spin')}</th>}
                          {schemes.includes('apt') && <th>APT</th>}
                          {schemes.includes('hirshfeld') && <th>Hirshfeld</th>}
                          {schemes.includes('cm5') && <th>CM5</th>}
                          {schemes.includes('npa') && <th>NPA</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {result.quantum.atom_charges.map((a) => {
                          const cell = (v?: number) => {
                            if (v === undefined) return <td>—</td>
                            const cls = v > 0.05 ? 'charge-pos' : v < -0.05 ? 'charge-neg' : ''
                            return <td className={`mono ${cls}`}>{v.toFixed(4)}</td>
                          }
                          return (
                            <tr key={a.index}>
                              <td className="mono">{a.index}</td>
                              <td><b>{a.element}</b></td>
                              {schemes.includes('mulliken') && cell(a.mulliken)}
                              {hasSpin && cell(a.mulliken_spin)}
                              {schemes.includes('apt') && cell(a.apt)}
                              {schemes.includes('hirshfeld') && cell(a.hirshfeld)}
                              {schemes.includes('cm5') && cell(a.cm5)}
                              {schemes.includes('npa') && cell(a.npa)}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {result.quantum && result.quantum.excited_states.length > 0 && (
                <div>
                  <div className="section-title">{tr('TD-DFT 激发态列表', 'TD-DFT Excited States')}</div>
                  <div className="desc-table-wrap">
                    <table className="desc-table">
                      <thead>
                        <tr>
                          <th>{tr('态', 'State')}</th>
                          <th>{tr('对称性/自旋', 'Symmetry')}</th>
                          <th>{tr('激发能 (eV)', 'Energy (eV)')}</th>
                          <th>{tr('波长 λ (nm)', 'λ (nm)')}</th>
                          <th>{tr('振子强度 f', 'Osc. f')}</th>
                          <th>&lt;S²&gt;</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.quantum.excited_states.map((es) => (
                          <tr key={es.state}>
                            <td className="mono">{es.state}</td>
                            <td>{es.symmetry}</td>
                            <td className="mono">{es.energy_ev.toFixed(4)}</td>
                            <td className="mono">{es.wavelength_nm.toFixed(2)}</td>
                            <td className="mono">{es.f.toFixed(4)}</td>
                            <td className="mono">{es.s2 !== null ? es.s2.toFixed(3) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {structureGroups.length > 0 && (
                <>
                  <div className="section-title">{tr('分子结构描述符 (RDKit 2D / 3D)', 'Structural Descriptors (RDKit 2D / 3D)')}</div>
                  <div className="desc-grid">{structureGroups.map(renderGroup)}</div>
                </>
              )}

              {result.structure?.all && (
                <details open={Boolean(q)}>
                  <summary className="section-title" style={{ cursor: 'pointer' }}>
                    {tr('全部 RDKit 2D 描述符', 'All RDKit 2D Descriptors')} ({allRdkitEntries.length} / {Object.keys(result.structure.all).length})
                  </summary>
                  <div className="desc-table-wrap" style={{ marginTop: 8 }}>
                    <table className="desc-table">
                      <thead>
                        <tr>
                          <th>{tr('描述符名称', 'Descriptor')}</th>
                          <th>{tr('数值', 'Value')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {allRdkitEntries.map(([k, v]) => (
                          <tr key={k}>
                            <td className="mono">{k}</td>
                            <td className="mono">{v === null || v === undefined ? '—' : v}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="desc-batch-grid">
            <div className="desc-card">
              <div className="desc-card-head">
                <span>{tr('已保存分子', 'Saved Molecules')} ({selMols.length}/{moleculeList.length})</span>
                <div className="row">
                  <button className="ghost sm" onClick={() => setSelMols(moleculeList.map((m) => m.id))}>{tr('全选', 'All')}</button>
                  <button className="ghost sm" onClick={() => setSelMols([])}>{tr('清空', 'Clear')}</button>
                </div>
              </div>
              <div className="desc-check-list">
                {moleculeList.length === 0 && <div className="muted">{tr('暂无已保存分子', 'No saved molecules')}</div>}
                {moleculeList.map((m) => (
                  <label key={m.id} className="desc-check-item">
                    <input
                      type="checkbox"
                      checked={selMols.includes(m.id)}
                      onChange={() => toggleId(selMols, m.id, setSelMols)}
                    />
                    <span className="ellipsis">{m.name || m.id}</span>
                    <span className="muted">{m.formula}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="desc-card">
              <div className="desc-card-head">
                <span>{tr('含日志的计算任务', 'Jobs with Logs')} ({selJobs.length}/{jobsWithLog.length})</span>
                <div className="row">
                  <button className="ghost sm" onClick={() => setSelJobs(jobsWithLog.map((j) => j.id))}>{tr('全选', 'All')}</button>
                  <button className="ghost sm" onClick={() => setSelJobs([])}>{tr('清空', 'Clear')}</button>
                </div>
              </div>
              <div className="desc-check-list">
                {jobsWithLog.length === 0 && <div className="muted">{tr('暂无带日志的任务', 'No jobs with logs')}</div>}
                {jobsWithLog.map((j) => (
                  <label key={j.id} className="desc-check-item">
                    <input
                      type="checkbox"
                      checked={selJobs.includes(j.id)}
                      onChange={() => toggleId(selJobs, j.id, setSelJobs)}
                    />
                    <span className="ellipsis">{j.molecule_name} · {j.spec_label}</span>
                    <span className={`badge ${j.status}`}>{j.status}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="desc-card">
              <div className="desc-card-head">
                <span>{tr('批量 SMILES 输入', 'Batch SMILES Input')}</span>
                <span className="muted">{tr('每行一条', 'One per line')}</span>
              </div>
              <div style={{ padding: 10 }}>
                <textarea
                  value={smilesText}
                  onChange={(e) => setSmilesText(e.target.value)}
                  rows={6}
                  style={{ width: '100%', fontFamily: 'var(--mono)', fontSize: 12 }}
                  placeholder={tr(
                    '支持格式:\nCCO,乙醇\nc1ccccc1,苯\nCC(=O)Oc1ccccc1C(=O)O,阿司匹林\ncaffeine CN1C=NC2=C1C(=O)N(C(=O)N2C)C',
                    'Supported formats:\nCCO,ethanol\nc1ccccc1,benzene\nCC(=O)Oc1ccccc1C(=O)O,aspirin\ncaffeine CN1C=NC2=C1C(=O)N(C(=O)N2C)C',
                  )}
                />
              </div>
            </div>
          </div>

          <div className="row" style={{ flexWrap: 'wrap', gap: 10 }}>
            <label className="row" style={{ fontSize: 12, color: 'var(--text-dim)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={batchAll}
                onChange={(e) => setBatchAll(e.target.checked)}
                style={{ width: 14, height: 14 }}
              />
              {tr('包含全部 RDKit 2D 描述符 (~217 列，适合 QSAR / 机器学习)', 'Include all RDKit 2D descriptors (~217 cols, ideal for QSAR / ML)')}
            </label>
            <div className="spacer" />
            <button className="primary" disabled={batchBusy} onClick={runBatch}>
              {batchBusy ? tr('提取中…', 'Extracting…') : tr('批量提取预览', 'Batch Preview')}
            </button>
            <button disabled={batchBusy} onClick={() => exportBatch('csv')}>
              {tr('导出 CSV (Excel/ML)', 'Export CSV (Excel/ML)')}
            </button>
            <button disabled={batchBusy} onClick={() => exportBatch('json')}>
              {tr('导出 JSON', 'Export JSON')}
            </button>
          </div>

          {batchErr && <div className="err-text">{batchErr}</div>}

          {batchRes && (
            <>
              <div className="row">
                <b>{tr('提取结果', 'Results')}</b>
                <span className="badge succeeded">{batchRes.count} {tr('条记录', 'rows')}</span>
                <span className="badge">{batchRes.columns.length} {tr('列特征', 'columns')}</span>
                {batchRes.errors.length > 0 && (
                  <span className="badge failed">{batchRes.errors.length} {tr('条失败', 'failed')}</span>
                )}
              </div>

              {batchRes.errors.length > 0 && (
                <div className="desc-warn">
                  {batchRes.errors.map((e, i) => (
                    <div key={i}>✕ {e.source}: {e.error}</div>
                  ))}
                </div>
              )}

              {batchRes.rows.length > 0 && (
                <div className="desc-table-wrap" style={{ maxHeight: 420 }}>
                  <table className="desc-table">
                    <thead>
                      <tr>
                        {batchRes.columns.slice(0, 40).map((col) => (
                          <th key={col}>{col}</th>
                        ))}
                        {batchRes.columns.length > 40 && (
                          <th>
                            {tr(
                              `… (+${batchRes.columns.length - 40} 列，请导出 CSV 查看全部)`,
                              `… (+${batchRes.columns.length - 40} more cols — export CSV for all)`,
                            )}
                          </th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {batchRes.rows.map((row, idx) => (
                        <tr key={idx}>
                          {batchRes.columns.slice(0, 40).map((col) => (
                            <td key={col} className="mono">
                              {formatValue((row[col] as DescriptorItem['value']) ?? null, isEn)}
                            </td>
                          ))}
                          {batchRes.columns.length > 40 && <td className="muted">…</td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
