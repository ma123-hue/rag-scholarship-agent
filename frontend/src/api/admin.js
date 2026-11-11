import http from './http'

export function fetchPolicyFiles() {
  return http.get('/admin/files')
}

export function uploadPolicyFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  return http.post('/admin/files', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export function deletePolicyFile(fileId) {
  return http.delete(`/admin/files/${fileId}`)
}

export function rebuildKnowledgeBase() {
  return http.post('/admin/rebuild')
}
