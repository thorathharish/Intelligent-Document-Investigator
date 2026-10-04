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

export interface ApiError {
  code: string
  message: string
}
