<script setup>
// 成分化学空间地图（T3-14）：165 个成分的 UMAP 散点
// 相对位置有意义（结构相似的成分靠近），坐标轴数值无物理含义
// 着色：入血概率梯度 / 应用域 / 主模型 vs 独立模型一致性，三种视角切换
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getChemMap } from '../api'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const loadError = ref(false)
const mode = ref('prob')  // prob | domain | consistency

const MODES = [
  { key: 'prob', label: '入血概率', hint: '颜色越绿，模型判断越可能入血' },
  { key: 'domain', label: '应用域', hint: '绿=域内（训练集里有相似样本），红=域外（预测可靠性有限）' },
  { key: 'consistency', label: '模型一致性', hint: '主模型与独立算法模型判断是否一致；分歧点若聚团，说明分歧来自结构类别' },
]

const cvNames = {
  both_high: '结论一致·高', both_low: '结论一致·低',
  main_only: '主模型单独高', indep_only: '独立模型单独高',
}

const adColors = { in: '#2e7d5b', edge: '#9a6b1f', out: '#b04a3a' }
const cvColors = { both_high: '#2e7d5b', both_low: '#6b7a72', main_only: '#9a6b1f', indep_only: '#9a6b1f' }

function colorOf(it) {
  if (mode.value === 'prob') {
    const p = it.prob_cctcm ?? 0
    return p >= 0.9 ? '#1d4a38' : p >= 0.7 ? '#2e7d5b' : p >= 0.5 ? '#9a6b1f' : '#b04a3a'
  }
  if (mode.value === 'domain') return adColors[it.ad_level] || '#6b7a72'
  return cvColors[it.cv_level] || '#6b7a72'
}

// 视口归一化：UMAP 坐标 → SVG 0-100
const bounds = computed(() => {
  if (!items.value.length) return { x0: 0, y0: 0, s: 1 }
  const xs = items.value.map(i => i.x), ys = items.value.map(i => i.y)
  const x0 = Math.min(...xs), x1 = Math.max(...xs)
  const y0 = Math.min(...ys), y1 = Math.max(...ys)
  return { x0, y0, s: 100 / Math.max(x1 - x0, y1 - y0, 1e-9) }
})
const px = (it) => 2 + (it.x - bounds.value.x0) * bounds.value.s
const py = (it) => 100 - 2 - (it.y - bounds.value.y0) * bounds.value.s

const legend = computed(() => {
  if (mode.value === 'prob') return [
    { c: '#1d4a38', t: '≥0.9 很高' }, { c: '#2e7d5b', t: '0.7–0.9 较高' },
    { c: '#9a6b1f', t: '0.5–0.7 中等' }, { c: '#b04a3a', t: '<0.5 偏低' }]
  if (mode.value === 'domain') return [
    { c: '#2e7d5b', t: '域内 160' }, { c: '#9a6b1f', t: '边缘 2' }, { c: '#b04a3a', t: '域外 3' }]
  return [
    { c: '#2e7d5b', t: '结论一致·高 45' }, { c: '#6b7a72', t: '结论一致·低 77' },
    { c: '#9a6b1f', t: '分歧 43' }]
})

// 悬停/点击态：手机上用点击选中
const picked = ref(null)
function pick(it) { picked.value = picked.value === it ? null : it }

function goDetail() {
  if (picked.value) router.push(`/compounds/${encodeURIComponent(picked.value.name)}`)
}

async function load() {
  try {
    const d = (await getChemMap()).data.data
    items.value = d.items || []
  } catch { loadError.value = true } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="card map-card">
      <div class="map-head">
        <b>成分化学空间地图</b>
        <span class="map-sub">{{ items.length }} 个成分 · 结构相似者靠近</span>
      </div>
      <div class="map-modes">
        <button v-for="m in MODES" :key="m.key" class="map-mode" :class="{ on: mode === m.key }" @click="mode = m.key">{{ m.label }}</button>
      </div>
      <p class="map-hint">{{ MODES.find(m => m.key === mode)?.hint }}</p>
      <div v-if="loading" class="map-loading">加载中…</div>
      <div v-else-if="loadError" class="map-loading">服务暂时不可用</div>
      <svg v-else viewBox="0 0 100 100" class="map-svg" preserveAspectRatio="xMidYMid meet">
        <circle v-for="it in items" :key="it.name" :cx="px(it)" :cy="py(it)" r="1.1"
                :fill="colorOf(it)" fill-opacity="0.82"
                :stroke="picked === it ? '#1d1a14' : 'none'" :stroke-width="0.7"
                class="map-dot" @click="pick(it)" />
      </svg>
      <div class="map-legend">
        <span v-for="l in legend" :key="l.t" class="lg-item"><i :style="{ background: l.c }"></i>{{ l.t }}</span>
      </div>
      <div v-if="picked" class="map-picked" @click="goDetail">
        <b>{{ picked.name }}</b>
        <span>入血概率 {{ picked.prob_cctcm ?? '—' }}<template v-if="picked.cv_level"> · {{ cvNames[picked.cv_level] }}</template></span>
        <em>点按查看成分档案 →</em>
      </div>
      <p class="a-disclaimer">{{ (items[0] && '') || '' }}坐标为 UMAP 降维结果（Morgan 指纹→2 维），相对位置有意义、坐标轴数值无物理含义。</p>
    </div>
  </div>
</template>

<style scoped>
.map-card { padding-bottom: 14px; }
.map-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.map-sub { font-size: 11px; color: var(--ink-400); }
.map-modes { display: flex; gap: 6px; margin-top: 10px; }
.map-mode { border: 1px solid var(--green-100); background: #fff; border-radius: 14px;
  padding: 4px 12px; font-size: 12px; color: var(--ink-600); font-family: inherit; }
.map-mode.on { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.map-hint { font-size: 11px; color: var(--ink-400); margin-top: 8px; min-height: 15px; }
.map-loading { padding: 60px 0; text-align: center; color: var(--ink-400); font-size: 13px; }
.map-svg { width: 100%; aspect-ratio: 1/1; background: var(--green-50); border-radius: 12px; touch-action: manipulation; }
.map-dot { cursor: pointer; }
.map-legend { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }
.lg-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--ink-600); }
.lg-item i { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.map-picked { margin-top: 10px; background: var(--green-50); border-radius: 10px; padding: 10px 12px;
  display: flex; flex-direction: column; gap: 2px; cursor: pointer; }
.map-picked b { font-size: 14px; color: var(--ink-900); }
.map-picked span { font-size: 12px; color: var(--ink-600); font-variant-numeric: tabular-nums; }
.map-picked em { font-size: 11px; color: var(--green-text); font-style: normal; }
</style>
