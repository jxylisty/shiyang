<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { LoaderCircle, Mic, Square } from '@lucide/vue'
import { showToast } from 'vant'
import { transcribeVoice } from '../api'
import { captureVoice } from '../utils/voiceCapture'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '语音输入' },
  compact: Boolean,
  append: Boolean,
  maxlength: Number,
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const phase = ref('idle')
const label = computed(() => ({
  opening: '正在打开麦克风',
  recording: '结束录音',
  transcribing: '识别中',
})[phase.value] || props.label)
let session = null

function stop() {
  if (phase.value !== 'recording') return
  phase.value = 'transcribing'
  try {
    session.stop()
  } catch {
    cancel()
    showToast('录音中断，请重试。')
  }
}

function cancel() {
  if (!session) return
  clearTimeout(session.limit)
  session.controller.abort()
  session = null
  phase.value = 'idle'
}

async function start() {
  if (phase.value === 'recording') {
    stop()
    return
  }
  if (phase.value !== 'idle' || props.disabled) return
  const active = { controller: new AbortController(), startText: props.modelValue }
  const { signal } = active.controller
  session = active
  phase.value = 'opening'
  try {
    const audio = await captureVoice(signal, stopRecording => {
      active.stop = stopRecording
      phase.value = 'recording'
      active.limit = setTimeout(stop, 15000)
    })
    if (signal.aborted) return
    clearTimeout(active.limit)
    if (!audio?.size) {
      showToast('没录到声音，请重试。')
      return
    }
    phase.value = 'transcribing'
    const { data } = await transcribeVoice(audio, signal)
    if (signal.aborted || props.disabled) return
    const recognized = data.data.text.trim()
    const text = props.append ? recognized : recognized.replace(/[。！？!?，、；;,.]+$/u, '')
    if (!text) return
    if (!props.append && props.modelValue !== active.startText) {
      showToast('输入已更改，请重新录音或继续打字。')
      return
    }
    const next = props.append && props.modelValue ? `${props.modelValue.trimEnd()} ${text}` : text
    if (props.maxlength && next.length > props.maxlength) {
      showToast(`识别结果较长，只填入前 ${props.maxlength} 个字。`)
    }
    emit('update:modelValue', props.maxlength ? next.slice(0, props.maxlength) : next)
  } catch (error) {
    if (signal.aborted) return
    if (['NotAllowedError', 'SecurityError'].includes(error.name)) {
      showToast('无法使用麦克风，请在浏览器或系统设置中允许录音。')
    } else if (error.name === 'NotFoundError') {
      showToast('没有找到可用的麦克风。')
    } else {
      const message = error.response?.data?.detail
      showToast(typeof message === 'string' ? message : (error.isAxiosError
        ? '暂时无法识别语音，请重试或继续打字。'
        : error.message || '语音输入失败，请重试。'))
    }
  } finally {
    clearTimeout(active.limit)
    if (session === active) {
      phase.value = 'idle'
      session = null
    }
  }
}

function onHidden() {
  if (document.hidden && phase.value === 'recording') cancel()
}

onMounted(() => {
  document.addEventListener('visibilitychange', onHidden)
  window.addEventListener('pagehide', cancel)
})
onBeforeUnmount(() => {
  cancel()
  document.removeEventListener('visibilitychange', onHidden)
  window.removeEventListener('pagehide', cancel)
})
</script>

<template>
  <span class="voice-control">
    <button
      type="button"
      class="voice-button"
      :class="{ 'is-recording': phase === 'recording', 'is-compact': compact }"
      :disabled="phase === 'opening' || phase === 'transcribing' || (disabled && phase === 'idle')"
      :aria-label="label"
      :aria-pressed="phase === 'recording'"
      :title="phase === 'idle' ? `${props.label}，录音由食养有据服务器转写` : label"
      @click.stop="start"
      @keydown.esc.stop="cancel"
    >
      <Square v-if="phase === 'recording'" :size="20" />
      <LoaderCircle v-else-if="phase !== 'idle'" :size="21" class="voice-spin" />
      <Mic v-else :size="22" />
      <span v-if="!compact">{{ label }}</span>
    </button>
    <span class="voice-status" aria-live="polite">
      {{ phase === 'recording' ? '正在录音，说完请点结束录音' : phase === 'transcribing' ? '正在识别语音' : '' }}
    </span>
  </span>
</template>

<style scoped>
.voice-control { display: inline-flex; flex: none; vertical-align: middle; }
.voice-button {
  display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  min-width: 44px; min-height: 44px; padding: 8px 14px; border: 1px solid rgba(58, 122, 94, 0.28); border-radius: 12px;
  background: var(--green-50); color: var(--green-text); cursor: pointer;
  font: inherit; font-size: 14.5px; font-weight: 700; white-space: nowrap;
}
.voice-button.is-compact { padding: 0 10px; }
.voice-button:hover, .voice-button:focus-visible { background: var(--green-100); border-color: var(--green-600); }
.voice-button:disabled { opacity: .58; cursor: default; }
.voice-button.is-recording { background: var(--green-700); border-color: var(--green-700); color: white; }
.voice-status { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.voice-spin { animation: voice-spin .8s linear infinite; }
@keyframes voice-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .voice-spin { animation: none; } }
</style>
