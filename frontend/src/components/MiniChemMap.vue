<script setup>
/**
 * 迷你化学空间图组件：入血概率着色的 UMAP 散点预览卡
 * - 用在成分词典页，给用户一个"整体分布感"的视觉钩子
 * - 点击卡片跳转 /chem-map 完整页（模式切换/成分详情都在那边）
 * - 懒加载：进视口才请求，且只要 max_points=700 的确定性抽样（全库 4,558 点会给手机白屏）
 * - 灰点 = 全库有结构但还没有入血概率预测的成分，是真实数据不是占位
 *
 * props: none（自己拉数据；将来要外灌数据再加 items prop）
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { getChemMap } from '../api'

const PREVIEW_POINTS = 700   // 预览卡点数上限：再多也看不出差别，只增加首次绘制成本

const router = useRouter()
const items = ref([])
const stats = ref(null)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref(false)
const el = ref(null)
let io = null

const PROB_LEGEND = [
  { c: 'var(--green-900)', t: '≥0.9 很高' },
  { c: 'var(--green-700)', t: '0.7–0.9 较高' },
  { c: 'var(--amber-600)', t: '0.5–0.7 中等' },
  { c: 'var(--red-500)', t: '<0.5 偏低' },
  { c: '#b9a67c', t: '外推估计' },
  { c: '#c9c1b4', t: '无预测' },
]

function colorOf(it) {
  if (it.prob == null) return '#c9c1b4'
  // HERB 外推（C 级）单独一档土黄，不与主力模型的绿/红同色
  if (it.caliber === 'herb_extrapolated') return '#b9a67c'
  const p = it.prob
  if (p >= 0.9) return 'var(--green-900)'
  if (p >= 0.7) return 'var(--green-700)'
  if (p >= 0.5) return 'var(--amber-600)'
  return 'var(--red-500)'
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

async function load() {
  if (loading.value || loaded.value) return
  loading.value = true
  try {
    const d = (await getChemMap(PREVIEW_POINTS)).data.data
    items.value = d.items || []
    stats.value = d.stats || null
    loaded.value = true
  } catch { loadError.value = true } finally { loading.value = false }
}

function goMap() { router.push('/chem-map') }

onMounted(() => {
  // 视口内才请求：成分词典首屏不该为一个装饰性图表付流量
  if (typeof IntersectionObserver === 'undefined') { load(); return }
  io = new IntersectionObserver((entries) => {
    if (entries.some(e => e.isIntersecting)) { load(); io?.disconnect(); io = null }
  }, { rootMargin: '200px' })
  if (el.value) io.observe(el.value)
})
onBeforeUnmount(() => { io?.disconnect(); io = null })
</script>

<template>
  <div ref="el" class="mini-map-card card pressable" @click="goMap">
    <div class="mm-head">
      <div class="mm-title-row">
        <b>化学空间一览</b>
        <span class="mm-count">{{ stats ? `${stats.total} 个成分` : '—' }}</span>
      </div>
      <p class="mm-hint">
        结构相似的成分在空间上靠得近 · 颜色越绿入血概率越高<template v-if="stats && stats.extrapolated"> · 土黄点为外推估计（误差较大）</template>
      </p>
    </div>

    <div class="mm-visual">
      <div v-if="loading" class="mm-placeholder">加载中…</div>
      <div v-else-if="loadError" class="mm-placeholder">服务暂时不可用</div>
      <div v-else-if="!loaded" class="mm-placeholder">滚动到此处自动加载</div>
      <svg v-else viewBox="0 0 100 100" class="mm-svg" preserveAspectRatio="xMidYMid meet" aria-label="成分化学空间分布散点图">
        <circle v-for="it in items" :key="it.name" :cx="px(it)" :cy="py(it)" r="1"
                :fill="colorOf(it)" fill-opacity="0.8" />
      </svg>
    </div>

    <div class="mm-foot">
      <div class="mm-legend">
        <span v-for="l in PROB_LEGEND" :key="l.t" class="lg-item">
          <i :style="{ background: l.c }"></i>{{ l.t }}
        </span>
      </div>
      <span class="mm-cta">查看完整地图 →</span>
    </div>
  </div>
</template>

<style scoped>
.mini-map-card {
  display: flex; flex-direction: column; gap: 10px;
  padding: 14px 14px 12px; cursor: pointer;
  /* 视觉上比普通卡稍突出一点，做"橱窗卡"感 */
  background-color: var(--card);
}
.mm-head { display: flex; flex-direction: column; gap: 2px; }
.mm-title-row { display: flex; align-items: baseline; gap: 8px; }
.mm-title-row b { font-family: var(--font-serif); font-size: 16px; color: var(--ink-900); }
.mm-count { font-size: 11px; color: var(--ink-400); }
.mm-hint { font-size: 12px; color: var(--ink-600); line-height: 1.5; margin: 0; }

.mm-visual {
  width: 100%; aspect-ratio: 2 / 1;  /* 扁宽，预览感，不是正方形大图 */
  background: var(--green-50);
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.mm-svg { width: 100%; height: 100%; display: block; }
.mm-placeholder { font-size: 12px; color: var(--ink-400); }

.mm-foot {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; flex-wrap: wrap;
}
.mm-legend { display: flex; gap: 10px; flex-wrap: wrap; }
.lg-item { display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; color: var(--ink-600); }
.lg-item i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.mm-cta {
  font-size: 11.5px; color: var(--green-text); font-weight: 500;
  white-space: nowrap;
}

@media (min-width: 680px) {
  .mini-map-card { padding: 18px; }
  .mm-title-row b { font-size: 18px; }
  .mm-visual { aspect-ratio: 3 / 1; }
}
</style>
