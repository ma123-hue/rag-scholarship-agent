import http from './http'
import {
  demoDeletePolicyFile,
  demoFetchPolicyFiles,
  demoRebuildKnowledgeBase,
  demoUploadPolicyFile,
} from './demo'

const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'

export function fetchPolicyFiles() {
  if (demoMode) return demoFetchPolicyFiles()
  return http.get('/admin/files')
}

export function uploadPolicyFile(file) {
  if (demoMode) return demoUploadPolicyFile(file)
  const formData = new FormData()
  formData.append('file', file)
  return http.post('/admin/files', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export function deletePolicyFile(fileId) {
  if (demoMode) return demoDeletePolicyFile(fileId)
  return http.delete(`/admin/files/${fileId}`)
}

export function rebuildKnowledgeBase() {
  if (demoMode) return demoRebuildKnowledgeBase()
  return http.post('/admin/rebuild')
}
