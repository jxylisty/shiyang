<script setup>
// 成分化学空间地图（T3-14）：全库 4,558 个可解析结构的成分的 UMAP 散点流形
// 相对位置有意义（基于 ECFP4 Morgan 指纹，结构相似的成分在流形上自发聚类）
// 着色：入血概率梯度 / 应用域 / 主模型 vs 独立模型一致性
// 视觉采用生信顶刊标准的粒子星云与半透明密度融合，消除过度绘制（Overplotting）
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { FlaskConical, ExternalLink, Sparkles, Compass } from '@lucide/vue'
import { getChemMap } from '../api'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'

const router = useRouter()
const items = ref([])
const stats = ref(null)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref(false)
const mode = ref('prob')  // prob | domain | consistency

const canvasEl = ref(null)
const wrapEl = ref(null)
const picked = ref(null)
let ctx = null
let ro = null

// 视图变换（缩放与平移）与动画状态
const INTRO_DURATION = 1100
const BG_STAGGER_MS = 150
const FADE_DURATION = 250
const MIN_SCALE = 1
const MAX_SCALE = 4
const DRAG_THRESHOLD_PX = 6
const DOUBLE_TAP_MS = 300
const DOUBLE_TAP_DIST_PX = 24

const view = { scale: 1, tx: 0, ty: 0 }
let introProgress = 1
let introRafId = 0
let fadeRafId = 0
let fadeFromMode = null
let fadeProgress = 1
let bgPrepared = []
let corePrepared = []

// Pointer Events 手势状态
const activePointers = new Map()
let downPos = null
let lastPos = null
let isDragging = false
let wasPinch = false
let prevPinchDist = 0
let prevPinchMid = { x: 0, y: 0 }
let lastTapTime = 0
let lastTapPos = null

const MODES = [
  { key: 'prob', label: '入血概率', hint: '深绿/朱砂红：ccTCM 核心训练验证集；冷灰青星云：HERB 拓展空间外推参考' },
  { key: 'domain', label: '应用域 (AD)', hint: '深绿=域内（高置信度高相似样本），红=域外（外推可靠性受限）；全库流形覆盖' },
  { key: 'consistency', label: '模型一致性', hint: '主模型与独立算法判定对比；核心 165 个训练集成分通过交叉双重检验' },
]

const cvNames = {
  both_high: '双模型一致·高入血', both_low: '双模型一致·低入血',
  main_only: '主模型单独高', indep_only: '独立模型单独高',
}

// 学术级高阶配色（消除脏黄色，采用冷灰青石雾与高纯度翡翠/珊瑚朱砂）
const NO_PROB = '#a8b4ad'       // 无预测/背景成分：通透冷灰
const EXTRAP = '#7a8f83'        // HERB 外推估计：冷青石雾，高雅星云底色
const adColors = { in: '#1b6e4b', edge: '#9a6b1f', out: '#b03d2f' }
const cvColors = { both_high: '#1b6e4b', both_low: '#5d7367', main_only: '#9a6b1f', indep_only: '#9a6b1f' }

function colorOf(it, targetMode = mode.value) {
  if (it.prob == null) return NO_PROB
  if (it.caliber === 'herb_extrapolated') return EXTRAP
  if (targetMode === 'prob') {
    const p = it.prob
    return p >= 0.9 ? '#114a31' : p >= 0.7 ? '#1b6e4b' : p >= 0.5 ? '#a8711e' : '#b03d2f'
  }
  if (targetMode === 'domain') return adColors[it.ad_level_live ?? it.ad_level] || NO_PROB
  return cvColors[it.cv_level] || NO_PROB
}

// 视口归一化：UMAP 坐标 → 单位方框（保留 6% 边距留给学术坐标轴）
const bounds = computed(() => {
  if (!items.value.length) return { x0: 0, y0: 0, s: 1 }
  const xs = items.value.map(i => i.x), ys = items.value.map(i => i.y)
  const x0 = Math.min(...xs), x1 = Math.max(...xs)
  const y0 = Math.min(...ys), y1 = Math.max(...ys)
  return { x0, y0, s: 1 / Math.max(x1 - x0, y1 - y0, 1e-9) }
})

// 留出左侧与底部 32px 空间画 UMAP 坐标轴
const px = (it) => 0.06 + (it.x - bounds.value.x0) * bounds.value.s * 0.88
const py = (it) => 0.92 - (it.y - bounds.value.y0) * bounds.value.s * 0.86

const legend = computed(() => {
  const s = stats.value || {}
  if (mode.value === 'prob') {
    return [
      { c: '#114a31', t: '≥0.9 极高入血' },
      { c: '#1b6e4b', t: '0.7–0.9 较高入血' },
      { c: '#a8711e', t: '0.5–0.7 中等' },
      { c: '#b03d2f', t: '<0.5 偏低' },
      { c: EXTRAP, t: `外推星云 ${s.extrapolated ?? 0}` },
      { c: NO_PROB, t: `背景结构 ${s.no_prob ?? 0}` }
    ]
  }
  if (mode.value === 'domain') {
    return [
      { c: adColors.in, t: `域内高信度 ${s.ad_in ?? 0}` },
      { c: adColors.edge, t: `临界边缘 ${s.ad_edge ?? 0}` },
      { c: adColors.out, t: `域外外推 ${s.ad_out ?? 0}` },
      { c: NO_PROB, t: `未评估 ${s.no_prob ?? 0}` }
    ]
  }
  return [
    { c: cvColors.both_high, t: `结论一致·高入血 ${s.cv_both_high ?? 0}` },
    { c: cvColors.both_low, t: `结论一致·低入血 ${s.cv_both_low ?? 0}` },
    { c: cvColors.main_only, t: `两模型分歧 ${s.cv_diverge ?? 0}` },
    { c: NO_PROB, t: `未评估 ${s.total - (s.cv_both_high ?? 0) - (s.cv_both_low ?? 0) - (s.cv_diverge ?? 0)}` }
  ]
})

function isReducedMotion() {
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3)
}

function getCanvasCssSize() {
  const cv = canvasEl.value
  const cssW = cv?.clientWidth || 340
  return { cssW, cssH: cssW }
}

function clampView(cssW, cssH) {
  view.scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.scale))
  const padX = cssW * 0.25
  const padY = cssH * 0.25
  const minTx = cssW * (1 - view.scale) - padX
  const maxTx = padX
  const minTy = cssH * (1 - view.scale) - padY
  const maxTy = padY
  view.tx = Math.min(maxTx, Math.max(minTx, view.tx))
  view.ty = Math.min(maxTy, Math.max(minTy, view.ty))
}

function preparePoints() {
  const rawBg = []
  const rawCore = []
  const staggerRatio = BG_STAGGER_MS / INTRO_DURATION
  let maxDist = 1e-6
  for (const it of items.value) {
    const nx = px(it)
    const ny = py(it)
    if (it.caliber === 'herb_extrapolated' || it.prob == null) {
      const dist = Math.hypot(nx - 0.5, ny - 0.5)
      if (dist > maxDist) maxDist = dist
      rawBg.push({ it, nx, ny, dist })
    } else {
      rawCore.push({ it, nx, ny })
    }
  }
  bgPrepared = rawBg.map((d) => ({
    it: d.it,
    nx: d.nx,
    ny: d.ny,
    delayP: (d.dist / maxDist) * staggerRatio,
  }))
  corePrepared = rawCore
}

function cancelAnimations() {
  if (introRafId) {
    cancelAnimationFrame(introRafId)
    introRafId = 0
  }
  if (fadeRafId) {
    cancelAnimationFrame(fadeRafId)
    fadeRafId = 0
  }
}

// ---- 生信顶刊级 Canvas 绘制 ----
function draw(progress = introProgress) {
  const cv = canvasEl.value
  if (!cv || !items.value.length) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const { cssW, cssH } = getCanvasCssSize()
  if (cv.width !== Math.round(cssW * dpr)) {
    cv.width = Math.round(cssW * dpr)
    cv.height = Math.round(cssH * dpr)
  }
  clampView(cssW, cssH)

  ctx = cv.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssW, cssH)

  // 1. 绘制极淡科研背景与微对齐十字网格（保持固定不随点云缩放）
  ctx.fillStyle = '#f6faf7'
  ctx.fillRect(0, 0, cssW, cssH)

  ctx.strokeStyle = 'rgba(58, 122, 94, 0.06)'
  ctx.lineWidth = 1
  const gridStep = cssW / 8
  ctx.beginPath()
  for (let x = gridStep; x < cssW; x += gridStep) {
    ctx.moveTo(x, 0); ctx.lineTo(x, cssH)
  }
  for (let y = gridStep; y < cssH; y += gridStep) {
    ctx.moveTo(0, y); ctx.lineTo(cssW, y)
  }
  ctx.stroke()

  const centerX = cssW * 0.5
  const centerY = cssH * 0.5
  const pClamped = Math.min(1, Math.max(0, progress))
  const coreEase = pClamped >= 1 ? 1 : easeOutCubic(pClamped)
  const radiusFactor = Math.min(1.65, 0.7 + 0.3 * view.scale)

  // 2. 绘制底层星云：微粒子半透明叠加，自然形成密度晕（入场带 0~150ms 距中心错峰）
  const rBg = Math.max(1.3, cssW / 240) * radiusFactor
  ctx.globalAlpha = 0.25
  ctx.fillStyle = EXTRAP
  for (const pt of bgPrepared) {
    let ax = pt.nx * cssW
    let ay = pt.ny * cssH
    if (pClamped < 1) {
      const localT = pClamped <= pt.delayP ? 0 : Math.min(1, (pClamped - pt.delayP) / (1 - pt.delayP))
      const eased = easeOutCubic(localT)
      ax = centerX + (ax - centerX) * eased
      ay = centerY + (ay - centerY) * eased
    }
    const sx = ax * view.scale + view.tx
    const sy = ay * view.scale + view.ty
    if (sx < -rBg || sx > cssW + rBg || sy < -rBg || sy > cssH + rBg) continue
    ctx.beginPath()
    ctx.arc(sx, sy, rBg, 0, Math.PI * 2)
    ctx.fill()
  }

  // 3. 绘制核心预测点（带层次与清晰色彩；模式切换时支持 250ms 双层交叉淡化）
  const rCore = Math.max(2.4, cssW / 140) * radiusFactor
  const isFading = Boolean(fadeFromMode && fadeProgress < 1)
  if (isFading) {
    const oldAlpha = 0.88 * (1 - fadeProgress)
    const newAlpha = 0.88 * fadeProgress
    for (const pt of corePrepared) {
      let ax = pt.nx * cssW
      let ay = pt.ny * cssH
      if (pClamped < 1) {
        ax = centerX + (ax - centerX) * coreEase
        ay = centerY + (ay - centerY) * coreEase
      }
      const sx = ax * view.scale + view.tx
      const sy = ay * view.scale + view.ty
      if (sx < -rCore || sx > cssW + rCore || sy < -rCore || sy > cssH + rCore) continue
      if (oldAlpha > 0.01) {
        ctx.globalAlpha = oldAlpha
        ctx.fillStyle = colorOf(pt.it, fadeFromMode)
        ctx.beginPath()
        ctx.arc(sx, sy, rCore, 0, Math.PI * 2)
        ctx.fill()
      }
      if (newAlpha > 0.01) {
        ctx.globalAlpha = newAlpha
        ctx.fillStyle = colorOf(pt.it, mode.value)
        ctx.beginPath()
        ctx.arc(sx, sy, rCore, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  } else {
    ctx.globalAlpha = 0.88
    for (const pt of corePrepared) {
      let ax = pt.nx * cssW
      let ay = pt.ny * cssH
      if (pClamped < 1) {
        ax = centerX + (ax - centerX) * coreEase
        ay = centerY + (ay - centerY) * coreEase
      }
      const sx = ax * view.scale + view.tx
      const sy = ay * view.scale + view.ty
      if (sx < -rCore || sx > cssW + rCore || sy < -rCore || sy > cssH + rCore) continue
      ctx.fillStyle = colorOf(pt.it)
      ctx.beginPath()
      ctx.arc(sx, sy, rCore, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // 4. 选中焦点微晕（跟随缩放平移变换）
  if (picked.value) {
    let ax = px(picked.value) * cssW
    let ay = py(picked.value) * cssH
    if (pClamped < 1) {
      ax = centerX + (ax - centerX) * coreEase
      ay = centerY + (ay - centerY) * coreEase
    }
    const sx = ax * view.scale + view.tx
    const sy = ay * view.scale + view.ty
    // 外发光环
    ctx.globalAlpha = 0.35
    ctx.fillStyle = colorOf(picked.value)
    ctx.beginPath()
    ctx.arc(sx, sy, rCore * 3.5, 0, Math.PI * 2)
    ctx.fill()
    // 聚焦实心环
    ctx.globalAlpha = 1
    ctx.strokeStyle = '#1d1a14'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(sx, sy, rCore * 2.2, 0, Math.PI * 2)
    ctx.stroke()
  }

  // 5. 学术级 L 型坐标轴与元数据水印（保持固定不随点云缩放）
  ctx.globalAlpha = 0.55
  ctx.strokeStyle = '#3a5948'
  ctx.lineWidth = 1.2
  const ox = 18, oy = cssH - 18
  ctx.beginPath()
  // Y 轴
  ctx.moveTo(ox, oy); ctx.lineTo(ox, oy - 38)
  ctx.lineTo(ox - 3, oy - 32); ctx.moveTo(ox, oy - 38); ctx.lineTo(ox + 3, oy - 32)
  // X 轴
  ctx.moveTo(ox, oy); ctx.lineTo(ox + 42, oy)
  ctx.lineTo(ox + 36, oy - 3); ctx.moveTo(ox + 42, oy); ctx.lineTo(ox + 36, oy + 3)
  ctx.stroke()

  ctx.fillStyle = '#2f4c3c'
  ctx.font = '600 9px ui-monospace, SFMono-Regular, monospace'
  ctx.fillText('UMAP 2', ox + 4, oy - 30)
  ctx.fillText('UMAP 1', ox + 18, oy + 12)

  // 右上角学术空间指纹注记
  ctx.textAlign = 'right'
  ctx.fillStyle = '#627a6d'
  ctx.font = '500 9px ui-monospace, SFMono-Regular, monospace'
  ctx.fillText('ECFP4 (Morgan) · Manifold', cssW - 10, 16)
  ctx.textAlign = 'left'
  ctx.globalAlpha = 1
}

function getLocalPoint(ev) {
  const cv = canvasEl.value
  const rect = cv.getBoundingClientRect()
  return {
    x: ev.clientX - rect.left,
    y: ev.clientY - rect.top,
    width: rect.width || 340,
    height: rect.height || 340,
  }
}

function getTwoPointerMetrics() {
  const pts = Array.from(activePointers.values())
  const a = pts[0], b = pts[1]
  return {
    dist: Math.hypot(b.x - a.x, b.y - a.y),
    mid: { x: (a.x + b.x) * 0.5, y: (a.y + b.y) * 0.5 },
  }
}

function pickAt(localX, localY, width, height) {
  // 点击坐标逆变换回归一化数据坐标：(mx - tx) / scale
  const dataX = (localX - view.tx) / (view.scale * width)
  const dataY = (localY - view.ty) / (view.scale * height)
  // 保持屏幕容差恒定约 0.024
  const tol = 0.024 / view.scale
  let best = null, bestD = Infinity
  for (const it of items.value) {
    const d = Math.hypot(px(it) - dataX, py(it) - dataY)
    if (d < bestD) { bestD = d; best = it }
  }
  if (best && bestD <= tol && best.prob != null) {
    picked.value = picked.value?.name === best.name ? null : best
  } else {
    picked.value = null
  }
  draw()
}

function onPointerDown(ev) {
  if (ev.pointerType === 'mouse' && ev.button !== 0) return
  const cv = canvasEl.value
  if (!cv) return
  try { cv.setPointerCapture?.(ev.pointerId) } catch {}
  const pt = getLocalPoint(ev)
  activePointers.set(ev.pointerId, { x: pt.x, y: pt.y })

  if (activePointers.size === 1) {
    downPos = { x: pt.x, y: pt.y }
    lastPos = { x: pt.x, y: pt.y }
    isDragging = false
    wasPinch = false
  } else if (activePointers.size === 2) {
    wasPinch = true
    isDragging = true
    const m = getTwoPointerMetrics()
    prevPinchDist = m.dist
    prevPinchMid = m.mid
  }
}

function onPointerMove(ev) {
  if (!activePointers.has(ev.pointerId)) return
  const pt = getLocalPoint(ev)
  activePointers.set(ev.pointerId, { x: pt.x, y: pt.y })

  if (activePointers.size === 1 && !wasPinch && lastPos && downPos) {
    if (!isDragging && Math.hypot(pt.x - downPos.x, pt.y - downPos.y) > DRAG_THRESHOLD_PX) {
      isDragging = true
    }
    if (isDragging) {
      view.tx += pt.x - lastPos.x
      view.ty += pt.y - lastPos.y
      clampView(pt.width, pt.height)
      draw()
    }
    lastPos = { x: pt.x, y: pt.y }
  } else if (activePointers.size === 2) {
    const m = getTwoPointerMetrics()
    if (prevPinchDist > 0) {
      const factor = m.dist / prevPinchDist
      const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.scale * factor))
      const ux = (prevPinchMid.x - view.tx) / view.scale
      const uy = (prevPinchMid.y - view.ty) / view.scale
      view.scale = nextScale
      view.tx = m.mid.x - ux * nextScale
      view.ty = m.mid.y - uy * nextScale
      clampView(pt.width, pt.height)
      draw()
    }
    prevPinchDist = m.dist
    prevPinchMid = m.mid
  }
}

function onPointerUp(ev) {
  const cv = canvasEl.value
  const pt = cv ? getLocalPoint(ev) : null
  const hadPointer = activePointers.delete(ev.pointerId)
  try { cv?.releasePointerCapture?.(ev.pointerId) } catch {}
  if (!hadPointer || !pt) return

  if (activePointers.size === 1) {
    const remaining = activePointers.values().next().value
    lastPos = remaining ? { x: remaining.x, y: remaining.y } : null
    return
  }

  if (activePointers.size === 0) {
    if (!isDragging && !wasPinch) {
      const now = performance.now()
      const isDoubleTap =
        lastTapTime > 0 &&
        now - lastTapTime <= DOUBLE_TAP_MS &&
        lastTapPos &&
        Math.hypot(pt.x - lastTapPos.x, pt.y - lastTapPos.y) <= DOUBLE_TAP_DIST_PX

      if (isDoubleTap) {
        lastTapTime = 0
        lastTapPos = null
        view.scale = 1
        view.tx = 0
        view.ty = 0
        draw()
      } else {
        lastTapTime = now
        lastTapPos = { x: pt.x, y: pt.y }
        pickAt(pt.x, pt.y, pt.width, pt.height)
      }
    }
    downPos = null
    lastPos = null
    isDragging = false
    wasPinch = false
    prevPinchDist = 0
  }
}

function onPointerCancel(ev) {
  activePointers.delete(ev.pointerId)
  if (activePointers.size === 1) {
    const remaining = activePointers.values().next().value
    lastPos = remaining ? { x: remaining.x, y: remaining.y } : null
  } else if (activePointers.size === 0) {
    downPos = null
    lastPos = null
    isDragging = false
    wasPinch = false
    prevPinchDist = 0
  }
}

function goDetail() {
  if (picked.value) router.push(`/compounds/${encodeURIComponent(picked.value.name)}`)
}

function startIntro() {
  cancelAnimations()
  introProgress = 0
  const t0 = performance.now()
  const step = (now) => {
    const p = Math.min(1, (now - t0) / INTRO_DURATION)
    introProgress = p
    if (p >= 1) {
      introRafId = 0
      introProgress = 1
      draw(1)
      return
    }
    draw(p)
    introRafId = requestAnimationFrame(step)
  }
  introRafId = requestAnimationFrame(step)
}

async function load() {
  if (loading.value || loaded.value) return
  loading.value = true
  try {
    const d = (await getChemMap()).data.data
    items.value = d.items || []
    stats.value = d.stats || null
    loaded.value = true
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
  if (!loaded.value) return
  preparePoints()
  await nextTick()
  if (isReducedMotion()) {
    introProgress = 1
    draw(1)
  } else {
    startIntro()
  }
}

watch(mode, (newMode, oldMode) => {
  if (!loaded.value || !items.value.length) return
  if (introRafId) {
    cancelAnimationFrame(introRafId)
    introRafId = 0
  }
  introProgress = 1
  if (fadeRafId) {
    cancelAnimationFrame(fadeRafId)
    fadeRafId = 0
  }
  if (!oldMode || newMode === oldMode || isReducedMotion()) {
    fadeFromMode = null
    fadeProgress = 1
    draw(1)
    return
  }
  fadeFromMode = oldMode
  fadeProgress = 0
  const t0 = performance.now()
  const step = (now) => {
    const p = Math.min(1, (now - t0) / FADE_DURATION)
    fadeProgress = p
    if (p >= 1) {
      fadeRafId = 0
      fadeFromMode = null
      fadeProgress = 1
      draw(1)
      return
    }
    draw(1)
    fadeRafId = requestAnimationFrame(step)
  }
  fadeRafId = requestAnimationFrame(step)
})

const onResize = () => draw()

onMounted(() => {
  load()
  if (typeof ResizeObserver !== 'undefined' && wrapEl.value) {
    ro = new ResizeObserver(onResize)
    ro.observe(wrapEl.value)
  } else {
    window.addEventListener('resize', onResize)
  }
})
onBeforeUnmount(() => {
  cancelAnimations()
  activePointers.clear()
  ro?.disconnect(); ro = null
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div class="page chem-map-page">
    <div class="card map-card">
      <div class="map-head">
        <div class="head-left">
          <div class="pro-tag">
            <Compass :size="12" :stroke-width="2.4" />
            <span>专业生信流形</span>
          </div>
          <h2 class="map-title">成分化学空间拓扑地图</h2>
        </div>
        <span class="map-sub">
          <template v-if="stats">{{ stats.total }} 个全库解析成分 · 空间流形表征结构相似性</template>
        </span>
      </div>

      <!-- 模式切换 -->
      <div class="map-modes">
        <button v-for="m in MODES" :key="m.key" class="map-mode" :class="{ on: mode === m.key }" @click="mode = m.key">
          {{ m.label }}
        </button>
      </div>
      <p class="map-hint">{{ MODES.find(m => m.key === mode)?.hint }}</p>

      <!-- 画布容器 -->
      <div ref="wrapEl" class="map-wrap">
        <div v-if="loading" class="map-loading">正在降维投影全库 4,558 个分子结构流形…</div>
        <div v-else-if="loadError" class="map-loading">服务暂时不可用</div>
        <div v-else-if="!loaded" class="map-loading">准备就绪</div>
        <canvas
          v-else
          ref="canvasEl"
          class="map-canvas"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerCancel"
        ></canvas>
      </div>

      <!-- 学术图例 -->
      <div class="map-legend">
        <span v-for="l in legend" :key="l.t" class="lg-item">
          <i :style="{ background: l.c }"></i>{{ l.t }}
        </span>
      </div>
      <p class="map-gesture-hint">双指缩放 · 拖拽平移 · 双击复位 · 点按查看成分</p>

      <!-- 点选成分卡片 -->
      <div v-if="picked" class="map-picked pressable" @click="goDetail">
        <div class="mp-top">
          <b class="mp-name">{{ picked.name }}</b>
          <span class="mp-go">查看档案 <ExternalLink :size="12" /></span>
        </div>
        <div class="mp-meta">
          <span>入血概率 <b>{{ picked.prob != null ? picked.prob.toFixed(3) : '—' }}</b></span>
          <span v-if="picked.cv_level" class="tag">{{ cvNames[picked.cv_level] }}</span>
        </div>
        <span v-if="picked.caliber === 'herb_extrapolated'" class="pick-warn">
          注：该化合物属 C 级外推参考集（非 ccTCM 核心验证集，由 HERB 辅助模型外推）
        </span>
      </div>
      <p v-else-if="loaded && stats?.extrapolated" class="map-tip">
        提示：冷青色星云代表全库 3,600+ 药食同源化合物的化学流形背景；高亮翡翠/珊瑚色为核心验证集，可直接点按查看该成分深度档案。
      </p>

      <p class="a-disclaimer">
        算法说明：基于 RDKit 计算 2048 位 Morgan 指纹 (ECFP4 半径=2)，经高维流形近似与投影 (UMAP) 映射至二维空间。空间欧氏距离反映分子结构相似性。
      </p>
      <DisclaimerBanner variant="compound" style="margin-top: 12px;" />
    </div>
  </div>
</template>

<style scoped>
.chem-map-page { padding-bottom: 24px; }
.map-card { padding: 18px 16px; border-radius: 16px; }

.head-left { display: flex; flex-direction: column; gap: 4px; }
.pro-tag {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px;
  background: var(--green-50); border: 1px solid var(--green-100);
  border-radius: 6px; font-size: 11px; color: var(--green-text); font-weight: 600; width: fit-content;
}
.map-title {
  font-family: var(--font-serif); font-size: 19px; font-weight: 700;
  color: var(--ink-900); margin: 0;
}
.map-sub { font-size: 11.5px; color: var(--ink-400); margin-top: 4px; display: block; }

.map-modes { display: flex; gap: 6px; margin-top: 14px; flex-wrap: wrap; }
.map-mode {
  border: 1px solid var(--green-100); background: #fff; border-radius: 20px;
  padding: 5px 14px; font-size: 12px; font-weight: 600; color: var(--ink-600);
  cursor: pointer; transition: all 0.15s ease;
}
.map-mode.on { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.map-hint { font-size: 11px; color: var(--ink-400); margin-top: 8px; min-height: 16px; line-height: 1.4; }

.map-wrap { margin-top: 12px; }
.map-loading {
  padding: 80px 16px; text-align: center; color: var(--ink-400); font-size: 13px;
  background: #f6faf7; border-radius: 14px; border: 1px solid rgba(58, 122, 94, 0.1);
}
.map-canvas {
  display: block; width: 100%; aspect-ratio: 1/1; background: #f6faf7;
  border-radius: 14px; border: 1px solid rgba(58, 122, 94, 0.15);
  box-shadow: inset 0 1px 4px rgba(0,0,0,0.02); touch-action: none; user-select: none; cursor: crosshair;
}

.map-legend { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; padding: 2px 0; }
.lg-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--ink-600); }
.lg-item i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.map-gesture-hint { margin: 6px 0 0; font-size: 11.5px; color: var(--ink-400); line-height: 1.4; }
:global(:root[data-fontsize="large"] .chem-map-page .map-gesture-hint) { font-size: 14px; line-height: 1.5; }
:global(:root[data-fontsize="xlarge"] .chem-map-page .map-gesture-hint) { font-size: 15.5px; line-height: 1.55; }

.map-picked {
  margin-top: 12px; background: linear-gradient(135deg, var(--green-50) 0%, #fff 100%);
  border: 1px solid rgba(58, 122, 94, 0.25); border-radius: 12px; padding: 12px 14px;
  display: flex; flex-direction: column; gap: 4px; cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}
.mp-top { display: flex; justify-content: space-between; align-items: center; }
.mp-name { font-size: 15px; font-family: var(--font-serif); color: var(--ink-900); }
.mp-go { font-size: 11.5px; color: var(--green-text); display: inline-flex; align-items: center; gap: 3px; }
.mp-meta { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-600); }
.mp-meta b { color: var(--green-text); font-variant-numeric: tabular-nums; }
.pick-warn { font-size: 11px; color: var(--amber-text); margin-top: 2px; }

.map-tip { margin-top: 10px; font-size: 11px; color: var(--ink-400); line-height: 1.5; }
.a-disclaimer {
  margin-top: 12px; font-size: 10.5px; color: var(--ink-400); line-height: 1.5;
  background: rgba(0,0,0,0.02); padding: 8px 10px; border-radius: 8px;
}
</style>
