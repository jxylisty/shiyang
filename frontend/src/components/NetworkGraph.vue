<script setup>
// 成分-靶点网络图（ECharts graph 力导向）
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'
import { getNetwork } from '../api'

const props = defineProps({ recipeId: [String, Number] })
const el = ref(null)
const empty = ref(false)
let chart = null

const COLORS = ['#2e7d5b', '#c98a2d', '#5b7fa6']

async function render() {
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
  } catch { empty.value = true }
}

onMounted(render)
watch(() => props.recipeId, render)
onBeforeUnmount(() => { chart?.dispose() })
defineExpose({ resize: () => chart?.resize() })
</script>

<template>
  <div>
    <div v-if="empty" class="net-empty">网络图数据不足</div>
    <div v-show="!empty" ref="el" class="net-chart"></div>
  </div>
</template>

<style scoped>
.net-chart { width: 100%; height: 320px; }
.net-empty { text-align: center; color: #8a978f; font-size: 13px; padding: 40px 0; }
</style>
