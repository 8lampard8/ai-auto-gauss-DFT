import { useStore } from './store'

export type Lang = 'zh' | 'en'

const STORAGE_KEY = 'aagd_lang'

export function loadInitialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'en' || saved === 'zh') return saved
  } catch {
    /* ignore */
  }
  return 'zh'
}

export function persistLang(lang: Lang): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    /* ignore */
  }
}

export function useT() {
  const lang = useStore((s) => s.lang)
  const setLang = useStore((s) => s.setLang)
  const tr = (zh: string, en: string) => (lang === 'en' ? en : zh)
  return { lang, setLang, tr }
}

export const GROUP_LABELS_EN: Record<string, string> = {
  calc: 'Calculation Info',
  energy: 'Energies',
  fmo: 'Frontier Molecular Orbitals (FMO)',
  cdft: 'Conceptual DFT Reactivity Indices (Koopmans)',
  electric: 'Electric Properties',
  thermo: 'Thermochemistry & Vibrations',
  excited: 'Excited States (TD-DFT)',
  basic: 'Basic Properties',
  druglike: 'Physicochemical / Drug-Likeness',
  topology: 'Topological Indices',
  shape3d: '3D Molecular Shape',
}

export const DESC_LABELS_EN: Record<string, string> = {
  // Quantum (Gaussian)
  program: 'Program',
  route: 'Route',
  stoichiometry: 'Stoichiometry',
  charge: 'Charge',
  multiplicity: 'Multiplicity',
  nbasis: 'Basis Functions',
  n_alpha: 'Alpha Electrons',
  n_beta: 'Beta Electrons',
  normal_termination: 'Normal Termination',
  elapsed_s: 'Elapsed Time',
  scf_method: 'SCF Method',
  scf_energy: 'SCF Electronic Energy',
  scf_energy_ev: 'SCF Electronic Energy',
  s2: '<S²>',
  excited_total_energy: 'Excited State Total Energy',
  homo: 'E(HOMO)',
  lumo: 'E(LUMO)',
  gap: 'HOMO-LUMO Gap',
  homo_1: 'E(HOMO-1)',
  lumo_1: 'E(LUMO+1)',
  beta_homo: 'β E(HOMO)',
  beta_lumo: 'β E(LUMO)',
  ip: 'Ionization Potential I = -E(HOMO)',
  ea: 'Electron Affinity A = -E(LUMO)',
  electronegativity: 'Electronegativity χ = (I+A)/2',
  chemical_potential: 'Chemical Potential μ = -χ',
  hardness: 'Chemical Hardness η = (I-A)/2',
  softness: 'Chemical Softness S = 1/(2η)',
  electrophilicity: 'Electrophilicity Index ω = μ²/(2η)',
  electrodonating: 'Electrodonating Power ω⁻',
  electroaccepting: 'Electroaccepting Power ω⁺',
  dipole: 'Dipole Moment',
  dipole_x: 'μx',
  dipole_y: 'μy',
  dipole_z: 'μz',
  polarizability_iso: 'Isotropic Polarizability α',
  polarizability_iso_ang3: 'Isotropic Polarizability α',
  polarizability_aniso: 'Polarizability Anisotropy Δα',
  q_scheme: 'Charge Scheme (Stats)',
  q_max: 'Max Atomic Charge q_max',
  q_min: 'Min Atomic Charge q_min',
  q_span: 'Charge Span Δq',
  zpe: 'Zero-Point Correction (ZPE)',
  zpe_kcal: 'Zero-Point Correction (ZPE)',
  corr_enthalpy: 'Thermal Correction to Enthalpy',
  corr_gibbs: 'Thermal Correction to Gibbs Free Energy',
  e_zpe: 'E + ZPE',
  enthalpy: 'Enthalpy H',
  gibbs: 'Gibbs Free Energy G',
  entropy_term: 'Entropy Term TS = H - G',
  temperature: 'Temperature',
  pressure: 'Pressure',
  n_imag: 'Imaginary Frequencies',
  lowest_freq: 'Lowest Frequency',
  n_freq: 'Vibrational Modes',
  s1_energy: 'First Excited State E(S1/T1)',
  s1_wavelength: 'First Excited State λ',
  s1_f: 'First Excited State Oscillator Strength f',
  max_f_state: 'Brightest State',
  max_f_wavelength: 'Absorption Maximum λmax',
  max_f: 'Max Oscillator Strength f',
  // RDKit Structure
  formula: 'Molecular Formula',
  canonical_smiles: 'Canonical SMILES',
  inchikey: 'InChIKey',
  inchi: 'InChI',
  mol_wt: 'Molecular Weight',
  exact_mass: 'Exact Mass (Monoisotopic)',
  n_atoms: 'Total Atoms (with H)',
  n_heavy_atoms: 'Heavy Atoms',
  n_heteroatoms: 'Heteroatoms',
  formal_charge: 'Formal Charge',
  n_valence_electrons: 'Valence Electrons',
  n_radical_electrons: 'Radical Electrons',
  n_bonds: 'Bonds (with H)',
  n_stereocenters: 'Stereocenters',
  logp: 'Partition Coefficient logP (Crippen)',
  mr: 'Molar Refractivity MR (Crippen)',
  tpsa: 'Topological Polar Surface Area (TPSA)',
  labute_asa: 'Labute Approx. Surface Area',
  hbd: 'H-Bond Donors (HBD)',
  hba: 'H-Bond Acceptors (HBA)',
  rot_bonds: 'Rotatable Bonds',
  n_rings: 'Ring Count',
  n_aromatic_rings: 'Aromatic Rings',
  fraction_csp3: 'Fraction sp³ Carbons (Fsp3)',
  qed: 'Drug-Likeness (QED)',
  lipinski_violations: 'Lipinski Ro5 Violations',
  veber_pass: 'Veber Rule Pass',
  max_partial_charge: 'Max Gasteiger Charge',
  min_partial_charge: 'Min Gasteiger Charge',
  bertz_ct: 'Bertz Complexity (BertzCT)',
  balaban_j: 'Balaban J Index',
  wiener: 'Wiener Index',
  hall_kier_alpha: 'Hall-Kier α',
  kappa1: 'Kappa-1 Shape Index',
  kappa2: 'Kappa-2 Shape Index',
  kappa3: 'Kappa-3 Shape Index',
  chi0v: 'Chi0v Connectivity',
  chi1v: 'Chi1v Connectivity',
  chi2v: 'Chi2v Connectivity',
  radius_of_gyration: 'Radius of Gyration Rg',
  pmi1: 'Principal Moment of Inertia I1',
  pmi2: 'Principal Moment of Inertia I2',
  pmi3: 'Principal Moment of Inertia I3',
  npr1: 'Normalized PMI Ratio NPR1',
  npr2: 'Normalized PMI Ratio NPR2',
  asphericity: 'Asphericity',
  eccentricity: 'Eccentricity',
  spherocity: 'Spherocity Index',
  inertial_shape_factor: 'Inertial Shape Factor',
  pbf: 'Plane of Best Fit (PBF)',
  vdw_volume: 'Molecular Volume (vdW grid)',
}

export const TASK_LABELS_EN: Record<string, string> = {
  opt: 'Geometry Optimization (OPT)',
  freq: 'Frequency Analysis (FREQ)',
  optfreq: 'Optimization + Frequency (OPT FREQ)',
  sp: 'Single-Point Energy (SP)',
  ts: 'Transition State (opt=ts)',
  qst2: 'QST2/QST3 Transition State',
  tddft: 'Excited States (TD-DFT)',
  irc: 'Intrinsic Reaction Coordinate (IRC)',
  scan: 'PES Scan (opt=modredundant)',
  nmr: 'NMR (GIAO)',
}

export const DESC_HINTS_EN: Record<string, string> = {
  s2: 'Open-shell spin contamination metric; ideal = S(S+1)',
  qed: '0–1, higher indicates greater drug-likeness',
  lipinski_violations: '≤1 generally considered orally bioavailable',
  npr1: 'NPR1/NPR2 PMI triangle: rod / disc / sphere',
  pbf: '0 indicates a perfectly planar molecule',
}

export const RECIPE_LABELS_EN: Record<string, string> = {
  homo: 'HOMO Orbital',
  lumo: 'LUMO Orbital',
  esp_vdw: 'ESP Isosurface',
  nci: 'NCI (RDG)',
  iri: 'IRI',
  igm: 'IGM',
  igmh: 'IGMH Non-Covalent Interactions',
}
