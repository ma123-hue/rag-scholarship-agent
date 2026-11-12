<script setup>
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed } from 'vue'

import { exportDocx } from '../api/chat'
import { formatApiDate } from '../utils/time'

const md = new MarkdownIt({
  breaks: true,
  linkify: true,
})

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})
const emit = defineEmits(['approval'])
const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'

const score = computed(() => {
  const match = props.message.content.match(/资格匹配度：\s*(\d{1,3})%/)
  if (!match) {
    return null
  }
  return Number(match[1])
})

const renderedHtml = computed(() => {
  const content = props.message.content || ''
  const isStreaming = Boolean(props.message.streaming)
  const fenceCount = (content.match(/```/g) || []).length
  const previewContent = isStreaming && fenceCount % 2 === 1
    ? `${content}\n\`\`\``
    : content
  const html = md.render(previewContent)
  return DOMPurify.sanitize(html)
})

const formattedTime = computed(() => {
  return formatApiDate(props.message.timestamp, {
    hour: '2-digit',
    minute: '2-digit',
  })
})

const isAssistantDone = computed(() => {
  return props.message.role === 'assistant' && !props.message.streaming && Boolean(props.message.content)
})

let exporting = false

async function handleExportDocx() {
  if (exporting) return
  exporting = true
  try {
    const token = localStorage.getItem('scholar_token')
    if (!token) {
      ElMessage.error('登录已过期，请重新登录')
      return
    }
    await exportDocx(props.message.content, token)
    ElMessage.success('文档已下载')
  } catch (error) {
    ElMessage.error(error.message || '导出失败')
  } finally {
    exporting = false
  }
}

async function handleApproval(type) {
  const approval = props.message.approval
  if (!approval || approval.resolving) return
  const actions = approval.actions || []
  if (!actions.length) return

  if (type === 'approve') {
    emit('approval', props.message, actions.map(() => ({ type: 'approve' })))
    return
  }
  if (type === 'reject') {
    emit('approval', props.message, actions.map(() => ({
      type: 'reject',
      message: '用户在审批界面拒绝了文件写入操作',
    })))
    return
  }

  try {
    const decisions = []
    for (const action of actions) {
      const { value } = await ElMessageBox.prompt(
        `修改 ${action.name} 的参数（JSON）`,
        '修改后执行',
        {
          inputValue: JSON.stringify(action.args || {}, null, 2),
          inputType: 'textarea',
          confirmButtonText: '提交修改',
          cancelButtonText: '取消',
        },
      )
      const editedArgs = JSON.parse(value)
      if (!editedArgs || Array.isArray(editedArgs) || typeof editedArgs !== 'object') {
        throw new Error('参数必须是 JSON 对象')
      }
      decisions.push({ type: 'edit', edited_args: editedArgs })
    }
    emit('approval', props.message, decisions)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.message || '参数 JSON 格式不正确')
    }
  }
}
</script>

<template>
  <div class="message-row" :class="message.role">
    <div class="message-avatar">
      {{ message.role === 'user' ? '我' : 'AI' }}
    </div>
    <div class="message-bubble">
      <div class="message-headline">
        <span class="message-role">{{ message.role === 'user' ? '你' : '奖助学金顾问' }}</span>
        <span class="message-time">{{ formattedTime }}</span>
      </div>
      <div v-if="message.role === 'assistant' && score !== null" class="score-panel">
        <div class="score-topline">
          <span>资格匹配度</span>
          <strong>{{ score }}%</strong>
        </div>
        <el-progress
          :percentage="score"
          :stroke-width="10"
          :show-text="false"
          color="#2d6cdf"
        />
      </div>
      <details
        v-if="message.role === 'assistant' && ((message.todos && message.todos.length) || (message.agentEvents && message.agentEvents.length))"
        class="agent-trace"
      >
        <summary class="agent-trace-title">Agent 执行轨迹（点击展开）</summary>
        <div v-if="message.todos && message.todos.length" class="agent-todos">
          <div
            v-for="(todo, index) in message.todos"
            :key="`${index}-${todo.content || todo.title}`"
            class="agent-todo"
          >
            <span>{{ todo.status === 'completed' ? '✓' : todo.status === 'in_progress' ? '▶' : '○' }}</span>
            <span>{{ todo.content || todo.title || `步骤 ${index + 1}` }}</span>
          </div>
        </div>
        <div
          v-for="event in message.agentEvents || []"
          :key="event.id"
          class="agent-event"
          :class="event.type"
        >
          <template v-if="event.type === 'tool_call'">
            <strong>调用 {{ event.name }}</strong>
            <code>{{ JSON.stringify(event.args) }}</code>
          </template>
          <template v-else>
            <strong>{{ event.name || '工具' }} 已返回</strong>
            <span>{{ event.preview }}</span>
          </template>
        </div>
      </details>
      <div v-if="message.role === 'assistant' && message.approval" class="approval-panel">
        <div class="approval-title">⚠ 等待人工审批</div>
        <p>Agent 想执行会写入本地文件的操作。检查参数后再决定是否继续。</p>
        <div
          v-for="(action, index) in message.approval.actions || []"
          :key="`${action.name}-${index}`"
          class="approval-action"
        >
          <strong>{{ action.name }}</strong>
          <span>{{ action.description }}</span>
          <code>{{ JSON.stringify(action.args, null, 2) }}</code>
        </div>
        <div class="approval-buttons">
          <button :disabled="message.approval.resolving" class="approval-approve" @click="handleApproval('approve')">
            批准执行
          </button>
          <button :disabled="message.approval.resolving" @click="handleApproval('edit')">修改参数</button>
          <button :disabled="message.approval.resolving" class="approval-reject" @click="handleApproval('reject')">
            拒绝
          </button>
        </div>
        <span v-if="message.approval.resolving" class="approval-resolving">正在恢复 Agent 执行…</span>
      </div>
      <div
        class="markdown-body"
        :class="{ streaming: message.streaming }"
        v-html="renderedHtml"
      ></div>
      <div class="message-meta">
        <span v-if="message.streaming">生成中...</span>
        <button
          v-if="isAssistantDone"
          class="export-btn"
          @click="handleExportDocx"
        >
          {{ demoMode ? '📄 下载演示报告' : '📄 转成文档编辑' }}
        </button>
      </div>
    </div>
  </div>
</template>
