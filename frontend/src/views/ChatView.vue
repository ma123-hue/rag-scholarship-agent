<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import ChatBubble from '../components/ChatBubble.vue'
import ChatComposer from '../components/ChatComposer.vue'
import FollowUpSuggestions from '../components/FollowUpSuggestions.vue'
import SessionSidebar from '../components/SessionSidebar.vue'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const authStore = useAuthStore()
const chatStore = useChatStore()
const router = useRouter()
const scrollContainer = ref(null)
const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'

const messages = computed(() => chatStore.activeMessages)
const suggestionPrompts = [
  '我是中国籍大二全日制本科生，专业排名前8%，综测排名前9%，无挂科无处分，已按时注册，诚实守信，有国家级竞赛获奖，请评估国家奖学金。',
  '我是大三全日制本科生，有贫困证明，专业排名前30%，综测前10%，无挂科，请评估国家励志奖学金。',
  '我是软件学院大二全日制本科生，专业排名前18%，获得3项优秀个人荣誉称号，无挂科无处分，三项成绩合格，已按时注册，成绩记录完整，请评估一等奖学金。',
]

const latestCompletedAssistantMessage = computed(() => {
  const lastMessage = messages.value[messages.value.length - 1]
  if (!lastMessage || lastMessage.role !== 'assistant' || lastMessage.streaming || !lastMessage.content) {
    return null
  }
  return lastMessage
})

const followUpSuggestions = computed(() => {
  return chatStore.activeFollowUpSuggestions
})

const showFollowUpSuggestions = computed(() => {
  return followUpSuggestions.value.length > 0 && !chatStore.streaming
})

async function initialize() {
  try {
    await chatStore.loadSessions()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '加载会话失败')
  }
}

async function handleSend(message) {
  try {
    await chatStore.sendMessage(message)
  } catch (error) {
    ElMessage.error(error.message || '发送失败')
  }
}

async function handleSuggestionClick(message) {
  await handleSend(message)
}

async function handleApproval(message, decisions) {
  try {
    await chatStore.resumeApproval(message, decisions)
  } catch (error) {
    ElMessage.error(error.message || '审批处理失败')
  }
}

function handleNewChat() {
  chatStore.startFreshSession()
}

async function handleDelete(sessionId) {
  try {
    await ElMessageBox.confirm('删除后无法恢复，是否继续？', '删除会话', {
      type: 'warning',
    })
    await chatStore.deleteSessionById(sessionId)
    ElMessage.success('会话已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || error.message || '删除失败')
    }
  }
}

async function handleLogout() {
  authStore.logout()
  chatStore.$reset()
  await router.push('/login')
}

async function handleOpenAdmin() {
  await router.push('/admin/files')
}

watch(
  () => messages.value.map((item) => item.content).join(''),
  async () => {
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  },
)

onMounted(() => {
  initialize()
})
</script>

<template>
  <div class="chat-page">
    <SessionSidebar
      :sessions="chatStore.sessions"
      :active-session-id="chatStore.activeSessionId"
      :username="authStore.username"
      :is-admin="authStore.isAdmin"
      @new-chat="handleNewChat"
      @select="chatStore.selectSession"
      @delete="handleDelete"
      @open-admin="handleOpenAdmin"
      @logout="handleLogout"
    />

    <main class="chat-main" :class="{ 'demo-layout': demoMode }">
      <div v-if="demoMode" class="demo-bar">
        <strong>RULE ENGINE</strong>
        <span>基于仓库内真实政策条款确定性计算｜未知信息不会自动推断</span>
      </div>
      <header class="chat-header">
        <div class="chat-header-main">
          <p class="chat-kicker">Scholarship Application Agent</p>
          <h2>奖助学金申请评估智能体</h2>
          <p class="chat-subcopy">
            {{ demoMode
              ? '输入明确条件，本地规则引擎会逐项核验政策，并展示满足、不满足和信息缺失。'
              : '输入你的目标与条件，Agent 会自主规划、调用政策与评估工具，并展示可核对的执行过程。' }}
          </p>
        </div>
        <div class="chat-header-status">
          <span class="chat-header-pill">DeepAgent 规划</span>
          <span class="chat-header-pill">MCP 工具</span>
        </div>
      </header>

      <section ref="scrollContainer" class="message-scroller">
        <div class="message-stack">
          <div v-if="messages.length === 0" class="empty-state">
            <span class="empty-badge">开始评估</span>
            <h3>先把关键条件说清楚，再由政策规则逐项判断。</h3>
            <p>
              推荐至少提供：专业、年级、绩点、专业排名、综测、家庭收入、贫困认定、获奖情况、是否有违纪记录。
            </p>
            <div class="suggestion-grid">
              <button
                v-for="prompt in suggestionPrompts"
                :key="prompt"
                class="suggestion-card"
                @click="handleSuggestionClick(prompt)"
              >
                {{ prompt }}
              </button>
            </div>
          </div>

          <ChatBubble
            v-for="message in messages"
            :key="message.id"
            :message="message"
            @approval="handleApproval"
          />

          <FollowUpSuggestions
            v-if="showFollowUpSuggestions"
            :suggestions="followUpSuggestions"
            :disabled="chatStore.streaming"
            @select="handleSuggestionClick"
          />
        </div>
      </section>

      <div class="composer-dock">
        <ChatComposer :loading="chatStore.streaming" @submit="handleSend" />
      </div>
    </main>
  </div>
</template>
