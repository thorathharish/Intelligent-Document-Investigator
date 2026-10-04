import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, postJson } from './client'
import type { DocumentInfo, Investigation, RunResult, UploadResult } from './types'

const IN_PROGRESS = new Set(['queued', 'extracting', 'indexing'])

export function useCreateInvestigation() {
  return useMutation({
    mutationFn: (title: string) => postJson<Investigation>('/investigations', { title }),
  })
}

export function useSeedDemo() {
  return useMutation({
    mutationFn: (set: 'A' | 'B') => postJson<Investigation>('/demo/seed', { set }),
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

export function useRuns(id: string) {
  return useQuery({ queryKey: ['runs', id], queryFn: () => api<RunResult[]>(`/investigations/${id}/runs`) })
}

export function useAskQuestion(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (question: string) => postJson<RunResult>(`/investigations/${id}/questions`, { question }),
    // a cache hit returns the stored run (same run_id): update it in place instead of adding a second card
    onSuccess: (run) =>
      queryClient.setQueryData<RunResult[]>(['runs', id], (previous = []) =>
        previous.some((r) => r.run_id === run.run_id)
          ? previous.map((r) => (r.run_id === run.run_id ? run : r))
          : [...previous, run],
      ),
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
