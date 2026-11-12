import http from './http'
import {
  demoExport,
  demoFetchMessages,
  demoFetchSessions,
  demoPendingApproval,
  demoRemoveSession,
  demoResumeChat,
  demoStreamChat,
} from './demo'

const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'

export async function exportDocx(content, token) {
  if (demoMode) {
    demoExport(content)
    return
  }
  const response = await fetch('/api/chat/export-docx', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  })

  if (!response.ok) {
    let detail = '导出失败'
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      detail = response.statusText || detail
    }
    throw new Error(detail)
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'scholarship-advice.docx'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function fetchSessions() {
  if (demoMode) return demoFetchSessions()
  return http.get('/sessions')
}

export function fetchSessionMessages(sessionId) {
  if (demoMode) return demoFetchMessages(sessionId)
  return http.get(`/sessions/${sessionId}/messages`)
}

export function removeSession(sessionId) {
  if (demoMode) return demoRemoveSession(sessionId)
  return http.delete(`/sessions/${sessionId}`)
}

export function fetchPendingApproval(sessionId) {
  if (demoMode) return demoPendingApproval(sessionId)
  return http.get(`/chat/${sessionId}/pending-approval`)
}

async function consumeSseBuffer(buffer, onEvent) {
  const events = buffer.split('\n\n')
  const rest = events.pop() || ''

  for (const event of events) {
    const lines = event.split('\n')
    for (const line of lines) {
      if (!line.startsWith('data: ')) {
        continue
      }
      const payload = JSON.parse(line.slice(6))
      await onEvent(payload)
    }
  }

  return rest
}

export async function streamChat({ token, sessionId, message, onEvent }) {
  if (demoMode) return demoStreamChat({ sessionId, message, onEvent })
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      session_id: sessionId ?? undefined,
      message,
    }),
  })

  if (!response.ok) {
    let detail = '请求失败'
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      detail = response.statusText || detail
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    buffer = await consumeSseBuffer(buffer, onEvent)
  }

  buffer += decoder.decode()
  buffer = await consumeSseBuffer(buffer, onEvent)

  if (buffer.trim().startsWith('data: ')) {
    const payload = JSON.parse(buffer.trim().slice(6))
    await onEvent(payload)
  }
}

export async function resumeChat({ token, sessionId, decisions, onEvent }) {
  if (demoMode) return demoResumeChat({ sessionId, decisions, onEvent })
  const response = await fetch(`/api/chat/${sessionId}/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decisions }),
  })

  if (!response.ok) {
    let detail = '恢复 Agent 执行失败'
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      detail = response.statusText || detail
    }
    throw new Error(detail)
  }
  if (!response.body) throw new Error('浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = await consumeSseBuffer(buffer, onEvent)
  }
  buffer += decoder.decode()
  buffer = await consumeSseBuffer(buffer, onEvent)
  if (buffer.trim().startsWith('data: ')) {
    await onEvent(JSON.parse(buffer.trim().slice(6)))
  }
}
