<script setup>
import { ChatLineRound, Guide, Opportunity } from '@element-plus/icons-vue'
import { computed } from 'vue'

const props = defineProps({
  suggestions: {
    type: Array,
    required: true,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['select'])

const icons = [Opportunity, Guide, ChatLineRound]

function normalizeSuggestion(value) {
  let text = String(value || '').trim()
  text = text.replace(/^```(?:json)?\s*|\s*```$/gi, '').trim()
  text = text.replace(/[?？。.!！]+$/g, '').trim()

  for (let index = 0; index < 3; index += 1) {
    const unwrapped = text
      .replace(/^\s*\[\s*['"“”]?/, '')
      .replace(/['"“”]?\s*\]\s*$/, '')
      .replace(/^\s*['"“]/, '')
      .replace(/['"”]\s*$/, '')
      .trim()

    if (unwrapped === text) {
      break
    }
    text = unwrapped
  }

  text = text.replace(/[?？]+$/g, '').trim()
  return text ? `${text}？` : ''
}

const normalizedSuggestions = computed(() => {
  const seen = new Set()
  return props.suggestions
    .map(normalizeSuggestion)
    .filter((item) => {
      if (!item || seen.has(item)) {
        return false
      }
      seen.add(item)
      return true
    })
    .slice(0, 3)
})
</script>

<template>
  <div v-if="normalizedSuggestions.length" class="followup-panel">
    <div class="followup-title">
      <el-icon><Opportunity /></el-icon>
      <span>你可能还想问</span>
    </div>
    <div class="followup-list">
      <button
        v-for="(suggestion, index) in normalizedSuggestions"
        :key="`${index}-${suggestion}`"
        class="followup-chip"
        type="button"
        :disabled="disabled"
        @click="emit('select', suggestion)"
      >
        <el-icon>
          <component :is="icons[index % icons.length]" />
        </el-icon>
        <span>{{ suggestion }}</span>
      </button>
    </div>
  </div>
</template>
