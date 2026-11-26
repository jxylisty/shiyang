<script>
// 模块级自增计数：保证未传 id 的实例 fallbackId 全局唯一（script setup 内声明会每实例重置）
let nextInstanceUid = 0
</script>

<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { Square, Volume2 } from '@lucide/vue'
import { isSpeechSupported, speak, speakingId, stopSpeak } from '../utils/speak'

const props = defineProps({
  text: { type: [String, Function], required: true },
  label: { type: String, default: '朗读' },
  id: { type: String, default: '' },
  ariaLabel: { type: String, default: '' },
})

const supported = isSpeechSupported()
const fallbackId = `speak-btn-${++nextInstanceUid}`
const buttonId = computed(() => props.id || fallbackId)

const resolvedText = computed(() => {
  const raw = typeof props.text === 'function' ? props.text() : props.text
  return typeof raw === 'string' ? raw : String(raw ?? '')
})

const hasText = computed(() => resolvedText.value.trim().length > 0)
const isSpeaking = computed(() => speakingId.value === buttonId.value)

const computedAriaLabel = computed(() => {
  if (isSpeaking.value) {
    return props.ariaLabel ? `停止${props.ariaLabel}` : '停止朗读'
  }
  return props.ariaLabel || `${props.label}内容`
})

function onToggle() {
  if (!supported) return
  if (isSpeaking.value) {
    stopSpeak()
    return
  }
  if (!hasText.value) return
  speak(resolvedText.value, buttonId.value)
}

// 文本或标识变化时，若当前按钮正在朗读旧内容则立即停止（如测评切题）
watch([resolvedText, buttonId], ([nextText, nextId], [prevText, prevId]) => {
  if ((nextText !== prevText || nextId !== prevId) && speakingId.value === prevId) {
    stopSpeak()
  }
})

onBeforeUnmount(() => {
  if (isSpeaking.value) {
    stopSpeak()
  }
})
</script>

<template>
  <button
    v-if="supported"
    type="button"
    class="speak-btn pressable"
    :class="{ 'is-speaking': isSpeaking }"
    :disabled="!hasText && !isSpeaking"
    :aria-label="computedAriaLabel"
    :aria-pressed="isSpeaking"
    @click="onToggle"
  >
    <Square v-if="isSpeaking" :size="14" :stroke-width="2.4" class="speak-icon" aria-hidden="true" />
    <Volume2 v-else :size="16" :stroke-width="2.2" class="speak-icon" aria-hidden="true" />
    <span>{{ isSpeaking ? '停止' : label }}</span>
  </button>
</template>

<style scoped>
.speak-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 44px;
  min-height: 44px;
  padding: 8px 13px;
  border-radius: 999px;
  border: 1px solid rgba(58, 122, 94, 0.28);
  background: var(--green-50);
  color: var(--green-text);
  font-family: var(--font-sans);
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease, color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}

.speak-btn:hover:not(:disabled),
.speak-btn:focus-visible:not(:disabled) {
  background: var(--green-100);
  border-color: var(--green-600);
}

.speak-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.speak-btn.is-speaking {
  background: var(--green-700);
  border-color: var(--green-700);
  color: #fdfaf1;
  box-shadow: 0 2px 8px rgba(42, 95, 74, 0.24);
}

.speak-btn.is-speaking:hover:not(:disabled),
.speak-btn.is-speaking:focus-visible:not(:disabled) {
  background: var(--green-900);
  border-color: var(--green-900);
}

.speak-icon {
  flex-shrink: 0;
}

.speak-btn.is-speaking .speak-icon {
  animation: speakBreath 1.4s ease-in-out infinite;
}

@keyframes speakBreath {
  0%, 100% {
    transform: scale(0.92);
    opacity: 0.85;
  }
  50% {
    transform: scale(1.1);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .speak-btn,
  .speak-btn.is-speaking .speak-icon {
    animation: none !important;
    transition: none !important;
  }
}
</style>
