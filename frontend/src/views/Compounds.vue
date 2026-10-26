<script setup>
// 成分库：按入血概率排序的化合物列表，双模型对比条 + 三维雷达分
import { ref, onMounted } from 'vue'
import { listCompounds } from '../api'

const items = ref([])
const loading = ref(true)
const loadError = ref(false)
const minProb = ref(0.5)
const barsGrown = ref(false)   // 概率条从 0 生长：数据到位后下一帧给终值

async function load() {
  loading.value = true
  loadError.value = false
  barsGrown.value = false
  try {
    const d = (await listCompounds(minProb.value, 200)).data.data
    items.value = d.items
    // 下一拍再给条形终值，让 width transition 真正从 0 播起
    // （setTimeout 替代 rAF：隐藏页签里 rAF 不触发会让条形定格 0）
    setTimeout(() => setTimeout(() => { barsGrown.value = true }, 16), 16)
  } catch {
    loadError.value = true
    items.value = []
  } finally { loading.value = false }
}
onMounted(load)

const LEVELS = [
  { label: '全部', v: 0 },
  { label: '≥0.5 较高', v: 0.5 },
  { label: '≥0.7 高', v: 0.7 },
  { label: '≥0.9 极高', v: 0.9 },
]
function pickLevel(v) { minProb.value = v; load() }

const RADAR = [
  { key: 'radar_anti_inflammatory', name: '抗炎' },
  { key: 'radar_immune_regulation', name: '免疫调节' },
  { key: 'radar_airway_repair', name: '气道修复' },
]
// 概率三档色：走令牌（ink-400 已调至 AA 对比度）
const probColor = (p) => p >= 0.9 ? 'var(--green-700)' : p >= 0.7 ? 'var(--amber-text)' : 'var(--ink-400)'
const avg = (c) => {
  const vals = RADAR.map(r => c[r.key]).filter(v => v !== null && v !== undefined)
  return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null
}
</script>

<template>
  <div class="page">
    <div class="card intro">
      <b>活性成分库</b>
      <p>来自大创课题「中药入血成分预测」的 PU-Learning 双模型（ccTCM / HERB）预测结果，入血概率越高，表示该成分被预测越可能进入血液发挥 systemic 作用。</p>
    </div>

    <div class="f-row">
      <button v-for="l in LEVELS" :key="l.v" class="tag level" :class="{ active: minProb === l.v }" @click="pickLevel(l.v)">{{ l.label }}</button>
    </div>

    <div v-if="loading">
      <div v-for="i in 6" :key="i" class="card cp-card">
        <div class="sk-line w50 sk-anim"></div>
        <div class="sk-line w90 sk-anim"></div>
        <div class="sk-line w40 sk-anim"></div>
      </div>
    </div>
    <van-empty v-else-if="loadError" image="error" description="服务暂时不可用，请稍后重试" />
    <van-empty v-else-if="!items.length" image="search" description="该概率阈值下暂无成分，调低试试" />

    <template v-else>
      <p class="count">共 {{ items.length }} 个成分 · 按入血概率排序</p>
      <router-link v-for="(c, i) in items" :key="c.id" :to="`/compounds/${encodeURIComponent(c.name)}`" class="card cp-card" :style="{ '--d': `${Math.min(i, 10) * 40}ms` }">
        <div class="cp-head">
          <span class="cp-rank">{{ i + 1 }}</span>
          <b class="cp-name">{{ c.name }}</b>
          <span class="cp-prob" :style="{ color: probColor(c.prob_cctcm) }">{{ c.prob_cctcm }}</span>
        </div>
        <!-- 双模型对比条：入场后从 0 生长到目标宽度 -->
        <div class="cp-bars">
          <div class="cp-bar-row">
            <span class="cp-bar-label">ccTCM</span>
            <div class="cp-bar"><i :style="{ width: barsGrown ? `${Math.round(c.prob_cctcm * 100)}%` : '0%', background: probColor(c.prob_cctcm) }"></i></div>
            <span class="cp-bar-val">{{ c.prob_cctcm }}</span>
          </div>
          <div class="cp-bar-row">
            <span class="cp-bar-label">HERB</span>
            <div class="cp-bar"><i :style="{ width: barsGrown ? `${Math.round(c.prob_herb * 100)}%` : '0%', background: 'var(--amber-600)' }"></i></div>
            <span class="cp-bar-val">{{ c.prob_herb }}</span>
          </div>
        </div>
        <!-- 三维雷达分 -->
        <div class="cp-radar">
          <span v-for="r in RADAR" :key="r.key" class="cp-radar-item"
                :class="{ dim: c[r.key] === null || c[r.key] === undefined }">
            {{ r.name }} <b>{{ c[r.key] != null ? Math.round(c[r.key]) : '—' }}</b>
          </span>
          <span class="cp-mw" v-if="c.mw">MW {{ Math.round(c.mw) }}</span>
        </div>
      </router-link>
      <p class="disclaimer-note">入血概率为模型预测参考值；三维评分为文献富集参考分（0-100），非临床结论。</p>
    </template>
  </div>
</template>

<style scoped>
.intro { background: linear-gradient(135deg, var(--green-700), var(--green-900)); color: #fff; border: none; }
.intro b { font-size: 16px; }
.intro p { font-size: 12.5px; opacity: .95; margin-top: 6px; line-height: 1.7; }

.f-row { display: flex; flex-wrap: wrap; gap: 0; margin-bottom: 10px; }
.level { cursor: pointer; border: 1px solid var(--green-100); background: #fff; transition: background var(--dur-fast) ease, color var(--dur-fast) ease, border-color var(--dur-fast) ease, scale var(--dur-fast) var(--ease-snap); }
.level:active { scale: 0.94; }
.level.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.count { font-size: 12px; color: var(--ink-400); margin-bottom: 8px; }

.cp-card { display: block; text-decoration: none; color: inherit; animation: rise .4s var(--ease-out-soft) backwards; animation-delay: var(--d, 0ms); }

.cp-head { display: flex; align-items: center; gap: 8px; }
.cp-rank { width: 20px; height: 20px; border-radius: 50%; background: var(--green-50); color: var(--green-700); font-size: 11px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.cp-name { flex: 1; font-size: 15px; }
.cp-prob { font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; }

.cp-bars { margin: 10px 0 8px; display: flex; flex-direction: column; gap: 5px; }
.cp-bar-row { display: flex; align-items: center; gap: 8px; }
.cp-bar-label { width: 46px; font-size: 11px; color: var(--ink-400); font-family: monospace; }
.cp-bar { flex: 1; height: 7px; background: var(--green-50); border-radius: 4px; overflow: hidden; }
.cp-bar i { display: block; height: 100%; border-radius: 4px; width: 0; transition: width var(--dur-slow) var(--ease-out-soft); }
.cp-bar-val { width: 40px; text-align: right; font-size: 11px; color: var(--ink-600); font-variant-numeric: tabular-nums; }

.cp-radar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 11px; color: var(--ink-600); }
.cp-radar-item { background: var(--green-50); border-radius: 8px; padding: 2px 8px; }
.cp-radar-item b { color: var(--green-700); }
.cp-radar-item.dim { opacity: .5; }
.cp-mw { margin-left: auto; color: var(--ink-400); font-variant-numeric: tabular-nums; }

.disclaimer-note { font-size: 11px; color: var(--ink-400); margin: 14px 4px; line-height: 1.6; }

.sk-line { height: 13px; border-radius: 6px; margin-bottom: 10px; }
.sk-line.w50 { width: 50%; }
.sk-line.w90 { width: 90%; }
.sk-line.w40 { width: 40%; margin-bottom: 0; }
/* sk-anim 用全局定义（style.css） */
</style>
