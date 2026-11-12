const STORAGE_KEY = 'scholar_demo_state_v1'

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

function buildScenario(message) {
  const asksReport = /报告|保存|导出/.test(message)
  if (asksReport) {
    return {
      approval: true,
      answer: '',
      suggestions: [],
    }
  }

  if (/困难|贫困|收入|助学金|低保/.test(message)) {
    return {
      score: 91,
      answer: `## 评估结论

根据你提供的家庭年收入、困难证明和综测情况，**建议优先申请国家励志奖学金与国家助学金**。当前资格匹配度：91%。

### 条件比对

- ✅ 已提供家庭经济困难相关证明，符合困难认定的核心材料要求。
- ✅ 综合测评位于前 20%，具备较好的学业与综合表现。
- ⚠️ 国家励志奖学金通常还要求上一学年无不及格课程，需要补充确认。
- ⚠️ 助学金档次需结合学校当年度困难认定结果，系统不能仅依据收入直接确定。

### 建议准备的材料

1. 家庭经济困难学生认定申请表；
2. 困难证明或低保证明复印件；
3. 上一学年成绩单与综合测评证明；
4. 个人情况说明及诚信承诺。

> 政策依据：学校国家奖助学金管理办法、软件学院家庭经济困难学生认定工作安排。最终结果以学校当年度通知和学院审核为准。`,
      suggestions: ['国家励志奖学金还需要满足哪些成绩条件？', '帮我整理一份材料检查清单', '生成这次评估的申请报告'],
    }
  }

  if (/国家奖学金|三好|竞赛|排名|绩点/.test(message)) {
    return {
      score: 86,
      answer: `## 评估结论

你的学业表现和荣誉经历较有竞争力，**可以进入国家奖学金重点准备名单**。当前资格匹配度：86%。

### 政策条件逐项比对

- ✅ 绩点与专业排名表现突出，满足“学习成绩优异”的方向性要求。
- ✅ 校级三好学生和竞赛奖项可作为综合素质与突出表现佐证。
- ⚠️ 尚未确认上一学年是否存在不及格课程或纪律处分。
- ⚠️ 国家奖学金名额有限，达到基础条件不等于最终获奖，还需参加学院排序与答辩。

### 申请策略

1. 将竞赛奖项按国家级、省级、校级分层，并核对学校竞赛评级目录；
2. 准备成绩排名、综测排名和无违纪证明；
3. 用“问题—行动—量化结果”结构撰写主要事迹；
4. 同步评估校级优秀学生奖学金，形成主申与备选方案。

> 政策依据：本科生国家奖助学金管理办法、优秀学生奖学金评定实施办法、大学生竞赛评级目录。最终资格以当年度通知为准。`,
      suggestions: ['竞赛奖项在评审中如何分级？', '还缺哪些信息才能提高判断准确度？', '生成这次评估的申请报告'],
    }
  }

  return {
    score: 64,
    answer: `## 初步判断

我已经建立了基础学生画像，但信息不足以完成可靠的政策比对。当前资格匹配度：64%。

请继续补充以下信息：

- 所在学院、专业与年级；
- 上一学年绩点、专业排名和综合测评排名；
- 是否有不及格课程或纪律处分；
- 家庭经济困难认定情况；
- 竞赛、荣誉、志愿服务和社会实践经历；
- 想申请的具体奖学金或助学金名称。

系统会坚持把条件区分为“已满足、明确不满足、信息缺失”，不会把未提供的信息自行推断为符合。`,
    suggestions: ['我应该优先申请哪类奖助学金？', '列出国家奖学金需要补充的信息', '家庭经济困难认定需要什么材料？'],
  }
}

function traceFor(message) {
  return [
    { type: 'todo', items: [
      { content: '提取学生画像与申请目标', status: 'completed' },
      { content: '检索相关奖助学金政策', status: 'completed' },
      { content: '逐项比较资格条件', status: 'completed' },
      { content: '生成材料清单与申请建议', status: 'completed' },
    ] },
    { type: 'tool_call', name: 'extract_student_profile', args: { query: message } },
    { type: 'tool_result', name: 'extract_student_profile', preview: '已提取年级、成绩排名、家庭情况与荣誉经历等明确事实。' },
    { type: 'tool_call', name: 'search_scholarship_policy', args: { query: '奖助学金申请条件与评定办法', top_k: 4 } },
    { type: 'tool_result', name: 'search_scholarship_policy', preview: '命中 4 条政策片段，来源包括国家奖助学金管理办法与学院评定细则。' },
    { type: 'tool_call', name: 'compare_profile_with_policy', args: { strict_missing: true } },
    { type: 'tool_result', name: 'compare_profile_with_policy', preview: '已区分满足项、风险项和待补充信息，未对缺失信息作推断。' },
  ]
}

async function emitTokens(text, onEvent) {
  const chunks = text.match(/[\s\S]{1,90}/g) || []
  for (const content of chunks) {
    await onEvent({ type: 'token', content })
    await sleep(12)
  }
}

export function demoAuth(username = '体验用户') {
  return Promise.resolve({
    data: {
      access_token: 'demo-local-token',
      username: username.trim() || '体验用户',
      is_admin: false,
    },
  })
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

  const scenario = buildScenario(message)
  const events = traceFor(message)
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
