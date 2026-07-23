export type ProviderKind = 'openai' | 'anthropic' | 'custom' | 'mock'

export interface SystemInfo {
  platform: string
  python: string
  cpu_count: number
  cpu_count_logical: number
  cpu_freq_mhz: number | null
  ram_total_gb: number
  ram_available_gb: number
}

export interface ProviderConfig {
  id: string
  name: string
  kind: ProviderKind
  base_url: string
  api_key: string // masked when coming from the backend
  models: string[]
  default_model: string
}

export interface Settings {
  gaussian_path: string
  multiwfn_path: string
  vmd_path: string
  active_provider_id: string
  active_model: string
  providers: ProviderConfig[]
  ssh_profiles: unknown[]
}

export interface Catalog {
  presets: Partial<ProviderConfig>[]
  functionals: string[]
  bases: string[]
  tasks: { id: string; label: string }[]
  solvents: string[]
  plots: Record<
    string,
    { label: string; needs: string[]; multiwfn: string; vmd: string }
  >
}

export interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
}

export interface SseEvent {
  type: 'delta' | 'done' | 'error' | 'molecule' | 'search'
  content?: string
  message?: string
  molecule?: Molecule
  query?: string
  count?: number
  results?: { title: string; url: string }[]
}

export interface Atom {
  element: string
  x: number
  y: number
  z: number
}

export interface Bond {
  a1: number
  a2: number
  order: number
}

export interface Molecule {
  id: string
  name: string
  source: string
  charge: number
  multiplicity: number
  atoms: Atom[]
  bonds: Bond[]
  smiles: string
  molblock: string
  xyz: string
  route: string
  title: string
  created_at: string
}

export interface MoleculeSummary {
  id: string
  name: string
  source: string
  formula: string
  natoms: number
  charge: number
  multiplicity: number
}

export type ImportSource =
  | 'smiles'
  | 'mol'
  | 'mol2'
  | 'gjf'
  | 'out'
  | 'cdxml'
  | 'image'

export interface MethodSpec {
  functional: string
  basis: string
  route: string
  dispersion: string
  scrf: string
  extra: string
  charge: number
  multiplicity: number
  memory: string
  nproc: number
  title: string
  label: string
  explanation: string
}

export interface Job {
  id: string
  status: string
  kind: 'local' | 'ssh'
  molecule_id: string
  molecule_name: string
  spec_label: string
  gjf_path: string
  log_path: string
  fchk_path: string
  remote_host: string
  remote_pid: string
  created_at: string
  updated_at: string
  message: string
  error: string
  nproc: number
  mem: string
  ssh_profile_id: string
}

export interface SshProfile {
  id: string
  name: string
  host: string
  port: number
  user: string
  key_path: string
  password: string
  gaussian_path: string
  scratch_dir: string
}

export interface Recipe {
  label: string
  needs: string[]
  multiwfn_input: string[]
  multiwfn_note: string
  vmd_script: string
  instructions: string
  cubes: string[]
}

export interface VisualizeResult {
  run_id: string
  recipe: string
  multiwfn_log: string
  vmd_log: string
  cubes: string[]
  image_url: string | null
  instructions: string
  vmd_out_dir: string
}
