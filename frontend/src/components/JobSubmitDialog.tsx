import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { useT } from '../i18n'
import type { Job, SshProfile } from '../types'

interface LocalRes {
  nproc: number
  mem_mb: number
  mem_human: string
  ram_total_gb: number
  cpu_count: number
}

const EMPTY_PROFILE: SshProfile = {
  id: '',
  name: '',
  host: '',
  port: 22,
  user: '',
  key_path: '',
  password: '',
  gaussian_path: 'g16',
  scratch_dir: '$HOME/gaussian_jobs',
}

export function JobSubmitDialog() {
  const open = useStore((s) => s.jobSubmitOpen)
  const close = () => useStore.getState().setJobSubmitOpen(false)
  const molecule = useStore((s) => s.currentMolecule)
  const spec = useStore((s) => s.pendingSpec)
  const gjf = useStore((s) => s.currentGjf)
  const refreshJobs = useStore((s) => s.refreshJobs)
  const setActiveView = useStore((s) => s.setActiveView)
  const { tr } = useT()

  const [kind, setKind] = useState<'local' | 'ssh'>('local')
  const [nproc, setNproc] = useState(4)
  const [mem, setMem] = useState('8GB')
  const [localRes, setLocalRes] = useState<LocalRes | null>(null)
  const [profiles, setProfiles] = useState<SshProfile[]>([])
  const [profileId, setProfileId] = useState('')
  const [showProfileForm, setShowProfileForm] = useState(false)
  const [newProfile, setNewProfile] = useState<SshProfile>(EMPTY_PROFILE)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setErr('')
    api.get<LocalRes>('/system/local-resources').then((r) => {
      setLocalRes(r)
      setNproc(r.nproc)
      setMem(r.mem_human)
    }).catch(() => {})
    api.get<{ ssh_profiles: SshProfile[] }>('/jobs/ssh-profiles').then((r) => {
      setProfiles(r.ssh_profiles)
      if (r.ssh_profiles[0]) setProfileId(r.ssh_profiles[0].id)
    }).catch(() => {})
  }, [open])

  if (!open) return null

  const addProfile = async () => {
    setErr('')
    if (!newProfile.id || !newProfile.host || !newProfile.user) {
      setErr(tr('SSH 节点需要 id / host / user', 'SSH profile requires id, host, and user'))
      return
    }
    try {
      const r = await api.post<{ ssh_profiles: SshProfile[] }>(
        '/jobs/ssh-profiles',
        newProfile,
      )
      setProfiles(r.ssh_profiles)
      setProfileId(newProfile.id)
      setNewProfile(EMPTY_PROFILE)
      setShowProfileForm(false)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const submit = async () => {
    if (!molecule || !spec) {
      setErr(tr('缺少分子或方法(请先在 gjf 编辑器中生成)', 'Missing molecule or method (generate a .gjf first)'))
      return
    }
    if (kind === 'ssh' && !profileId) {
      setErr(tr('请选择 SSH 节点(或新增一个)', 'Select or add an SSH profile'))
      return
    }
    setBusy(true)
    setErr('')
    try {
      await api.post<Job>('/jobs', {
        molecule_id: molecule.id,
        kind,
        spec,
        ssh_profile_id: kind === 'ssh' ? profileId : '',
        nproc,
        mem,
        gjf: gjf || '',
      })
      await refreshJobs()
      setActiveView('jobs')
      close()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="overlay" onClick={close}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          {tr('提交任务', 'Submit Job')}
          <div className="spacer" />
          <button className="ghost" onClick={close}>✕</button>
        </div>
        <div className="modal-body">
          <div className="row">
            <span className="muted">{tr('分子:', 'Molecule:')}</span>
            <b>{molecule?.name || tr('(未选)', '(none)')}</b>
            <span className="spacer" />
            <span className="muted">{tr('方法:', 'Method:')}</span>
            <b>{spec?.label || `${spec?.functional}/${spec?.basis}` || tr('(未设)', '(unset)')}</b>
          </div>

          <div className="row">
            <button className={kind === 'local' ? 'primary' : 'ghost'} onClick={() => setKind('local')}>
              {tr('本地执行', 'Local')}
            </button>
            <button className={kind === 'ssh' ? 'primary' : 'ghost'} onClick={() => setKind('ssh')}>
              {tr('SSH 远程', 'Remote SSH')}
            </button>
          </div>

          {kind === 'local' ? (
            <div className="form-grid">
              <label className="field">
                <span className="lbl">%nprocshared</span>
                <input type="number" value={nproc} onChange={(e) => setNproc(parseInt(e.target.value) || 1)} />
              </label>
              <label className="field">
                <span className="lbl">%mem</span>
                <input value={mem} onChange={(e) => setMem(e.target.value)} />
              </label>
              {localRes && (
                <div className="muted" style={{ gridColumn: '1 / -1' }}>
                  {tr(
                    `本机:${localRes.cpu_count} 核 / ${localRes.ram_total_gb}GB (建议 nproc=${localRes.nproc}, mem=${localRes.mem_human})`,
                    `Host: ${localRes.cpu_count} cores / ${localRes.ram_total_gb}GB RAM (suggested nproc=${localRes.nproc}, mem=${localRes.mem_human})`,
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="form-grid">
              <label className="field" style={{ gridColumn: '1 / -1' }}>
                <span className="lbl">{tr('SSH 节点', 'SSH Host')}</span>
                <div className="row">
                  <select value={profileId} onChange={(e) => setProfileId(e.target.value)} style={{ flex: 1 }}>
                    {profiles.length === 0 && <option value="">{tr('(无,请新增)', '(none, add one)')}</option>}
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name || p.id} ({p.user}@{p.host})
                      </option>
                    ))}
                  </select>
                  <button className="ghost sm" onClick={() => setShowProfileForm(!showProfileForm)}>
                    {showProfileForm ? tr('取消', 'Cancel') : tr('新增节点', 'Add Host')}
                  </button>
                </div>
              </label>
              {showProfileForm && (
                <>
                  <label className="field"><span className="lbl">ID</span><input value={newProfile.id} onChange={(e) => setNewProfile({ ...newProfile, id: e.target.value })} placeholder="node1" /></label>
                  <label className="field"><span className="lbl">{tr('名称', 'Name')}</span><input value={newProfile.name} onChange={(e) => setNewProfile({ ...newProfile, name: e.target.value })} /></label>
                  <label className="field"><span className="lbl">Host</span><input value={newProfile.host} onChange={(e) => setNewProfile({ ...newProfile, host: e.target.value })} placeholder="10.0.0.1" /></label>
                  <label className="field"><span className="lbl">User</span><input value={newProfile.user} onChange={(e) => setNewProfile({ ...newProfile, user: e.target.value })} /></label>
                  <label className="field"><span className="lbl">{tr('密钥路径(优先)', 'Key path (preferred)')}</span><input value={newProfile.key_path} onChange={(e) => setNewProfile({ ...newProfile, key_path: e.target.value })} placeholder="~/.ssh/id_rsa" /></label>
                  <label className="field"><span className="lbl">{tr('或密码', 'or Password')}</span><input type="password" value={newProfile.password} onChange={(e) => setNewProfile({ ...newProfile, password: e.target.value })} /></label>
                  <label className="field"><span className="lbl">{tr('g16 路径', 'g16 path')}</span><input value={newProfile.gaussian_path} onChange={(e) => setNewProfile({ ...newProfile, gaussian_path: e.target.value })} /></label>
                  <label className="field"><span className="lbl">{tr('远程 scratch 目录', 'Remote scratch dir')}</span><input value={newProfile.scratch_dir} onChange={(e) => setNewProfile({ ...newProfile, scratch_dir: e.target.value })} /></label>
                  <div className="row" style={{ gridColumn: '1 / -1' }}>
                    <button onClick={addProfile}>{tr('保存节点', 'Save Host')}</button>
                  </div>
                </>
              )}
              <label className="field"><span className="lbl">%nprocshared</span><input type="number" value={nproc} onChange={(e) => setNproc(parseInt(e.target.value) || 1)} /></label>
              <label className="field"><span className="lbl">%mem</span><input value={mem} onChange={(e) => setMem(e.target.value)} /></label>
            </div>
          )}

          {err && <div className="err-text">{err}</div>}
          {gjf ? (
            <div className="ok-text" style={{ background: 'var(--accent-soft)', padding: '8px 10px', borderRadius: 8 }}>
              {tr(
                '✓ 将使用你在编辑器中修改后的 gjf 提交(%nprocshared / %mem 以 gjf 内容为准,不再用推荐设置重生成)。',
                '✓ Submitting your edited .gjf verbatim (%nprocshared / %mem taken from the .gjf).',
              )}
            </div>
          ) : (
            <div className="muted">{tr('未提供已编辑 gjf,将按推荐设置(spec)生成 gjf 提交。', 'No edited .gjf; will generate one from spec.')}</div>
          )}
          <div className="row">
            <button className="primary" onClick={submit} disabled={busy}>
              {busy ? tr('提交中…', 'Submitting…') : tr('一键提交', 'Submit')}
            </button>
            <span className="muted">
              {kind === 'local'
                ? tr('未配置 Gaussian 时将生成 gjf 但不执行(可下载)', 'If Gaussian is not configured, generates .gjf only (downloadable)')
                : tr('将 SSH 连接节点,nohup 提交并轮询,完成后回传 log/fchk', 'Submits over SSH via nohup, polls status, and fetches log/fchk')}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
