import { defineStore } from 'pinia'
import { reactive } from 'vue'

import {
  fetchPendingApproval,
  fetchSessionMessages,
  fetchSessions,
  removeSession,
  resumeChat,
  streamChat,
} from '../api/chat'
import { useAuthStore } from './auth'


function nowIso() {
  return new Date().toISOString()
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
const TYPEWRITER_CHARS_PER_TICK = DEMO_MODE ? 5 : 1
const TYPEWRITER_DELAY_MS = DEMO_MODE ? 8 : 18


export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [],
    activeSessionId: null,
    draftMessages: [],
    messagesBySession: {},
    followUpSuggestionsBySession: {},
    loadingSessions: false,
    streaming: false,
  }),
  getters: {
    activeMessages(state) {
      if (state.activeSessionId === null) {
        return state.draftMessages
      }
      return state.messagesBySession[state.activeSessionId] || []
    },
    activeFollowUpSuggestions(state) {
      if (state.activeSessionId === null) {
        return []
      }
      return state.followUpSuggestionsBySession[state.activeSessionId] || []
    },
  },
  actions: {
    async refreshSessionMessages(sessionId) {
      if (sessionId === null || sessionId === undefined) {
        return
      }
      const { data } = await fetchSessionMessages(sessionId)
      this.messagesBySession[sessionId] = data
    },
    async loadSessions() {
      this.loadingSessions = true
      try {
        const { data } = await fetchSessions()
        this.sessions = data
        if (this.activeSessionId === null && data.length > 0) {
          await this.selectSession(data[0].id)
        }
      } finally {
        this.loadingSessions = false
      }
    },
    async selectSession(sessionId) {
      this.activeSessionId = sessionId
      if (!this.messagesBySession[sessionId]) {
        const { data } = await fetchSessionMessages(sessionId)
        this.messagesBySession[sessionId] = data
      }
      await this.restorePendingApproval(sessionId)
    },
    async restorePendingApproval(sessionId) {
      const { data } = await fetchPendingApproval(sessionId)
      const messages = this.messagesBySession[sessionId] || []
      for (const message of messages) {
        if (message.role === 'assistant' && message.approval) message.approval = null
      }
      if (!data.pending || !data.approval) return

      let assistantMessage = [...messages].reverse().find((item) => item.role === 'assistant')
      if (!assistantMessage) {
        assistantMessage = reactive({
          id: `approval-${sessionId}`,
          role: 'assistant',
          content: '',
          timestamp: nowIso(),
          agentEvents: [],
          todos: [],
          streaming: false,
        })
        messages.push(assistantMessage)
        this.messagesBySession[sessionId] = messages
      }
      assistantMessage.approval = { ...data.approval, resolving: false }
    },
    startFreshSession() {
      this.activeSessionId = null
      this.draftMessages = []
      this.followUpSuggestionsBySession = {}
    },
    async deleteSessionById(sessionId) {
      await removeSession(sessionId)
      this.sessions = this.sessions.filter((item) => item.id !== sessionId)
      delete this.messagesBySession[sessionId]
      delete this.followUpSuggestionsBySession[sessionId]
      if (this.activeSessionId === sessionId) {
        if (this.sessions.length > 0) {
          await this.selectSession(this.sessions[0].id)
        } else {
          this.startFreshSession()
        }
      }
    },
    async sendMessage(message) {
      if (this.streaming) return
      const authStore = useAuthStore()
      const targetSessionId = this.activeSessionId
      let resolvedSessionId = targetSessionId
      let targetList
      if (targetSessionId === null) {
        targetList = this.draftMessages
      } else {
        if (!this.messagesBySession[targetSessionId]) {
          this.messagesBySession[targetSessionId] = []
        }
        targetList = this.messagesBySession[targetSessionId]
      }
      let receivedEndEvent = false
      let pendingAssistantText = ''
      let typingPromise = null

      const userMessage = reactive({
        id: `u-${Date.now()}`,
        role: 'user',
        content: message,
        timestamp: nowIso(),
      })
      const assistantMessage = reactive({
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: '',
        timestamp: nowIso(),
        suggestions: [],
        agentEvents: [],
        todos: [],
        streaming: true,
      })

      targetList.push(userMessage, assistantMessage)
      this.streaming = true

      const drainAssistantText = async () => {
        try {
          while (pendingAssistantText.length > 0) {
            const nextText = pendingAssistantText.slice(0, TYPEWRITER_CHARS_PER_TICK)
            pendingAssistantText = pendingAssistantText.slice(TYPEWRITER_CHARS_PER_TICK)
            assistantMessage.content += nextText
            await wait(TYPEWRITER_DELAY_MS)
          }
        } finally {
          typingPromise = null
          if (pendingAssistantText.length > 0) {
            typingPromise = drainAssistantText()
          }
        }
      }

      const enqueueAssistantText = (text) => {
        if (!text) {
          return
        }
        pendingAssistantText += text
        if (!typingPromise) {
          typingPromise = drainAssistantText()
        }
      }

      const flushAssistantText = async () => {
        while (typingPromise || pendingAssistantText.length > 0) {
          if (!typingPromise && pendingAssistantText.length > 0) {
            typingPromise = drainAssistantText()
          }
          if (typingPromise) {
            await typingPromise
          }
        }
      }

      try {
        await streamChat({
          token: authStore.token,
          sessionId: targetSessionId,
          message,
          onEvent: async (event) => {
            if (event.type === 'session') {
              resolvedSessionId = event.session_id
              if (targetSessionId === null) {
                this.messagesBySession[event.session_id] = this.draftMessages
                this.draftMessages = []
                targetList = this.messagesBySession[event.session_id]
                this.activeSessionId = event.session_id
              }

              const existing = this.sessions.find((item) => item.id === event.session_id)
              if (!existing) {
                this.sessions.unshift({
                  id: event.session_id,
                  session_title: event.session_title,
                  created_at: nowIso(),
                  updated_at: nowIso(),
                })
              }
            }

            if (event.type === 'token') {
              enqueueAssistantText(event.content)
            }

            if (event.type === 'todo') {
              assistantMessage.todos = Array.isArray(event.items) ? event.items : []
            }

            if (event.type === 'tool_call' || event.type === 'tool_result') {
              assistantMessage.agentEvents.push({
                ...event,
                id: `${event.type}-${Date.now()}-${assistantMessage.agentEvents.length}`,
              })
            }

            if (event.type === 'approval_required') {
              assistantMessage.approval = { ...event, resolving: false }
            }

            if (event.type === 'error') {
              enqueueAssistantText(`\n\n系统错误：${event.content}`)
            }

            if (event.type === 'suggestions') {
              const suggestions = Array.isArray(event.items) ? event.items.slice(0, 3) : []
              if (resolvedSessionId !== null && resolvedSessionId !== undefined) {
                this.followUpSuggestionsBySession[resolvedSessionId] = suggestions
              }
            }

            if (event.type === 'end') {
              receivedEndEvent = true
              await flushAssistantText()
              assistantMessage.streaming = false
              await this.loadSessions()
            }
          },
        })
      } finally {
        if (!receivedEndEvent) {
          await flushAssistantText()
          assistantMessage.streaming = false
          await this.loadSessions()
        }
        this.streaming = false
      }
    },
    async resumeApproval(message, decisions) {
      const authStore = useAuthStore()
      const sessionId = this.activeSessionId
      if (!sessionId || !message.approval || this.streaming) return

      const previousApproval = { ...message.approval }
      message.approval.resolving = true
      message.streaming = true
      this.streaming = true
      try {
        await resumeChat({
          token: authStore.token,
          sessionId,
          decisions,
          onEvent: async (event) => {
            if (event.type === 'session') message.approval = null
            if (event.type === 'token') message.content += event.content || ''
            if (event.type === 'todo') message.todos = Array.isArray(event.items) ? event.items : []
            if (event.type === 'tool_call' || event.type === 'tool_result') {
              if (!message.agentEvents) message.agentEvents = []
              message.agentEvents.push({
                ...event,
                id: `${event.type}-${Date.now()}-${message.agentEvents.length}`,
              })
            }
            if (event.type === 'approval_required') {
              message.approval = { ...event, resolving: false }
            }
            if (event.type === 'error') message.content += `\n\n系统错误：${event.content}`
            if (event.type === 'end') {
              message.streaming = false
              await this.loadSessions()
            }
          },
        })
      } catch (error) {
        message.approval = { ...previousApproval, resolving: false }
        message.streaming = false
        throw error
      } finally {
        message.streaming = false
        this.streaming = false
      }
    },
  },
})
