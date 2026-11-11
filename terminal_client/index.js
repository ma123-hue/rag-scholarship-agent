/** 奖助学金申请评估 Agent 终端客户端。 */
import readline from 'node:readline/promises'
import { stdin as input, stdout as output } from 'node:process'

const BASE_URL = process.env.SCHOLARSHIP_AGENT_URL ?? 'http://127.0.0.1:8000'
const USERNAME = process.env.SCHOLARSHIP_AGENT_USER ?? 'admin'
const PASSWORD = process.env.SCHOLARSHIP_AGENT_PASSWORD ?? 'admin123456'

let token = ''
let sessionId = null
let pendingApproval = null

async function login() {
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  })
  if (!response.ok) throw new Error(`登录失败：HTTP ${response.status}`)
  const data = await response.json()
  token = data.access_token
}

function parseFrame(frame) {
  let namedEvent = ''
  const dataLines = []
  for (const line of frame.split('\n')) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) namedEvent = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (dataLines.length === 0) return null
  try {
    const data = JSON.parse(dataLines.join('\n'))
    return { type: data.type ?? namedEvent ?? 'message', ...data }
  } catch {
    return null
  }
}

function showEvent(event) {
  switch (event.type) {
    case 'session':
      sessionId = event.session_id
      console.log(`\n[会话 ${sessionId}]`)
      break
    case 'todo':
      console.log('\n  📋 任务计划')
      for (const item of event.items ?? []) {
        const mark = item.status === 'completed' ? '✓' : item.status === 'in_progress' ? '▶' : '○'
        console.log(`     ${mark} ${item.content ?? item.title ?? '未命名步骤'}`)
      }
      break
    case 'tool_call':
      console.log(`\n  ⚙ 调用 ${event.name} ${JSON.stringify(event.args)}`)
      break
    case 'tool_result':
      console.log(`  ✓ ${event.name || '工具'} 返回：${event.preview}`)
      break
    case 'approval_required':
      pendingApproval = event
      console.log('\n  ⚠ 操作等待人工审批')
      for (const action of event.actions ?? []) {
        console.log(`     工具：${action.name}`)
        console.log(`     说明：${action.description || '该操作会产生外部副作用'}`)
        console.log(`     参数：${JSON.stringify(action.args, null, 2)}`)
      }
      break
    case 'token':
      process.stdout.write(event.content ?? event.text ?? '')
      break
    case 'error':
      console.log(`\n  ✗ ${event.content ?? event.message ?? '未知错误'}`)
      break
    case 'end':
      console.log('\n')
      break
    default:
      break
  }
}

async function consumeResponse(response) {
  if (!response.ok || !response.body) throw new Error(`请求失败：HTTP ${response.status}`)

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r/g, '')
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const event = parseFrame(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      if (event) showEvent(event)
      boundary = buffer.indexOf('\n\n')
    }
  }
  buffer += decoder.decode()
  if (buffer.trim()) {
    const event = parseFrame(buffer.trim())
    if (event) showEvent(event)
  }
}

async function sendMessage(message) {
  const response = await fetch(`${BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  await consumeResponse(response)
}

async function resumeAgent(decisions) {
  const response = await fetch(`${BASE_URL}/api/chat/${sessionId}/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decisions }),
  })
  await consumeResponse(response)
}

async function loadPendingApproval() {
  const response = await fetch(`${BASE_URL}/api/chat/${sessionId}/pending-approval`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`读取审批状态失败：HTTP ${response.status}`)
  const data = await response.json()
  pendingApproval = data.approval
  if (pendingApproval) showEvent(pendingApproval)
}

async function handlePendingApproval(rl) {
  while (pendingApproval) {
    const approval = pendingApproval
    const choice = (await rl.question('审批 [a=批准 / e=修改 / r=拒绝] ▸ ')).trim().toLowerCase()
    let decisions
    if (choice === 'a') {
      decisions = (approval.actions ?? []).map(() => ({ type: 'approve' }))
    } else if (choice === 'r') {
      decisions = (approval.actions ?? []).map(() => ({
        type: 'reject',
        message: '用户在终端拒绝了文件写入操作',
      }))
    } else if (choice === 'e') {
      decisions = []
      try {
        for (const action of approval.actions ?? []) {
          const raw = await rl.question(`修改 ${action.name} 参数 JSON ▸ `)
          const editedArgs = JSON.parse(raw)
          if (!editedArgs || Array.isArray(editedArgs) || typeof editedArgs !== 'object') {
            throw new Error('参数必须是 JSON 对象')
          }
          decisions.push({ type: 'edit', edited_args: editedArgs })
        }
      } catch (error) {
        console.log(`参数无效：${error.message}`)
        continue
      }
    } else {
      console.log('请输入 a、e 或 r。')
      continue
    }

    pendingApproval = null
    try {
      await resumeAgent(decisions)
    } catch (error) {
      pendingApproval = approval
      throw error
    }
  }
}

async function main() {
  await login()
  console.log('奖助学金申请评估 Agent')
  console.log(`服务端：${BASE_URL}`)
  console.log('输入 /new 新建会话，/resume <会话ID> 恢复审批，/exit 退出\n')
  const rl = readline.createInterface({ input, output })
  while (true) {
    const line = (await rl.question('你 ▸ ')).trim()
    if (!line) continue
    if (line === '/exit' || line === 'exit' || line === 'quit') break
    if (line === '/new') {
      sessionId = null
      pendingApproval = null
      console.log('已新建会话。')
      continue
    }
    if (line.startsWith('/resume ')) {
      const requestedId = Number(line.slice(8).trim())
      if (!Number.isInteger(requestedId) || requestedId <= 0) {
        console.log('会话 ID 必须是正整数。')
        continue
      }
      sessionId = requestedId
      try {
        await loadPendingApproval()
        if (!pendingApproval) console.log('该会话没有待审批操作。')
        await handlePendingApproval(rl)
      } catch (error) {
        console.log(`恢复失败：${error.message}`)
      }
      continue
    }
    try {
      await sendMessage(line)
      await handlePendingApproval(rl)
    } catch (error) {
      console.log(`请求出错：${error.message}`)
    }
  }
  rl.close()
}

main().catch((error) => {
  console.error(`启动失败：${error.message}`)
  process.exitCode = 1
})
