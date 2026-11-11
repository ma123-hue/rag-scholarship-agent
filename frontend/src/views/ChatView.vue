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

const messages = computed(() => chatStore.activeMessages)
const suggestionPrompts = [
  '我是大二计算机专业，绩点 3.82/4.0，专业排名前 8%，请先告诉我还需要补充哪些信息才能评估奖学金资格。',
  '我家庭年收入 2 万元，有贫困证明，综测前 20%，请评估我可能符合哪些助学金。',
  '我获得过校级三好学生和竞赛奖项，想申请国家奖学金，请按政策条款逐项比对。',
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

    <main class="chat-main">
      <header class="chat-header">
        <div class="chat-header-main">
          <p class="chat-kicker">Scholarship Application Agent</p>
          <h2>奖助学金申请评估智能体</h2>
          <p class="chat-subcopy">
            输入你的目标与条件，Agent 会自主规划、调用政策与评估工具，并展示可核对的执行过程。
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
            <h3>先把你的关键条件说清楚，再让模型判断是否符合政策。</h3>
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
