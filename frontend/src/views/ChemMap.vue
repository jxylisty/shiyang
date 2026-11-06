<script setup>
// 成分化学空间地图（T3-14）：全库 4,558 个可解析结构的成分的 UMAP 散点
// 相对位置有意义（结构相似的成分靠近），坐标轴数值无物理含义
// 着色：入血概率梯度 / 应用域 / 主模型 vs 独立模型一致性，三种视角切换
//
// 渲染用 canvas 而不是 SVG：4,500+ 个 circle 会插 4,500+ DOM 节点，手机上拖都拖不动。
// 数据懒加载（进视口才请求），且只有概率预测的那 165 个支持点选查成分——
// 其余成分没有预测值，点开也没有可解释内容，光标就不该给 affordance。
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
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

const MODES = [
  { key: 'prob', label: '入血概率', hint: '绿/红=ccTCM 主力模型结论；土黄=HERB 兜底模型外推，误差更大' },
  { key: 'domain', label: '应用域', hint: '绿=域内（训练集里有相似样本），红=域外（预测可靠性有限）；全库已覆盖' },
  { key: 'consistency', label: '模型一致性', hint: '主模型与独立算法模型判断是否一致；只有 165 个训练集内成分评估过，其余显示为未评估' },
]

const cvNames = {
  both_high: '结论一致·高', both_low: '结论一致·低',
  main_only: '主模型单独高', indep_only: '独立模型单独高',
}

const NO_PROB = '#c9c1b4'   // 无预测成分：中性灰，不参与任何着色维度
const EXTRAP = '#b9a67c'    // HERB 外推估计：灰黄色，与主力模型的绿/红刻意区分
const adColors = { in: '#2e7d5b', edge: '#9a6b1f', out: '#b04a3a' }
const cvColors = { both_high: '#2e7d5b', both_low: '#6b7a72', main_only: '#9a6b1f', indep_only: '#9a6b1f' }

function colorOf(it) {
  // 没有任何预测数据 → 灰色。不要落到「<0.5 偏低」的红色档，
  // 那会把「没测」误读成「测了但很低」，属于数据失真。
  if (it.prob == null) return NO_PROB
  // 外推估计（C 级，仅 HERB 兜底模型、误差明显更大）单独一档灰黄，
  // 绝不与主力模型的绿/红同色，否则用户会以为两者同等可靠。
  if (it.caliber === 'herb_extrapolated') return EXTRAP
  if (mode.value === 'prob') {
    const p = it.prob
    return p >= 0.9 ? '#1d4a38' : p >= 0.7 ? '#2e7d5b' : p >= 0.5 ? '#9a6b1f' : '#b04a3a'
  }
  if (mode.value === 'domain') return adColors[it.ad_level_live ?? it.ad_level] || NO_PROB
  return cvColors[it.cv_level] || NO_PROB
}

// 视口归一化：UMAP 坐标 → 单位方框，绘制时再乘画布像素
const bounds = computed(() => {
  if (!items.value.length) return { x0: 0, y0: 0, s: 1 }
  const xs = items.value.map(i => i.x), ys = items.value.map(i => i.y)
  const x0 = Math.min(...xs), x1 = Math.max(...xs)
  const y0 = Math.min(...ys), y1 = Math.max(...ys)
  return { x0, y0, s: 1 / Math.max(x1 - x0, y1 - y0, 1e-9) }
})
const px = (it) => 0.03 + (it.x - bounds.value.x0) * bounds.value.s * 0.94
const py = (it) => 0.97 - (it.y - bounds.value.y0) * bounds.value.s * 0.94

const legend = computed(() => {
  const s = stats.value || {}
  if (mode.value === 'prob') {
    return [
      { c: '#1d4a38', t: '≥0.9 很高' }, { c: '#2e7d5b', t: '0.7–0.9 较高' },
      { c: '#9a6b1f', t: '0.5–0.7 中等' }, { c: '#b04a3a', t: '<0.5 偏低' },
      { c: EXTRAP, t: `外推估计 ${s.extrapolated ?? 0}` },
      { c: NO_PROB, t: `无预测 ${s.no_prob ?? 0}` }]
  }
  if (mode.value === 'domain') {
    return [
      { c: adColors.in, t: `域内 ${s.ad_in ?? 0}` },
      { c: adColors.edge, t: `边缘 ${s.ad_edge ?? 0}` },
      { c: adColors.out, t: `域外 ${s.ad_out ?? 0}` },
      { c: NO_PROB, t: `未评估 ${s.no_prob ?? 0}` }]
  }
  return [
    { c: cvColors.both_high, t: `结论一致·高 ${s.cv_both_high ?? 0}` },
    { c: cvColors.both_low, t: `结论一致·低 ${s.cv_both_low ?? 0}` },
    { c: cvColors.main_only, t: `分歧 ${s.cv_diverge ?? 0}` },
    { c: NO_PROB, t: `未评估 ${s.total - (s.cv_both_high ?? 0) - (s.cv_both_low ?? 0) - (s.cv_diverge ?? 0)}` }]
})

// ---- canvas 绘制 ----
function draw() {
  const cv = canvasEl.value
  if (!cv || !items.value.length) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)   // 上限 2：3x 屏上 4,500 点没必要
  const cssW = cv.clientWidth || 320
  const cssH = cssW
  if (cv.width !== Math.round(cssW * dpr)) {
    cv.width = Math.round(cssW * dpr)
    cv.height = Math.round(cssH * dpr)
  }
  ctx = cv.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssW, cssH)

  // 先画无预测的灰点（在底层），再画有预测的彩点，保证彩点不被压住
  const gray = [], color = []
  for (const it of items.value) (it.prob == null ? gray : color).push(it)

  const r = cssW / 100   // 与旧 SVG 视野 100×100 对齐，点径 1.1 → 视觉尺寸不变
  ctx.globalAlpha = 0.5
  ctx.fillStyle = NO_PROB
  for (const it of gray) {
    ctx.beginPath()
    ctx.arc(px(it) * cssW, py(it) * cssH, r * 1.1, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 0.9
  for (const it of color) {
    ctx.fillStyle = colorOf(it)
    ctx.beginPath()
    ctx.arc(px(it) * cssW, py(it) * cssH, r * 1.3, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1

  if (picked.value) {
    const cx = px(picked.value) * cssW, cy = py(picked.value) * cssH
    ctx.strokeStyle = '#1d1a14'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.arc(cx, cy, r * 2.6, 0, Math.PI * 2)
    ctx.stroke()
  }
}

// 点选：canvas 没有 DOM 命中，自己算最近点（只允许选中有预测值的点）
function onClick(ev) {
  const cv = canvasEl.value
  if (!cv) return
  const rect = cv.getBoundingClientRect()
  const mx = (ev.clientX - rect.left) / rect.width
  const my = (ev.clientY - rect.top) / rect.height
  const tol = 0.022   // 手指粗，容差按画面比例给
  let best = null, bestD = Infinity
  for (const it of items.value) {
    const d = Math.hypot(px(it) - mx, py(it) - my)
    if (d < bestD) { bestD = d; best = it }
  }
  if (best && bestD <= tol && best.prob != null) {
    picked.value = picked.value?.name === best.name ? null : best
  } else {
    picked.value = null
  }
  draw()
}

function goDetail() {
  if (picked.value) router.push(`/compounds/${encodeURIComponent(picked.value.name)}`)
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
    // 必须先关 loading：canvas 在 `v-else-if="!loaded"` 之后的分支里，
    // loading 仍为 true 时 DOM 上是「加载中…」，此时 nextTick 后 draw() 拿不到 canvas，
    // 画布会一直空白（2026-11-06 实测踩过）。
    loading.value = false
  }
  await nextTick()
  draw()
}

watch(mode, () => draw())

onMounted(() => {
  // 整页地图是用户主动导航进来的，页面存在的唯一目的就是看这张图 ——
  // 不需要滚动触发。2026-11-06 实测：在 in-app browser 里对整页 canvas 容器
  // 挂 IntersectionObserver，回调根本不触发（手动构造 IO 观察同一元素 1.5s 无回调），
  // 页面会永久停在「滚动到此处自动加载」。这里改为直接加载，不赌环境。
  load()
  // 窗口尺寸变化重绘（canvas 不是矢量的，缩放必须重画）
  if (typeof ResizeObserver !== 'undefined' && wrapEl.value) {
    ro = new ResizeObserver(() => draw())
    ro.observe(wrapEl.value)
  } else {
    window.addEventListener('resize', draw)
  }
})
onBeforeUnmount(() => {
  ro?.disconnect(); ro = null
  window.removeEventListener('resize', draw)
})
</script>

<template>
  <div class="page">
    <div class="card map-card">
      <div class="map-head">
        <b>成分化学空间地图</b>
        <span class="map-sub">
          <template v-if="stats">{{ stats.total }} 个成分 · 其中 {{ stats.with_prob }} 个有入血预测</template>
          <template v-else>结构相似者靠近</template>
        </span>
      </div>
      <div class="map-modes">
        <button v-for="m in MODES" :key="m.key" class="map-mode" :class="{ on: mode === m.key }" @click="mode = m.key">{{ m.label }}</button>
      </div>
      <p class="map-hint">{{ MODES.find(m => m.key === mode)?.hint }}</p>

      <div ref="wrapEl" class="map-wrap">
        <div v-if="loading" class="map-loading">加载中…</div>
        <div v-else-if="loadError" class="map-loading">服务暂时不可用</div>
        <div v-else-if="!loaded" class="map-loading">滚动到此处自动加载</div>
        <canvas v-else ref="canvasEl" class="map-canvas" @click="onClick"></canvas>
      </div>

      <div class="map-legend">
        <span v-for="l in legend" :key="l.t" class="lg-item"><i :style="{ background: l.c }"></i>{{ l.t }}</span>
      </div>

      <div v-if="picked" class="map-picked" @click="goDetail">
        <b>{{ picked.name }}</b>
        <span>入血概率 {{ picked.prob != null ? picked.prob.toFixed(3) : '—' }}<template v-if="picked.cv_level"> · {{ cvNames[picked.cv_level] }}</template></span>
        <span v-if="picked.caliber === 'herb_extrapolated'" class="pick-warn">外推估计（不在主力模型训练集内，仅供参考）</span>
        <em>点按查看成分档案 →</em>
      </div>
      <p v-else-if="loaded && stats?.extrapolated" class="map-tip">
        绿/红色点是 ccTCM 主力模型结论，可点选查看成分档案；土黄色点是 HERB 兜底模型外推估计
        （该成分不在这两个模型的训练集内，仅有结构数据可算），误差更大，仅供参考。
      </p>

      <p class="a-disclaimer">坐标为 UMAP 降维结果（Morgan 指纹→2 维），相对位置有意义、坐标轴数值无物理含义。</p>
      <DisclaimerBanner variant="compound" style="margin-top: 12px;" />
    </div>
  </div>
</template>

<style scoped>
.map-card { padding-bottom: 14px; }
.map-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.map-sub { font-size: 11px; color: var(--ink-400); }
.map-modes { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.map-mode { border: 1px solid var(--green-100); background: #fff; border-radius: 14px;
  padding: 4px 12px; font-size: 12px; color: var(--ink-600); font-family: inherit; }
.map-mode.on { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.map-hint { font-size: 11px; color: var(--ink-400); margin-top: 8px; min-height: 15px; }

.map-wrap { margin-top: 10px; }
.map-loading { padding: 60px 0; text-align: center; color: var(--ink-400); font-size: 13px;
  background: var(--green-50); border-radius: 12px; }
.map-canvas { display: block; width: 100%; aspect-ratio: 1/1; background: var(--green-50);
  border-radius: 12px; touch-action: manipulation; cursor: pointer; }

.map-legend { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }
.lg-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--ink-600); }
.lg-item i { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.map-picked { margin-top: 10px; background: var(--green-50); border-radius: 10px; padding: 10px 12px;
  display: flex; flex-direction: column; gap: 2px; cursor: pointer; }
.map-picked b { font-size: 14px; color: var(--ink-900); }
.map-picked span { font-size: 12px; color: var(--ink-600); font-variant-numeric: tabular-nums; }
.map-picked em { font-size: 11px; color: var(--green-text); font-style: normal; }
.map-picked .pick-warn { font-size: 11px; color: var(--amber-text); }
.map-tip { margin-top: 10px; font-size: 11px; color: var(--ink-400); line-height: 1.6; }
</style>
