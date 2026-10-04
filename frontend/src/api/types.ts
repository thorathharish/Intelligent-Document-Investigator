export type DocumentStatus = 'queued' | 'extracting' | 'indexing' | 'ready' | 'failed' | 'duplicate'

export interface DocumentInfo {
  id: string
  filename: string
  ext: string
  status: DocumentStatus
  error_message: string | null
  page_count: number | null
  extraction_method: 'text' | 'ocr' | 'mixed' | null
  chunk_count: number
}

export interface RunSummary {
  id: string
  question: string
  state: string
  created_at: string
}

export interface Investigation {
  id: string
  title: string
  created_at: string
  documents: DocumentInfo[]
  runs: RunSummary[]
}

export interface UploadResult {
  accepted: DocumentInfo[]
  rejected: { filename: string; reason: string }[]
}

export type EvidenceState = 'HIGH' | 'MEDIUM' | 'LOW' | 'CONFLICT' | 'INSUFFICIENT'

export interface Evidence {
  chunk_id: string
  document_id: string
  document: string
  page: number | null
  section: string | null
  paragraph: number
  quote: string
  extraction_method: 'text' | 'ocr'
  ocr_quality: 'good' | 'low' | null
}

export interface Claim {
  id: string
  citation: number
  aspect_id: string
  value: string
  value_type: string
  position_key: string | null
  scope: string | null
  explicit: boolean
  evidence: Evidence
}

export interface AnswerSentence {
  text: string
  claim_ids: string[]
}

export interface Aspect {
  id: string
  label: string
  status: 'consistent' | 'conflict' | 'complementary' | 'uncovered'
  basis: 'typed' | 'text'
  positions: { key: string; display: string; claim_ids: string[]; document_ids: string[] }[]
  notes: { text: string; evidence: Evidence }[]
}

export interface RunResult {
  run_id: string
  investigation_id: string
  question: string
  created_at: string
  state: EvidenceState
  headline: string
  degraded: boolean
  cached: boolean
  answer: AnswerSentence[]
  aspects: Aspect[]
  claims: Claim[]
  signals: Record<string, number | boolean>
  reasons: string[]
  related: Evidence[]
  warnings: string[]
}

export interface ApiError {
  code: string
  message: string
}
