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

function colorOf(it) {
  if (it.prob == null) return NO_PROB
  if (it.caliber === 'herb_extrapolated') return EXTRAP
  if (mode.value === 'prob') {
    const p = it.prob
    return p >= 0.9 ? '#114a31' : p >= 0.7 ? '#1b6e4b' : p >= 0.5 ? '#a8711e' : '#b03d2f'
  }
  if (mode.value === 'domain') return adColors[it.ad_level_live ?? it.ad_level] || NO_PROB
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

// ---- 生信顶刊级 Canvas 绘制 ----
function draw() {
  const cv = canvasEl.value
  if (!cv || !items.value.length) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const cssW = cv.clientWidth || 340
  const cssH = cssW
  if (cv.width !== Math.round(cssW * dpr)) {
    cv.width = Math.round(cssW * dpr)
    cv.height = Math.round(cssH * dpr)
  }
  ctx = cv.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssW, cssH)

  // 1. 绘制极淡科研背景与微对齐十字网格
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

  // 2. 数据分流：背景外推点 (多) vs 核心验证集预测点 (少而精)
  const bgDots = [], coreDots = []
  for (const it of items.value) {
    if (it.caliber === 'herb_extrapolated' || it.prob == null) {
      bgDots.push(it)
    } else {
      coreDots.push(it)
    }
  }

  // 3. 绘制底层星云：微粒子半透明叠加，自然形成密度晕
  const rBg = Math.max(1.3, cssW / 240)
  ctx.globalAlpha = 0.25
  ctx.fillStyle = EXTRAP
  for (const it of bgDots) {
    ctx.beginPath()
    ctx.arc(px(it) * cssW, py(it) * cssH, rBg, 0, Math.PI * 2)
    ctx.fill()
  }

  // 4. 绘制核心预测点（带层次与清晰色彩）
  const rCore = Math.max(2.4, cssW / 140)
  ctx.globalAlpha = 0.88
  for (const it of coreDots) {
    const cx = px(it) * cssW, cy = py(it) * cssH
    ctx.fillStyle = colorOf(it)
    ctx.beginPath()
    ctx.arc(cx, cy, rCore, 0, Math.PI * 2)
    ctx.fill()
  }

  // 5. 选中焦点微晕
  if (picked.value) {
    const cx = px(picked.value) * cssW, cy = py(picked.value) * cssH
    // 外发光环
    ctx.globalAlpha = 0.35
    ctx.fillStyle = colorOf(picked.value)
    ctx.beginPath()
    ctx.arc(cx, cy, rCore * 3.5, 0, Math.PI * 2)
    ctx.fill()
    // 聚焦实心环
    ctx.globalAlpha = 1
    ctx.strokeStyle = '#1d1a14'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(cx, cy, rCore * 2.2, 0, Math.PI * 2)
    ctx.stroke()
  }

  // 6. 学术级 L 型坐标轴与元数据水印（Nature / Bioinformatics 规范）
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

function onClick(ev) {
  const cv = canvasEl.value
  if (!cv) return
  const rect = cv.getBoundingClientRect()
  const mx = (ev.clientX - rect.left) / rect.width
  const my = (ev.clientY - rect.top) / rect.height
  const tol = 0.024
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
    loading.value = false
  }
  await nextTick()
  draw()
}

watch(mode, () => draw())

onMounted(() => {
  load()
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
        <canvas v-else ref="canvasEl" class="map-canvas" @click="onClick"></canvas>
      </div>

      <!-- 学术图例 -->
      <div class="map-legend">
        <span v-for="l in legend" :key="l.t" class="lg-item">
          <i :style="{ background: l.c }"></i>{{ l.t }}
        </span>
      </div>

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
  box-shadow: inset 0 1px 4px rgba(0,0,0,0.02); touch-action: manipulation; cursor: crosshair;
}

.map-legend { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; padding: 2px 0; }
.lg-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--ink-600); }
.lg-item i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

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
