<script setup>
import { Promotion } from '@element-plus/icons-vue'
import { ref } from 'vue'

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['submit'])
const draft = ref('')

function submit() {
  const value = draft.value.trim()
  if (!value || props.loading) {
    return
  }
  emit('submit', value)
  draft.value = ''
}

function handleKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="composer-shell">
    <div class="composer-heading">
      <span class="composer-heading-dot"></span>
      <p class="composer-heading-text">建议一次性输入完整条件，系统会更准确地对照政策。</p>
    </div>
    <el-input
      v-model="draft"
      type="textarea"
      :rows="3"
      resize="none"
      placeholder="输入你的专业排名、绩点、综测、家庭收入、贫困证明、获奖情况等。Shift+Enter 换行，Enter 发送。"
      @keydown="handleKeydown"
    />
    <div class="composer-actions">
      <div class="composer-shortcuts">
        <span>Enter 发送</span>
        <span>Shift + Enter 换行</span>
      </div>
      <el-button class="composer-send" type="primary" round :loading="loading" @click="submit">
        <el-icon><Promotion /></el-icon>
        发送
      </el-button>
    </div>
  </div>
</template>
