<script setup>
// 四层证据链桑基图：方子 → 药材(克重) → 活性成分(入血概率) → 作用靶点
// 与 NetworkGraph 的区别：Sankey 保留层级流向，一眼看出"哪味药贡献了哪些成分、打到哪些靶点"；
// 力导向图适合看聚类，Sankey 适合讲故事。
import { ref, onMounted, onBeforeUnmount, watch, watchEffect, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getEvidenceChain } from '../api'

const props = defineProps({ recipeId: [String, Number] })
const el = ref(null)
const empty = ref(false)
const loading = ref(true)
const ready = ref(false)
const levels = ref(['方子', '药材', '活性成分', '作用靶点'])
let chart = null
let ro = null

const THEME = {
  light: { text: '#1f2b26', sub: '#55645d' },
  dark: { text: '#e4ece7', sub: '#a3b3ab' },
}
const themeColors = () => (document.documentElement.dataset.theme === 'dark' ? THEME.dark : THEME.light)

// 按层着色：方子墨绿、药材绿、成分琥珀、靶点蓝
const LEVEL_COLORS = ['#1d4a38', '#2e7d5b', '#c98a2d', '#5b7fa6']

function buildOption(d) {
  const tc = themeColors()
  const names = d.nodes.map((n) => n.name)
  return {
    tooltip: {
      confine: true,
      formatter: (p) => {
        if (p.dataType === 'edge') return `${p.data.source} → ${p.data.target}`
        const n = d.nodes[p.dataIndex]
        const lv = levels.value[n?.depth] || ''
        const extra = n?.kind === 'herb' && n.value ? ` · ${n.value}g`
          : n?.kind === 'compound' && n.value ? ` · 入血概率 ${n.value}` : ''
        return `${lv}：${p.name}${extra}`
      },
    },
    series: [{
      type: 'sankey',
      left: 6, right: 96, top: 8, bottom: 8,
      nodeWidth: 12,
      nodeGap: 7,
      draggable: false,
      emphasis: { focus: 'adjacency' },
      data: d.nodes.map((n) => ({
        name: n.name,
        itemStyle: { color: LEVEL_COLORS[n.depth] || tc.sub },
        // 靶点/成分名较长，标签放右侧；药材放左侧更省空间
        label: {
          color: n.depth >= 2 ? tc.text : tc.sub,
          fontSize: 10,
          position: n.depth === 0 ? 'left' : 'right',
        },
      })),
      links: d.links.map((l) => ({ source: l.source, target: l.target, value: l.value })),
      label: { show: true },
      lineStyle: { color: 'gradient', opacity: 0.32, curveness: 0.5 },
      levels: [0, 1, 2, 3].map((i) => ({
        depth: i,
        itemStyle: { color: LEVEL_COLORS[i] },
        lineStyle: { color: 'gradient', opacity: 0.3 },
      })),
    }],
  }
}

async function render() {
  loading.value = true
  ready.value = false
  try {
    const { data } = await getEvidenceChain(props.recipeId)
    const d = data.data
    if (!d.nodes || d.nodes.length < 3) { empty.value = true; loading.value = false; return }
    empty.value = false
    if (d.levels) levels.value = d.levels
    // 先切到 v-else 分支让容器进 DOM，再初始化 ECharts（否则 el 为 null）
    loading.value = false
    await nextTick()
    if (!el.value) { empty.value = true; return }
    if (!chart) chart = echarts.init(el.value)
    chart.setOption(buildOption(d), true)
    requestAnimationFrame(() => { ready.value = true })
  } catch (e) { console.error('[EvidenceChain] render failed:', e); empty.value = true }
  finally { loading.value = false }
}

onMounted(() => {
  render()
  ro = new ResizeObserver(() => chart?.resize())
  watchEffect(() => { if (el.value) ro.observe(el.value) })
})
watch(() => props.recipeId, render)
onBeforeUnmount(() => { chart?.dispose(); ro?.disconnect() })
</script>

<template>
  <div>
    <div v-if="loading" class="chain-loading">
      <span class="skl chain-skl-bar"></span>
      <span class="skl chain-skl-bar" style="animation-delay:.15s"></span>
      <span class="skl chain-skl-bar" style="animation-delay:.3s"></span>
      <p class="chain-skl-text">正在串联证据链…</p>
    </div>
    <div v-else-if="empty" class="chain-empty">该方暂无足够的成分数据绘制证据链</div>
    <template v-else>
      <div class="chain-legend">
        <span v-for="(lv, i) in levels" :key="lv" class="cl-item">
          <i :style="{ background: ['#1d4a38', '#2e7d5b', '#c98a2d', '#5b7fa6'][i] }"></i>{{ lv }}
        </span>
      </div>
      <div ref="el" class="chain-chart" :class="{ ready }"></div>
    </template>
  </div>
</template>

<style scoped>
.chain-chart { width: 100%; height: 380px; opacity: 0; transition: opacity .5s ease; }
.chain-chart.ready { opacity: 1; }
.chain-legend { display: flex; gap: 14px; flex-wrap: wrap; padding: 2px 0 8px; }
.cl-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--ink-600); }
.cl-item i { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }
.chain-empty { text-align: center; color: var(--ink-400); font-size: 13px; padding: 40px 0; }
.chain-loading { height: 380px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 9px; }
.chain-skl-bar { width: 55%; height: 12px; border-radius: 6px; }
.chain-skl-text { font-size: 12px; color: var(--ink-400); }
@media (max-width: 400px) { .chain-chart { height: 340px; } }
</style>
