<script setup>
import { Delete, EditPen, FolderOpened, Plus } from '@element-plus/icons-vue'

import { formatApiDate } from '../utils/time'

const props = defineProps({
  sessions: {
    type: Array,
    required: true,
  },
  activeSessionId: {
    type: Number,
    default: null,
  },
  username: {
    type: String,
    default: '',
  },
  isAdmin: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['new-chat', 'select', 'delete', 'open-admin', 'logout'])

function formatTime(value) {
  return formatApiDate(value, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <aside class="sidebar-shell">
    <div class="sidebar-brand">
      <div class="brand-mark">S</div>
      <div>
        <p class="brand-title">Scholarship AI</p>
        <p class="brand-subtitle">政策检索与资格评估</p>
      </div>
    </div>

    <el-button class="new-chat-button" type="primary" round @click="emit('new-chat')">
      <el-icon><Plus /></el-icon>
      新建对话
    </el-button>

    <el-button
      v-if="isAdmin"
      class="admin-entry-button"
      plain
      round
      @click="emit('open-admin')"
    >
      <el-icon><FolderOpened /></el-icon>
      文件管理
    </el-button>

    <p class="sidebar-section-label">历史会话</p>

    <div class="session-list">
      <button
        v-for="session in sessions"
        :key="session.id"
        class="session-card"
        :class="{ active: activeSessionId === session.id }"
        @click="emit('select', session.id)"
      >
        <div class="session-main">
          <el-icon class="session-icon"><EditPen /></el-icon>
          <div class="session-copy">
            <span class="session-title">{{ session.session_title }}</span>
            <span class="session-time">{{ formatTime(session.updated_at) }}</span>
          </div>
        </div>
        <span
          class="session-delete"
          @click.stop="emit('delete', session.id)"
        >
          <el-icon><Delete /></el-icon>
        </span>
      </button>
    </div>

    <div class="sidebar-footer">
      <div class="user-chip">
        <span class="user-dot"></span>
        <span>{{ username || '未命名用户' }}</span>
      </div>
      <el-button text class="logout-button" @click="emit('logout')">退出登录</el-button>
    </div>
  </aside>
</template>
