<script setup>
/**
 * 迷你化学空间图组件：入血概率着色的 UMAP 散点预览卡
 * - 用在成分词典页顶部，给用户一个"整体分布感"的视觉钩子
 * - 点击卡片跳转 /chem-map 完整页（模式切换/成分详情都在那边）
 * - 数据来自 getChemMap()，只展示不交互，保持轻量
 *
 * props: none（自己拉数据；将来要外灌数据再加 items prop）
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getChemMap } from '../api'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const loadError = ref(false)

const PROB_LEGEND = [
  { c: 'var(--green-900)', t: '≥0.9 很高' },
  { c: 'var(--green-700)', t: '0.7–0.9 较高' },
  { c: 'var(--amber-600)', t: '0.5–0.7 中等' },
  { c: 'var(--red-500)', t: '<0.5 偏低' },
]

function colorOf(it) {
  const p = it.prob_cctcm ?? 0
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
  try {
    const d = (await getChemMap()).data.data
    items.value = d.items || []
  } catch { loadError.value = true } finally { loading.value = false }
}

function goMap() { router.push('/chem-map') }

onMounted(load)
</script>

<template>
  <div class="mini-map-card card pressable" @click="goMap">
    <div class="mm-head">
      <div class="mm-title-row">
        <b>化学空间一览</b>
        <span class="mm-count">{{ items.length || '—' }} 个成分</span>
      </div>
      <p class="mm-hint">结构相似的成分在空间上靠得近 · 颜色越绿入血概率越高</p>
    </div>

    <div class="mm-visual">
      <div v-if="loading" class="mm-placeholder">加载中…</div>
      <div v-else-if="loadError" class="mm-placeholder">服务暂时不可用</div>
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
