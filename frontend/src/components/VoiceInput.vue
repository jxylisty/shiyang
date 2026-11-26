<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Check, LoaderCircle, Mic, Square, X } from '@lucide/vue'
import { showToast } from 'vant'
import { transcribeVoice } from '../api'
import { captureVoice } from '../utils/voiceCapture'
import VoiceWave from './VoiceWave.vue'

const SLIDE_CANCEL_PX = 60
const BOTTOM_ZONE_HEIGHT = 170

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '语音输入' },
  compact: Boolean,
  append: Boolean,
  maxlength: Number,
  disabled: Boolean,
  iconSize: { type: Number, default: 22 },
  hold: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])

const phase = ref('idle')
const stream = ref(null)
const zone = ref('send')
const slideCancel = computed(() => zone.value === 'cancel')
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
  if (zone.value === 'cancel') return '松开取消'
  if (zone.value === 'text') return '松开转文字'
  return '松开转文字，上滑取消'
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

function resolveHoldZone(clientX, clientY) {
  const vw = window.innerWidth || 0
  const vh = window.innerHeight || 0
  if (vh > 0 && clientY > vh - BOTTOM_ZONE_HEIGHT) {
    return clientX < vw / 2 ? 'cancel' : 'text'
  }
  return (pointerStartY - clientY) >= SLIDE_CANCEL_PX ? 'cancel' : 'send'
}

function resetPointerState() {
  activePointerId = null
  pointerStartY = 0
  zone.value = 'send'
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
  zone.value = 'send'
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
  zone.value = 'send'
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
  zone.value = 'send'
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
      zone.value = 'send'
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
  zone.value = 'send'
  try {
    e.currentTarget?.setPointerCapture?.(e.pointerId)
  } catch { /* ignore */ }
  start()
}

function onPointerMove(e) {
  if (!props.hold || e.pointerId !== activePointerId) return
  if (phase.value !== 'recording' && phase.value !== 'opening') return
  zone.value = resolveHoldZone(e.clientX, e.clientY)
}

function onPointerUp(e) {
  if (!props.hold || e.pointerId !== activePointerId) return
  e.preventDefault()
  releaseCapture(e.currentTarget, e.pointerId)
  const shouldCancel = zone.value === 'cancel'
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
  const slidUp = resolveHoldZone(e.clientX, e.clientY) === 'cancel' || zone.value === 'cancel'
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

function onPageHide() {
  resetPointerState()
  cancel()
}

onMounted(() => {
  document.addEventListener('visibilitychange', onHidden)
  document.addEventListener('keydown', onDocKeyDown)
  window.addEventListener('pagehide', onPageHide)
  window.addEventListener('blur', onWindowBlur)
})
onBeforeUnmount(() => {
  clearTimeout(suppressTimer)
  resetPointerState()
  cancel()
  document.removeEventListener('visibilitychange', onHidden)
  document.removeEventListener('keydown', onDocKeyDown)
  window.removeEventListener('pagehide', onPageHide)
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
        'is-text': hold && zone === 'text',
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
          v-if="!hold && phase === 'recording'"
          class="voice-overlay"
          role="status"
          aria-live="polite"
        >
          <div class="vo-head">
            <span class="vo-state">
              <span class="vo-dot" aria-hidden="true" />
              <Mic :size="15" :stroke-width="2.2" />
              <span>录音中</span>
            </span>
            <span class="vo-timer">{{ formattedTime }}</span>
          </div>

          <VoiceWave
            :stream="stream"
            :active="phase === 'recording'"
          />

          <p class="vo-hint">{{ overlayHint }}</p>

          <div class="vo-actions">
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

      <Transition name="voice-wechat">
        <div
          v-if="hold && phase === 'recording'"
          class="voice-wechat"
          :class="{ 'is-cancel': zone === 'cancel', 'is-text': zone === 'text' }"
          role="status"
          aria-live="polite"
        >
          <div class="vw-stage">
            <div class="vw-bubble">
              <span class="vw-timer">{{ formattedTime }}</span>
              <VoiceWave
                :stream="stream"
                :active="phase === 'recording'"
                :danger="zone === 'cancel'"
              />
            </div>
            <p class="vw-hint">{{ overlayHint }}</p>
          </div>

          <div class="vw-arcs" aria-hidden="true">
            <div class="vw-arc vw-arc-cancel" :class="{ 'is-active': zone === 'cancel' }">
              <span class="vw-arc-label">
                <X :size="18" :stroke-width="2.4" />
                <span>取消</span>
              </span>
            </div>
            <div class="vw-arc vw-arc-text" :class="{ 'is-active': zone === 'text' }">
              <span class="vw-arc-label">
                <Check :size="18" :stroke-width="2.4" />
                <span>滑到这里转文字</span>
              </span>
            </div>
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
.voice-button.is-hold.is-recording.is-text { background: var(--green-800, #1b4336); border-color: var(--green-800, #1b4336); color: #fdfaf1; }
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

/* hold 模式微信式全屏浮层 */
.voice-wechat {
  position: fixed;
  inset: 0;
  background: rgba(16, 28, 22, 0.55);
  z-index: 2200;
  pointer-events: none;
  overflow: hidden;
}
.vw-stage {
  position: absolute;
  top: 36%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.vw-bubble {
  position: relative;
  width: 240px;
  max-width: calc(100vw - 32px);
  padding: 24px 18px 14px;
  border-radius: 18px;
  background: linear-gradient(165deg, #1b4336 0%, var(--green-900) 100%);
  border: 1px solid rgba(143, 201, 171, 0.28);
  color: #fdfaf1;
  box-shadow: 0 12px 32px -6px rgba(20, 51, 42, 0.44), 0 4px 12px rgba(20, 51, 42, 0.22);
  transition: transform 180ms var(--ease-out-soft), opacity 180ms ease, background var(--dur-fast) ease, border-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.vw-bubble::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -9px;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 9px solid var(--green-900);
  transition: border-top-color var(--dur-fast) ease;
}
.voice-wechat.is-cancel .vw-bubble {
  background: linear-gradient(165deg, var(--cinnabar) 0%, #86261e 100%);
  border-color: rgba(253, 250, 241, 0.36);
  box-shadow: 0 12px 32px -6px rgba(168, 52, 42, 0.46), 0 4px 12px rgba(168, 52, 42, 0.24);
}
.voice-wechat.is-cancel .vw-bubble::after {
  border-top-color: #86261e;
}
.vw-timer {
  position: absolute;
  top: 8px;
  right: 12px;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
  line-height: 1;
  color: rgba(253, 250, 241, 0.86);
}
.vw-hint {
  margin: 20px 0 0;
  text-align: center;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.4;
  color: #fdfaf1;
  white-space: nowrap;
  text-shadow: 0 1px 4px rgba(16, 28, 22, 0.45);
  transition: opacity 180ms ease;
}
.vw-arcs {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 170px;
  overflow: hidden;
  transition: transform 220ms var(--ease-out-soft), opacity 220ms ease;
}
.vw-arc {
  position: absolute;
  bottom: 0;
  width: 58vw;
  height: 170px;
  border-radius: 50% 50% 0 0 / 100% 100% 0 0;
  background: rgba(253, 250, 241, 0.14);
  color: #fdfaf1;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.3;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  transform-origin: center bottom;
  transition: background var(--dur-fast) ease, transform var(--dur-fast) var(--ease-out-soft);
}
.vw-arc-cancel {
  left: -10vw;
  padding: 52px 10px 16px 10vw;
}
.vw-arc-text {
  right: -10vw;
  padding: 52px 10vw 16px 10px;
}
.vw-arc-label {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
}
.vw-arc-cancel.is-active {
  background: rgba(168, 52, 42, 0.85);
  transform: scale(1.04);
}
.vw-arc-text.is-active {
  background: rgba(27, 67, 54, 0.9);
  transform: scale(1.04);
}

.voice-wechat-enter-active {
  transition: opacity 180ms ease;
}
.voice-wechat-leave-active {
  transition: opacity 150ms ease;
}
.voice-wechat-leave-active .vw-bubble,
.voice-wechat-leave-active .vw-hint,
.voice-wechat-leave-active .vw-arcs {
  transition-duration: 150ms;
}
.voice-wechat-enter-from,
.voice-wechat-leave-to {
  opacity: 0;
}
.voice-wechat-enter-from .vw-bubble,
.voice-wechat-leave-to .vw-bubble {
  opacity: 0;
  transform: scale(0.9) translateY(8px);
}
.voice-wechat-enter-from .vw-hint,
.voice-wechat-leave-to .vw-hint {
  opacity: 0;
}
.voice-wechat-enter-from .vw-arcs,
.voice-wechat-leave-to .vw-arcs {
  opacity: 0;
  transform: translateY(24px);
}

:global(:root[data-fontsize="large"]) .vw-timer { font-size: 14px; }
:global(:root[data-fontsize="large"]) .vw-hint,
:global(:root[data-fontsize="large"]) .vw-arc { font-size: 19px; }
:global(:root[data-fontsize="xlarge"]) .vw-timer { font-size: 15px; }
:global(:root[data-fontsize="xlarge"]) .vw-hint { font-size: 21px; }
:global(:root[data-fontsize="xlarge"]) .vw-arc { font-size: 20px; }

@keyframes voice-spin { to { transform: rotate(360deg); } }
@keyframes voPulse {
  0%, 100% { transform: scale(0.85); opacity: 0.55; }
  50% { transform: scale(1.18); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .voice-spin,
  .vo-dot { animation: none; }
  .voice-sheet-enter-active,
  .voice-sheet-leave-active,
  .voice-wechat-enter-active,
  .voice-wechat-leave-active,
  .voice-wechat-enter-active .vw-bubble,
  .voice-wechat-leave-active .vw-bubble,
  .voice-wechat-enter-active .vw-hint,
  .voice-wechat-leave-active .vw-hint,
  .voice-wechat-enter-active .vw-arcs,
  .voice-wechat-leave-active .vw-arcs,
  .vw-bubble,
  .vw-bubble::after,
  .vw-hint,
  .vw-arcs,
  .vw-arc { transition: none; }
}
</style>
