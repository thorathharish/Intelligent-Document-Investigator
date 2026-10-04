import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, postJson } from './client'
import type { DocumentInfo, Investigation, UploadResult } from './types'

const IN_PROGRESS = new Set(['queued', 'extracting', 'indexing'])

export function useCreateInvestigation() {
  return useMutation({
    mutationFn: (title: string) => postJson<Investigation>('/investigations', { title }),
  })
}

export function useInvestigation(id: string) {
  return useQuery({ queryKey: ['investigation', id], queryFn: () => api<Investigation>(`/investigations/${id}`) })
}

export function useDocuments(id: string) {
  return useQuery({
    queryKey: ['documents', id],
    queryFn: () => api<DocumentInfo[]>(`/investigations/${id}/documents`),
    // poll once a second while any document is still being processed
    refetchInterval: (query) => (query.state.data?.some((d) => IN_PROGRESS.has(d.status)) ? 1000 : false),
  })
}

export function useUploadDocuments(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      files.forEach((file) => form.append('files', file))
      return api<UploadResult>(`/investigations/${id}/documents`, { method: 'POST', body: form })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents', id] }),
  })
}
