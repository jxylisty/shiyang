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
// 概率三档色：走令牌
const probColor = (p) => p >= 0.9 ? 'var(--green-700)' : p >= 0.7 ? 'var(--amber-text)' : 'var(--ink-400)'
</script>

<template>
  <div class="page">
    <div class="card intro">
      <b class="intro-title">活性成分数据图鉴</b>
      <p>数据来自南京中医药大学赵玉男老师团队自建的 <b>ccTCM 2.0</b> 数据库，入血概率由 PU-Learning 模型预测（ROC-AUC 0.903）。</p>
      <p class="intro-note">提示：入血概率表示成分<b>在血中被检出的倾向</b>，不是口服吸收率。大分子皂苷吸收率低但血中可检出，模型仍可能给高分。</p>
    </div>

    <div class="f-row">
      <button v-for="l in LEVELS" :key="l.v" class="tag level" :class="{ active: minProb === l.v }" @click="pickLevel(l.v)">{{ l.label }}</button>
    </div>

    <div v-if="loading" class="compound-list">
      <div v-for="i in 6" :key="i" class="card cp-card">
        <div class="sk-line w50 sk-anim"></div>
        <div class="sk-line w90 sk-anim"></div>
        <div class="sk-line w40 sk-anim"></div>
      </div>
    </div>
    <van-empty v-else-if="loadError" image="error" description="服务暂时不可用，请稍后重试" />
    <van-empty v-else-if="!items.length" image="search" description="该概率阈值下暂无成分，调低试试" />

    <template v-else>
      <p class="count">共 <b>{{ items.length }}</b> 个活性成分 · 按预测入血概率排序</p>
      <div class="compound-list">
        <router-link v-for="(c, i) in items" :key="c.id" :to="`/compounds/${encodeURIComponent(c.name)}`" class="card cp-card pressable" :style="{ '--d': `${Math.min(i, 10) * 40}ms` }">
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
      </div>
      <p class="disclaimer-note">入血概率为 PU-Learning 模型预测值；三维评分为 Enrichr 通路富集结果（0-100），非临床结论。</p>
    </template>
  </div>
</template>

<style scoped>
.intro {
  background: linear-gradient(135deg, #1c4d39 0%, #15382a 100%);
  color: #fff; border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 4px 16px rgba(22, 56, 42, 0.15);
}
.intro-title { font-family: var(--font-serif); font-size: 17px; letter-spacing: 0.02em; }
.intro p { font-size: 13px; opacity: .9; margin-top: 6px; line-height: 1.6; }
.intro .intro-note { font-size: 11.5px; opacity: .72; border-top: 1px solid rgba(255,255,255,.15); padding-top: 6px; margin-top: 8px; }

.f-row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 12px; }
.level {
  cursor: pointer; border: 1px solid var(--green-100); background: #fff;
  transition: all var(--dur-fast) ease;
}
.level:active { scale: 0.94; }
.level.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.count { font-size: 12.5px; color: var(--ink-400); margin-bottom: 10px; }
.count b { color: var(--ink-900); font-variant-numeric: tabular-nums; }

.compound-list { display: flex; flex-direction: column; gap: 10px; }
@media (min-width: 680px) {
  .compound-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
}

.cp-card { display: block; text-decoration: none; color: inherit; margin-bottom: 0; animation: rise .4s var(--ease-out-soft) backwards; animation-delay: var(--d, 0ms); }

.cp-head { display: flex; align-items: center; gap: 8px; }
.cp-rank {
  width: 20px; height: 20px; border-radius: 50%; background: var(--green-50);
  color: var(--green-700); font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.cp-name { flex: 1; font-size: 15px; color: var(--ink-900); font-weight: 600; }
.cp-prob { font-size: 16px; font-weight: 700; font-variant-numeric: tabular-nums; }

.cp-bars { margin: 10px 0 8px; display: flex; flex-direction: column; gap: 6px; }
.cp-bar-row { display: flex; align-items: center; gap: 8px; }
.cp-bar-label { width: 44px; font-size: 11px; color: var(--ink-400); font-family: monospace; font-weight: 600; }
.cp-bar { flex: 1; height: 7px; background: var(--green-50); border-radius: 4px; overflow: hidden; border: 1px solid rgba(0,0,0,0.03); }
.cp-bar i { display: block; height: 100%; border-radius: 4px; width: 0; transition: width var(--dur-slow) var(--ease-out-soft); }
.cp-bar-val { width: 38px; text-align: right; font-size: 11px; color: var(--ink-600); font-variant-numeric: tabular-nums; font-weight: 500; }

.cp-radar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 11px; color: var(--ink-600); }
.cp-radar-item { background: var(--green-50); border: 1px solid var(--green-100); border-radius: 6px; padding: 2px 7px; }
.cp-radar-item b { color: var(--green-700); font-variant-numeric: tabular-nums; }
.cp-radar-item.dim { opacity: .5; }
.cp-mw { margin-left: auto; color: var(--ink-400); font-variant-numeric: tabular-nums; font-size: 11px; }

.disclaimer-note { font-size: 11.5px; color: var(--ink-400); margin: 16px 4px; line-height: 1.6; }

.sk-line { height: 13px; border-radius: 6px; margin-bottom: 10px; }
.sk-line.w50 { width: 50%; }
.sk-line.w90 { width: 90%; }
.sk-line.w40 { width: 40%; margin-bottom: 0; }
</style>
