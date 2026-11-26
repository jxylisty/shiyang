<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { LoaderCircle, Mic, Square, X } from '@lucide/vue'
import { showToast } from 'vant'
import { transcribeVoice } from '../api'
import { captureVoice } from '../utils/voiceCapture'
import VoiceWave from './VoiceWave.vue'

const SLIDE_CANCEL_PX = 60

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '语音输入' },
  compact: Boolean,
  append: Boolean,
  maxlength: Number,
  disabled: Boolean,
  iconSize: { type: Number, default: 22 },
  hold: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const phase = ref('idle')
const stream = ref(null)
const slideCancel = ref(false)
const elapsedSec = ref(0)

const label = computed(() => {
  if (props.hold) {
    return ({
      opening: '正在打开麦克风',
      recording: '松开结束',
      transcribing: '识别中',
    })[phase.value] || '按住说话'
  }
  return ({
    opening: '正在打开麦克风',
    recording: '结束录音',
    transcribing: '识别中',
  })[phase.value] || props.label
})

const formattedTime = computed(() => {
  const mins = Math.floor(elapsedSec.value / 60)
  const secs = elapsedSec.value % 60
  return `${mins}:${String(secs).padStart(2, '0')}`
})

const overlayHint = computed(() => {
  if (!props.hold) return '正在录音，点按结束'
  return slideCancel.value ? '松开取消' : '松开结束，上滑取消'
})

let session = null
let activePointerId = null
let pointerStartY = 0
let suppressClick = false
let suppressTimer = null

function clearSessionTimers(target) {
  if (!target) return
  clearTimeout(target.limit)
  clearInterval(target.tick)
  target.limit = null
  target.tick = null
}

function resetPointerState() {
  activePointerId = null
  pointerStartY = 0
  slideCancel.value = false
}

function scheduleClearSuppressClick() {
  clearTimeout(suppressTimer)
  suppressTimer = setTimeout(() => {
    suppressClick = false
  }, 80)
}

function releaseCapture(el, pointerId) {
  try {
    if (el?.hasPointerCapture?.(pointerId)) {
      el.releasePointerCapture(pointerId)
    }
  } catch { /* ignore */ }
}

function stop() {
  if (phase.value !== 'recording' || !session) return
  clearSessionTimers(session)
  stream.value = null
  slideCancel.value = false
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
  clearSessionTimers(session)
  session.controller.abort()
  session = null
  stream.value = null
  slideCancel.value = false
  elapsedSec.value = 0
  phase.value = 'idle'
}

async function start() {
  if (phase.value === 'recording') {
    stop()
    return
  }
  if (phase.value !== 'idle' || props.disabled) return
  const active = {
    controller: new AbortController(),
    startText: props.modelValue,
    limit: null,
    tick: null,
    stop: null,
  }
  const { signal } = active.controller
  session = active
  phase.value = 'opening'
  slideCancel.value = false
  elapsedSec.value = 0
  try {
    const audio = await captureVoice(signal, (stopRecording, mediaStream) => {
      if (signal.aborted || session !== active) return
      active.stop = stopRecording
      stream.value = mediaStream || null
      elapsedSec.value = 0
      const startedAt = Date.now()
      active.tick = setInterval(() => {
        elapsedSec.value = Math.floor((Date.now() - startedAt) / 1000)
      }, 250)
      active.limit = setTimeout(stop, 15000)
      phase.value = 'recording'
    })
    if (signal.aborted) return
    clearSessionTimers(active)
    stream.value = null
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
    clearSessionTimers(active)
    if (session === active) {
      phase.value = 'idle'
      session = null
      stream.value = null
      slideCancel.value = false
      elapsedSec.value = 0
    }
  }
}

function onPointerDown(e) {
  if (!props.hold) return
  if (e.button !== undefined && e.button !== 0) return
  e.preventDefault()
  if (phase.value !== 'idle' || props.disabled) return
  clearTimeout(suppressTimer)
  suppressClick = true
  activePointerId = e.pointerId
  pointerStartY = e.clientY
  slideCancel.value = false
  try {
    e.currentTarget?.setPointerCapture?.(e.pointerId)
  } catch { /* ignore */ }
  start()
}

function onPointerMove(e) {
  if (!props.hold || e.pointerId !== activePointerId) return
  if (phase.value !== 'recording' && phase.value !== 'opening') return
  slideCancel.value = (pointerStartY - e.clientY) >= SLIDE_CANCEL_PX
}

function onPointerUp(e) {
  if (!props.hold || e.pointerId !== activePointerId) return
  e.preventDefault()
  releaseCapture(e.currentTarget, e.pointerId)
  const shouldCancel = slideCancel.value
  resetPointerState()
  scheduleClearSuppressClick()
  if (phase.value === 'opening') {
    cancel()
    showToast('请按住按钮说话')
  } else if (phase.value === 'recording') {
    if (shouldCancel) cancel()
    else stop()
  }
}

function onPointerCancel(e) {
  if (!props.hold || e.pointerId !== activePointerId) return
  releaseCapture(e.currentTarget, e.pointerId)
  resetPointerState()
  scheduleClearSuppressClick()
  if (phase.value === 'opening' || phase.value === 'recording') {
    cancel()
  }
}

function onPointerLeave(e) {
  if (!props.hold || e.pointerId !== activePointerId) return
  if (e.currentTarget?.hasPointerCapture?.(e.pointerId)) return
  const slidUp = (pointerStartY - e.clientY) >= SLIDE_CANCEL_PX || slideCancel.value
  resetPointerState()
  scheduleClearSuppressClick()
  if (phase.value === 'opening') {
    cancel()
  } else if (phase.value === 'recording') {
    if (slidUp) cancel()
    else stop()
  }
}

function onContextMenu(e) {
  if (props.hold) e.preventDefault()
}

function onButtonClick() {
  if (props.hold && suppressClick) {
    suppressClick = false
    clearTimeout(suppressTimer)
    return
  }
  start()
}

function onButtonKeyDown(e) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    resetPointerState()
    cancel()
    return
  }
  if (props.hold && (e.key === 'Enter' || e.key === ' ')) {
    suppressClick = false
  }
}

function onHidden() {
  if (document.hidden && (phase.value === 'recording' || phase.value === 'opening')) {
    resetPointerState()
    cancel()
  }
}

function onWindowBlur() {
  if (props.hold && (phase.value === 'recording' || phase.value === 'opening')) {
    resetPointerState()
    cancel()
  }
}

function onDocKeyDown(e) {
  if (e.key === 'Escape' && (phase.value === 'recording' || phase.value === 'opening')) {
    resetPointerState()
    cancel()
  }
}

onMounted(() => {
  document.addEventListener('visibilitychange', onHidden)
  document.addEventListener('keydown', onDocKeyDown)
  window.addEventListener('pagehide', cancel)
  window.addEventListener('blur', onWindowBlur)
})
onBeforeUnmount(() => {
  clearTimeout(suppressTimer)
  resetPointerState()
  cancel()
  document.removeEventListener('visibilitychange', onHidden)
  document.removeEventListener('keydown', onDocKeyDown)
  window.removeEventListener('pagehide', cancel)
  window.removeEventListener('blur', onWindowBlur)
})
</script>

<template>
  <span class="voice-control">
    <button
      type="button"
      class="voice-button"
      :class="{
        'is-recording': phase === 'recording',
        'is-opening': phase === 'opening',
        'is-compact': compact,
        'is-hold': hold,
        'is-cancel': hold && slideCancel,
      }"
      :disabled="phase === 'transcribing' || (disabled && phase === 'idle')"
      :aria-disabled="phase === 'opening' ? 'true' : undefined"
      :aria-label="label"
      :aria-pressed="phase === 'recording'"
      :title="phase === 'idle' ? `${hold ? '按住说话' : props.label}，录音由食养有据服务器转写` : label"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerCancel"
      @pointerleave="onPointerLeave"
      @contextmenu="onContextMenu"
      @click.stop="onButtonClick"
      @keydown="onButtonKeyDown"
    >
      <Square v-if="phase === 'recording' && !hold" :size="Math.max(20, iconSize - 2)" />
      <LoaderCircle v-else-if="phase === 'opening' || phase === 'transcribing'" :size="Math.max(21, iconSize - 1)" class="voice-spin" />
      <Mic v-else :size="iconSize" />
      <span v-if="!compact">{{ label }}</span>
    </button>
    <span class="voice-status" aria-live="polite">
      {{ phase === 'recording' ? overlayHint : phase === 'transcribing' ? '正在识别语音' : '' }}
    </span>

    <Teleport to="body">
      <Transition name="voice-sheet">
        <div
          v-if="phase === 'recording'"
          class="voice-overlay"
          :class="{ 'is-hold': hold, 'is-cancel': hold && slideCancel }"
          role="status"
          aria-live="polite"
        >
          <div class="vo-head">
            <span class="vo-state">
              <span class="vo-dot" aria-hidden="true" />
              <X v-if="hold && slideCancel" :size="15" :stroke-width="2.4" />
              <Mic v-else :size="15" :stroke-width="2.2" />
              <span>{{ hold && slideCancel ? '准备取消' : '录音中' }}</span>
            </span>
            <span class="vo-timer">{{ formattedTime }}</span>
          </div>

          <VoiceWave
            :stream="stream"
            :active="phase === 'recording'"
            :danger="hold && slideCancel"
          />

          <p class="vo-hint">{{ overlayHint }}</p>

          <div v-if="!hold" class="vo-actions">
            <button type="button" class="vo-btn vo-btn-cancel" @click.stop="cancel">
              <X :size="16" :stroke-width="2.2" />
              <span>取消</span>
            </button>
            <button type="button" class="vo-btn vo-btn-stop" @click.stop="stop">
              <Square :size="14" :stroke-width="2.4" />
              <span>结束录音</span>
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </span>
</template>

<style scoped>
.voice-control { display: inline-flex; flex: none; vertical-align: middle; }
.voice-button {
  display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  flex-shrink: 0;
  min-width: 44px; min-height: 44px; padding: 8px 14px; border: 1px solid rgba(58, 122, 94, 0.28); border-radius: 12px;
  background: var(--green-50); color: var(--green-text); cursor: pointer;
  font: inherit; font-size: 14.5px; font-weight: 700; white-space: nowrap;
}
.voice-button.is-compact { padding: 0 10px; }
.voice-button.is-hold {
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}
.voice-button:hover, .voice-button:focus-visible { background: var(--green-100); border-color: var(--green-600); }
.voice-button:disabled,
.voice-button.is-opening { opacity: .58; cursor: default; }
.voice-button.is-recording { background: var(--green-700); border-color: var(--green-700); color: white; }
.voice-button.is-recording.is-cancel { background: var(--cinnabar); border-color: var(--cinnabar); color: #fdfaf1; }
.voice-status { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.voice-spin { animation: voice-spin .8s linear infinite; }

.voice-overlay {
  position: fixed;
  left: 16px;
  right: 16px;
  bottom: calc(20px + var(--tabbar-offset, 0px));
  max-width: 352px;
  margin: 0 auto;
  z-index: 2200;
  padding: 13px 16px 14px;
  border-radius: 16px;
  background: linear-gradient(165deg, #1b4336 0%, var(--green-900) 100%);
  border: 1px solid rgba(143, 201, 171, 0.28);
  color: #fdfaf1;
  box-shadow: 0 12px 32px -6px rgba(20, 51, 42, 0.44), 0 4px 12px rgba(20, 51, 42, 0.22);
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.voice-overlay.is-hold {
  bottom: calc(124px + var(--tabbar-offset, 0px));
  pointer-events: none;
}
.voice-overlay.is-cancel {
  background: linear-gradient(165deg, var(--cinnabar) 0%, #86261e 100%);
  border-color: rgba(253, 250, 241, 0.36);
  box-shadow: 0 12px 32px -6px rgba(168, 52, 42, 0.46), 0 4px 12px rgba(168, 52, 42, 0.24);
}
.vo-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.vo-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #fdfaf1;
}
.vo-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #8fc9ab;
  animation: voPulse 1.2s ease-in-out infinite;
}
.voice-overlay.is-cancel .vo-dot {
  background: #fdfaf1;
}
.vo-timer {
  font-size: 17px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
  color: #fdfaf1;
}
.vo-hint {
  margin: 0;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  color: rgba(238, 243, 236, 0.9);
}
.voice-overlay.is-cancel .vo-hint {
  color: #fdfaf1;
}
.vo-actions {
  display: grid;
  grid-template-columns: 1fr 1.35fr;
  gap: 10px;
  margin-top: 2px;
}
.vo-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 44px;
  min-height: 44px;
  padding: 8px 14px;
  border-radius: 11px;
  font-family: inherit;
  font-size: 14.5px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity var(--dur-fast) ease, background var(--dur-fast) ease;
}
.vo-btn-cancel {
  background: rgba(253, 250, 241, 0.12);
  border: 1px solid rgba(253, 250, 241, 0.28);
  color: #fdfaf1;
}
.vo-btn-cancel:hover {
  background: rgba(253, 250, 241, 0.2);
}
.vo-btn-stop {
  background: #fdfaf1;
  border: 1px solid #fdfaf1;
  color: var(--green-900);
}
.vo-btn-stop:hover {
  opacity: 0.92;
}

.voice-sheet-enter-active,
.voice-sheet-leave-active {
  transition: opacity var(--dur-fast) ease, transform var(--dur-fast) var(--ease-out-soft);
}
.voice-sheet-enter-from,
.voice-sheet-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@keyframes voice-spin { to { transform: rotate(360deg); } }
@keyframes voPulse {
  0%, 100% { transform: scale(0.85); opacity: 0.55; }
  50% { transform: scale(1.18); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .voice-spin,
  .vo-dot { animation: none; }
  .voice-sheet-enter-active,
  .voice-sheet-leave-active { transition: none; }
}
</style>
