<script setup>
// 成分-靶点网络图（ECharts graph 力导向）
import { ref, onMounted, onBeforeUnmount, watch, watchEffect } from 'vue'
import * as echarts from 'echarts'
import { getNetwork } from '../api'

const props = defineProps({ recipeId: [String, Number] })
const el = ref(null)
const empty = ref(false)
const loading = ref(true)
const ready = ref(false)   // 图首次渲染后容器淡入
let chart = null
let ro = null

const COLORS = ['#2e7d5b', '#c98a2d', '#5b7fa6']

async function render() {
  loading.value = true
  ready.value = false
  try {
    const { data } = await getNetwork(props.recipeId)
    const d = data.data
    if (!d.nodes || d.nodes.length <= 1) { empty.value = true; return }
    empty.value = false
    if (!chart) chart = echarts.init(el.value)
    chart.setOption({
      tooltip: { confine: true, formatter: (p) => p.dataType === 'node' ? p.data.name : '' },
      legend: { data: d.legend, bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11, color: '#55645d' } },
      series: [{
        type: 'graph', layout: 'force', roam: true, draggable: true,
        force: { repulsion: 130, edgeLength: [40, 90], gravity: 0.08 },
        categories: d.legend.map((name) => ({ name })),
        color: COLORS,
        label: { show: true, fontSize: 10, color: '#1f2b26', formatter: (p) => p.data.name.length > 8 ? p.data.name.slice(0, 8) + '…' : p.data.name },
        data: d.nodes.map((n) => ({ ...n, symbolSize: n.value })),
        links: d.edges.map((e) => ({ source: e.source, target: e.target, lineStyle: { color: '#c3d8cd', width: 1 } })),
      }],
    })
    requestAnimationFrame(() => { ready.value = true })
  } catch { empty.value = true }
  finally { loading.value = false }
}

onMounted(() => {
  render()
  // 视口变化自适应（此前 expose 了 resize 但没人调，改用 ResizeObserver 内聚）
  ro = new ResizeObserver(() => chart?.resize())
  watchEffect(() => {
    const node = el.value
    if (node) ro.observe(node)
  })
})
watch(() => props.recipeId, render)
onBeforeUnmount(() => { chart?.dispose(); ro?.disconnect() })
defineExpose({ resize: () => chart?.resize() })
</script>

<template>
  <div>
    <!-- 加载占位（此前 320px 区域纯空白） -->
    <div v-if="loading" class="net-loading">
      <span class="skl net-skl-dot"></span>
      <span class="skl net-skl-dot" style="animation-delay: .15s"></span>
      <span class="skl net-skl-dot" style="animation-delay: .3s"></span>
      <p class="net-skl-text">正在布局成分网络…</p>
    </div>
    <div v-else-if="empty" class="net-empty">网络图数据不足</div>
    <div v-show="!empty && !loading" ref="el" class="net-chart" :class="{ ready }"></div>
  </div>
</template>

<style scoped>
.net-chart { width: 100%; height: 320px; opacity: 0; transition: opacity .5s ease; }
.net-chart.ready { opacity: 1; }
.net-empty { text-align: center; color: var(--ink-400); font-size: 13px; padding: 40px 0; }
.net-loading { height: 320px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; }
.net-skl-dot { width: 14px; height: 14px; border-radius: 50%; display: inline-block; }
.net-skl-text { font-size: 12px; color: var(--ink-400); }
</style>
