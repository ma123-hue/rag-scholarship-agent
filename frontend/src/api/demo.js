import { buildRuleTrace, evaluateMessage } from '../demo/ruleEngine'

// 规则引擎版使用独立存储，避免旧版预设答案继续出现在历史会话中。
const STORAGE_KEY = 'scholar_demo_state_v2'
const ADMIN_STORAGE_KEY = 'scholar_admin_demo_state_v1'

const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))

function emptyState() {
  return { sessions: [], messages: {} }
}

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || emptyState()
  } catch {
    return emptyState()
  }
}

function saveState(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function titleFrom(message) {
  return message.replace(/\s+/g, ' ').slice(0, 22) || '奖助学金资格评估'
}

async function emitTokens(text, onEvent) {
  const chunks = text.match(/[\s\S]{1,90}/g) || []
  for (const content of chunks) {
    await onEvent({ type: 'token', content })
    await sleep(12)
  }
}

export function demoAuth(username = '体验用户', isAdmin = false) {
  return Promise.resolve({
    data: {
      access_token: 'demo-local-token',
      username: username.trim() || '体验用户',
      is_admin: isAdmin,
    },
  })
}

function defaultAdminState() {
  return {
    files: [
      { id: 1, original_filename: '太原理工大学本科生国家奖助学金管理办法.pdf', file_type: 'pdf', size_bytes: 1843200, uploaded_by: '系统管理员', created_at: '2026-09-01T08:30:00+08:00' },
      { id: 2, original_filename: '软件学院优秀学生奖学金评定实施办法.pdf', file_type: 'pdf', size_bytes: 962560, uploaded_by: '系统管理员', created_at: '2026-09-03T10:15:00+08:00' },
      { id: 3, original_filename: '家庭经济困难学生认定工作说明.docx', file_type: 'docx', size_bytes: 286720, uploaded_by: '政策运营', created_at: '2026-09-08T14:20:00+08:00' },
    ],
    lastRebuild: null,
  }
}

function loadAdminState() {
  try {
    return JSON.parse(localStorage.getItem(ADMIN_STORAGE_KEY)) || defaultAdminState()
  } catch {
    return defaultAdminState()
  }
}

function saveAdminState(state) {
  localStorage.setItem(ADMIN_STORAGE_KEY, JSON.stringify(state))
}

export async function demoFetchPolicyFiles() {
  await sleep(220)
  return { data: loadAdminState().files }
}

export async function demoUploadPolicyFile(file) {
  await sleep(500)
  const state = loadAdminState()
  const extension = file.name.split('.').pop()?.toLowerCase() || 'txt'
  const created = {
    id: Date.now(),
    original_filename: file.name,
    file_type: extension,
    size_bytes: file.size,
    uploaded_by: '演示管理员',
    created_at: new Date().toISOString(),
  }
  state.files.unshift(created)
  saveAdminState(state)
  return { data: created }
}

export async function demoDeletePolicyFile(fileId) {
  await sleep(320)
  const state = loadAdminState()
  state.files = state.files.filter((item) => item.id !== fileId)
  saveAdminState(state)
  return { data: { ok: true } }
}

export async function demoRebuildKnowledgeBase() {
  await sleep(1100)
  const state = loadAdminState()
  const documentCount = state.files.length
  const chunkCount = state.files.reduce((total, file) => total + Math.max(8, Math.round(file.size_bytes / 7200)), 0)
  state.lastRebuild = new Date().toISOString()
  saveAdminState(state)
  return { data: { document_count: documentCount, chunk_count: chunkCount, completed_at: state.lastRebuild } }
}

export function demoFetchSessions() {
  const state = loadState()
  return Promise.resolve({ data: [...state.sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at)) })
}

export function demoFetchMessages(sessionId) {
  return Promise.resolve({ data: loadState().messages[sessionId] || [] })
}

export function demoRemoveSession(sessionId) {
  const state = loadState()
  state.sessions = state.sessions.filter((item) => item.id !== sessionId)
  delete state.messages[sessionId]
  saveState(state)
  return Promise.resolve({ data: { ok: true } })
}

export function demoPendingApproval() {
  return Promise.resolve({ data: { pending: false, approval: null } })
}

export async function demoStreamChat({ sessionId, message, onEvent }) {
  const state = loadState()
  const id = sessionId ?? Date.now()
  const timestamp = new Date().toISOString()
  let session = state.sessions.find((item) => item.id === id)
  if (!session) {
    session = { id, session_title: titleFrom(message), created_at: timestamp, updated_at: timestamp }
    state.sessions.unshift(session)
  }
  session.updated_at = timestamp
  await onEvent({ type: 'session', session_id: id, session_title: session.session_title })
  await sleep(180)

  const approvalRequested = /报告|保存|导出/.test(message)
  const evaluation = approvalRequested ? null : evaluateMessage(message)
  const scenario = approvalRequested
    ? { approval: true, answer: '', suggestions: [] }
    : { approval: false, answer: evaluation.answer, suggestions: evaluation.suggestions }
  const events = approvalRequested
    ? buildRuleTrace(message, evaluateMessage('请评估我可以申请哪些奖助学金'))
    : buildRuleTrace(message, evaluation)
  for (const event of events) {
    await onEvent(event)
    await sleep(event.type === 'todo' ? 260 : 180)
  }

  const assistantMessage = {
    id: `a-${Date.now()}`,
    role: 'assistant',
    content: scenario.answer,
    timestamp,
    suggestions: scenario.suggestions,
    agentEvents: events.filter((event) => event.type.startsWith('tool_')),
    todos: events.find((event) => event.type === 'todo')?.items || [],
    streaming: false,
  }
  state.messages[id] = [
    ...(state.messages[id] || []),
    { id: `u-${Date.now()}`, role: 'user', content: message, timestamp },
    assistantMessage,
  ]

  if (scenario.approval) {
    await onEvent({
      type: 'approval_required',
      actions: [{
        name: 'save_application_report',
        description: '将当前评估结果保存为 Markdown 申请报告',
        args: { filename: '奖助学金申请评估报告.md' },
      }],
    })
    saveState(state)
  } else {
    await emitTokens(scenario.answer, onEvent)
    // 在 end 事件触发界面刷新历史会话之前先完成本地持久化。
    saveState(state)
    await onEvent({ type: 'suggestions', items: scenario.suggestions })
    await onEvent({ type: 'end' })
  }
}

export async function demoResumeChat({ sessionId, decisions, onEvent }) {
  const approved = decisions.some((item) => item.type === 'approve' || item.type === 'edit')
  await onEvent({ type: 'session', session_id: sessionId })
  if (approved) {
    await onEvent({ type: 'tool_call', name: 'save_application_report', args: { filename: '奖助学金申请评估报告.md' } })
    await sleep(240)
    await onEvent({ type: 'tool_result', name: 'save_application_report', preview: '演示报告已在浏览器本地生成，不会上传任何个人信息。' })
    await emitTokens('\n\n✅ 已完成审批演示。真实系统会在用户批准后生成报告文件；当前免费演示版不会向服务器写入数据。', onEvent)
  } else {
    await emitTokens('\n\n已拒绝保存报告，本次操作没有产生任何文件。', onEvent)
  }
  await onEvent({ type: 'end' })
}

export function demoExport(content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'scholarship-demo-report.md'
  anchor.click()
  URL.revokeObjectURL(url)
}
