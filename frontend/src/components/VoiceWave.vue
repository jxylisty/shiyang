<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  stream: { type: Object, default: null },
  active: { type: Boolean, default: true },
  danger: { type: Boolean, default: false },
})

const BAR_COUNT = 32
const FALLBACK_COUNT = 28

const canvasRef = ref(null)
const fallbackForced = ref(false)
const reducedMotion = ref(false)

const useCanvas = computed(() => Boolean(props.stream) && !fallbackForced.value)

// 中间高两边低的对称包络系数（0.28 ~ 1.0）
function envelopeAt(index, total) {
  if (total <= 1) return 1
  const t = Math.abs((index / (total - 1)) * 2 - 1)
  return 0.28 + 0.72 * Math.pow(Math.cos(t * Math.PI * 0.5), 1.35)
}

const fallbackBars = Array.from({ length: FALLBACK_COUNT }, (_, i) => {
  const env = envelopeAt(i, FALLBACK_COUNT)
  const delay = ((i % 7) * 0.12).toFixed(2)
  return {
    id: i,
    heightPct: Math.round((24 + env * 52) * 10) / 10,
    delay: `${delay}s`,
  }
})

let rafId = null
let audioCtx = null
let sourceNode = null
let analyserNode = null
let freqData = null
let timeData = null
let resizeObserver = null
let motionQuery = null
const smoothed = new Float32Array(BAR_COUNT)

function cleanupAudioAndRaf() {
  if (rafId != null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  try {
    sourceNode?.disconnect()
  } catch { /* ignore */ }
  try {
    analyserNode?.disconnect()
  } catch { /* ignore */ }
  sourceNode = null
  analyserNode = null
  freqData = null
  timeData = null
  if (audioCtx && audioCtx.state !== 'closed') {
    audioCtx.close().catch(() => {})
  }
  audioCtx = null
}

function drawBars(levels) {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = canvas.clientWidth || 240
  const height = canvas.clientHeight || 42
  const dpr = Math.min(window.devicePixelRatio || 1, 3)
  const targetW = Math.round(width * dpr)
  const targetH = Math.round(height * dpr)
  if (canvas.width !== targetW || canvas.height !== targetH) {
    canvas.width = targetW
    canvas.height = targetH
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)

  const step = width / BAR_COUNT
  const barWidth = Math.max(2.4, Math.min(3.6, step * 0.46))
  const maxSpan = Math.max(4, height - barWidth - 6)
  const cy = height / 2

  ctx.lineWidth = barWidth
  ctx.lineCap = 'round'

  for (let i = 0; i < BAR_COUNT; i++) {
    const env = envelopeAt(i, BAR_COUNT)
    const level = levels ? levels[i] : 0.14
    const span = Math.max(2, maxSpan * env * Math.min(1, Math.max(0.08, level)))
    const half = span / 2
    const x = (i + 0.5) * step

    const alpha = props.danger
      ? (0.58 + 0.38 * env)
      : (0.52 + 0.44 * env)
    ctx.strokeStyle = props.danger
      ? `rgba(253, 250, 241, ${alpha.toFixed(2)})`
      : `rgba(188, 228, 204, ${alpha.toFixed(2)})`

    ctx.beginPath()
    ctx.moveTo(x, cy - half)
    ctx.lineTo(x, cy + half)
    ctx.stroke()
  }
}

function startWaveform() {
  cleanupAudioAndRaf()
  fallbackForced.value = false

  if (!props.active || !props.stream) return

  if (reducedMotion.value) {
    drawBars(null)
    return
  }

  const AudioCtx = window.AudioContext || window.webkitAudioContext
  if (!AudioCtx) {
    fallbackForced.value = true
    return
  }

  try {
    audioCtx = new AudioCtx()
    if (audioCtx.state === 'suspended') {
      audioCtx.resume().catch(() => {})
    }
    sourceNode = audioCtx.createMediaStreamSource(props.stream)
    analyserNode = audioCtx.createAnalyser()
    analyserNode.fftSize = 256
    analyserNode.smoothingTimeConstant = 0.72
    sourceNode.connect(analyserNode)

    const bins = analyserNode.frequencyBinCount
    freqData = new Uint8Array(bins)
    timeData = new Uint8Array(bins)
    smoothed.fill(0.12)
  } catch {
    cleanupAudioAndRaf()
    fallbackForced.value = true
    return
  }

  const render = (now) => {
    if (!props.active || !analyserNode) return
    analyserNode.getByteFrequencyData(freqData)
    analyserNode.getByteTimeDomainData(timeData)

    let sumSq = 0
    for (let i = 0; i < timeData.length; i++) {
      const sample = (timeData[i] - 128) / 128
      sumSq += sample * sample
    }
    const rms = Math.min(1, Math.sqrt(sumSq / timeData.length) * 3.6)

    for (let i = 0; i < BAR_COUNT; i++) {
      const dist = Math.abs(i - (BAR_COUNT - 1) / 2) / ((BAR_COUNT - 1) / 2)
      const bin = Math.min(freqData.length - 2, 1 + Math.floor(dist * 24))
      const avgBin = (freqData[bin - 1] + freqData[bin] + freqData[bin + 1]) / 3
      const freqNorm = Math.min(1, avgBin / 205)
      const ripple = 0.88 + 0.12 * Math.sin(now * 0.007 + i * 0.65)
      const target = Math.max(0.10, (freqNorm * 0.62 + rms * 0.56) * ripple)
      smoothed[i] += (target - smoothed[i]) * 0.32
    }

    drawBars(smoothed)
    rafId = requestAnimationFrame(render)
  }

  rafId = requestAnimationFrame(render)
}

function onMotionChange(e) {
  reducedMotion.value = Boolean(e.matches)
  startWaveform()
}

function handleResize() {
  if (useCanvas.value && reducedMotion.value) {
    drawBars(null)
  }
}

onMounted(() => {
  motionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null
  reducedMotion.value = Boolean(motionQuery?.matches)
  motionQuery?.addEventListener?.('change', onMotionChange)

  if (typeof ResizeObserver !== 'undefined' && canvasRef.value) {
    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(canvasRef.value)
  } else {
    window.addEventListener('resize', handleResize)
  }

  startWaveform()
})

watch(
  [() => props.stream, () => props.active, () => props.danger],
  ([nextStream, nextActive], [prevStream, prevActive]) => {
    if (nextStream !== prevStream || nextActive !== prevActive) {
      startWaveform()
    } else if (reducedMotion.value && useCanvas.value) {
      drawBars(null)
    }
  },
)

onBeforeUnmount(() => {
  cleanupAudioAndRaf()
  motionQuery?.removeEventListener?.('change', onMotionChange)
  resizeObserver?.disconnect()
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="voice-wave" :class="{ 'is-danger': danger }" aria-hidden="true">
    <canvas v-if="useCanvas" ref="canvasRef" class="vw-canvas" />
    <div v-else class="vw-fallback">
      <span
        v-for="bar in fallbackBars"
        :key="bar.id"
        class="vw-fallback-bar"
        :style="{ height: `${bar.heightPct}%`, animationDelay: bar.delay }"
      />
    </div>
  </div>
</template>

<style scoped>
.voice-wave {
  width: 100%;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.vw-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
.vw-fallback {
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 3px;
  padding: 0 4px;
}
.vw-fallback-bar {
  flex: 1;
  max-width: 3.5px;
  border-radius: 999px;
  background: rgba(188, 228, 204, 0.78);
  transform-origin: center;
  animation: vwBreathe 1.45s ease-in-out infinite;
}
.voice-wave.is-danger .vw-fallback-bar {
  background: rgba(253, 250, 241, 0.84);
}
@keyframes vwBreathe {
  0%, 100% {
    transform: scaleY(0.38);
    opacity: 0.56;
  }
  50% {
    transform: scaleY(0.86);
    opacity: 0.94;
  }
}
@media (prefers-reduced-motion: reduce) {
  .vw-fallback-bar {
    animation: none;
    transform: scaleY(0.55);
    opacity: 0.72;
  }
}
</style>
