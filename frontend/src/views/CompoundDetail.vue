<script setup>
// 成分词典页（对标 Examine.com 的成分条目模式）：单化合物全景
// 双模型概率 + Lipinski 特征人话解读 + 关联药材/靶点 + 出现在哪些方子
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getExplainCompound } from '../api'

const route = useRoute()
const router = useRouter()
const data = ref(null)
const loading = ref(true)
const loadError = ref(false)
const notFound = ref(false)

async function load() {
  loading.value = true
  loadError.value = false
  notFound.value = false
  try {
    const d = (await getExplainCompound(route.params.name)).data.data
    data.value = d
  } catch (e) {
    if (e?.response?.status === 404) notFound.value = true
    else loadError.value = true
  } finally { loading.value = false }
}
onMounted(load)

const probColor = (p) => p >= 0.9 ? 'var(--green-700)' : p >= 0.7 ? 'var(--amber-text)' : 'var(--ink-400)'

function goHerb(name) { router.push({ path: '/herbs', query: { h: name } }) }
function goRecipe(id) { router.push(`/recipes/${id}`) }
</script>

<template>
  <div class="page">
    <div v-if="loading">
      <div class="card"><div class="sk-line w50 sk-anim"></div><div class="sk-line w90 sk-anim"></div><div class="sk-line w70 sk-anim"></div></div>
      <div class="card"><div class="sk-line w40 sk-anim"></div><div class="sk-line w80 sk-anim"></div></div>
    </div>
    <van-empty v-else-if="notFound" image="search" description="没有找到该成分，试试在成分库中检索" />
    <van-empty v-else-if="loadError" image="error" description="服务暂时不可用，请稍后重试" />

    <template v-else-if="data">
      <!-- 1. 页头：名称 + 档位徽章 + 理化 -->
      <div class="card cd-head">
        <div class="cd-title">
          <h2>{{ data.name }}</h2>
          <span class="cd-badge" :style="{ background: data.band.color }">{{ data.band.tier }}入血可能</span>
        </div>
        <p class="cd-say">{{ data.band.say }}</p>
        <div class="cd-props">
          <span v-if="data.mw != null">MW {{ data.mw.toFixed(1) }} Da</span>
          <span v-if="data.logp != null">logP {{ data.logp.toFixed(2) }}</span>
          <span v-if="data.target_count">{{ data.target_count }} 个关联靶点</span>
        </div>
        <p class="cd-smiles" v-if="data.smiles">SMILES：<code>{{ data.smiles }}</code></p>
      </div>

      <!-- 2. 双模型概率对比 -->
      <div class="card">
        <b class="cd-sec">入血概率 · 双模型对比</b>
        <div class="cd-bars">
          <div class="cd-bar-row">
            <span class="cd-bar-label">ccTCM</span>
            <div class="cd-bar"><i :style="{ width: `${Math.round((data.prob_cctcm || 0) * 100)}%`, background: probColor(data.prob_cctcm) }"></i></div>
            <span class="cd-bar-val">{{ data.prob_cctcm ?? '—' }}</span>
          </div>
          <div class="cd-bar-row">
            <span class="cd-bar-label">HERB</span>
            <div class="cd-bar"><i :style="{ width: `${Math.round((data.prob_herb || 0) * 100)}%`, background: 'var(--amber-600)' }"></i></div>
            <span class="cd-bar-val">{{ data.prob_herb ?? '—' }}</span>
          </div>
        </div>
      </div>

      <!-- 3. Lipinski 特征解读（为什么是这个概率） -->
      <div class="card">
        <b class="cd-sec">为什么是这个概率 · Lipinski 特征解读</b>
        <p class="cd-rule">{{ data.rule_summary }}</p>
        <div v-for="f in data.features" :key="f.key" class="cd-feat" :class="{ pass: f.pass, fail: !f.pass }">
          <div class="cd-feat-head">
            <span class="cd-feat-check">{{ f.pass ? '✓' : '✗' }}</span>
            <b>{{ f.label }}</b>
            <span class="cd-feat-val">实际 {{ f.value }} / 门槛 &lt; {{ f.limit }}</span>
          </div>
          <p class="cd-feat-say">{{ f.say }}</p>
          <p class="cd-feat-why">{{ f.why }}</p>
        </div>
        <p class="cd-note">{{ data.note }}</p>
      </div>

      <!-- 4. 关联药材 -->
      <div class="card" v-if="data.herbs.length">
        <b class="cd-sec">存在于这些药材（{{ data.herbs.length }}）</b>
        <div class="cd-chips">
          <button v-for="h in data.herbs" :key="h" class="cd-chip" @click="goHerb(h)">{{ h }}</button>
        </div>
      </div>

      <!-- 5. 关联靶点 -->
      <div class="card" v-if="data.targets.length">
        <b class="cd-sec">关联靶点<span class="cd-sec-sub">（人类蛋白，前 {{ data.targets.length }} 个）</span></b>
        <div class="cd-targets">
          <div v-for="t in data.targets" :key="t.gene + t.species" class="cd-target">
            <b>{{ t.gene }}</b>
            <span>{{ t.target_type }}<template v-if="t.species"> · {{ t.species }}</template></span>
          </div>
        </div>
      </div>

      <!-- 6. 出现在哪些方子 -->
      <div class="card" v-if="data.recipes.length">
        <b class="cd-sec">喝这些方子会摄入它</b>
        <button v-for="r in data.recipes" :key="r.id" class="cd-recipe" @click="goRecipe(r.id)">
          <span class="cd-recipe-name">{{ r.name }}</span>
          <span class="cd-recipe-sub">{{ r.type }}<template v-if="r.oneliner"> · {{ r.oneliner }}</template></span>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cd-head { background: linear-gradient(135deg, var(--green-700), var(--green-900)); color: #fff; border: none; }
.cd-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.cd-title h2 { font-size: 20px; letter-spacing: .5px; }
.cd-badge { font-size: 11.5px; padding: 3px 10px; border-radius: 12px; color: #fff; }
.cd-say { font-size: 13px; opacity: .9; margin-top: 8px; }
.cd-props { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; font-size: 11.5px; }
.cd-props span { background: rgba(255,255,255,.14); border-radius: 8px; padding: 2px 9px; font-variant-numeric: tabular-nums; }
.cd-smiles { margin-top: 10px; font-size: 11px; opacity: .85; word-break: break-all; }
.cd-smiles code { font-family: monospace; }

.cd-sec { font-size: 14.5px; display: block; }
.cd-sec-sub { font-size: 11px; color: var(--ink-400); font-weight: 400; margin-left: 4px; }

.cd-bars { margin-top: 12px; display: flex; flex-direction: column; gap: 7px; }
.cd-bar-row { display: flex; align-items: center; gap: 8px; }
.cd-bar-label { width: 46px; font-size: 11px; color: var(--ink-400); font-family: monospace; }
.cd-bar { flex: 1; height: 8px; background: var(--green-50); border-radius: 4px; overflow: hidden; }
.cd-bar i { display: block; height: 100%; border-radius: 4px; }
.cd-bar-val { width: 40px; text-align: right; font-size: 11px; color: var(--ink-600); font-variant-numeric: tabular-nums; }

.cd-rule { font-size: 12px; color: var(--ink-600); margin: 8px 0 12px; }
.cd-feat { border: 1px solid var(--green-100); border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; }
.cd-feat.pass { background: var(--green-50); }
.cd-feat.fail { background: var(--amber-50); }
.cd-feat-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.cd-feat-check { font-weight: 700; }
.cd-feat.pass .cd-feat-check { color: var(--green-text); }
.cd-feat.fail .cd-feat-check { color: var(--amber-text); }
.cd-feat-val { margin-left: auto; font-size: 11px; color: var(--ink-400); font-variant-numeric: tabular-nums; }
.cd-feat-say { font-size: 12.5px; color: var(--ink-900); margin-top: 6px; line-height: 1.6; }
.cd-feat-why { font-size: 11px; color: var(--ink-400); margin-top: 3px; }
.cd-note { font-size: 11px; color: var(--ink-400); margin-top: 10px; line-height: 1.6; }

.cd-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.cd-chip { border: 1px solid var(--green-100); background: var(--green-50); color: var(--green-text);
  border-radius: 16px; padding: 5px 14px; font-size: 13px; cursor: pointer; font-family: inherit; }
.cd-chip:active { scale: .94; }

.cd-targets { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
.cd-target { background: var(--green-50); border-radius: 10px; padding: 8px 10px; display: flex; flex-direction: column; gap: 2px; }
.cd-target b { font-size: 13px; color: var(--green-text); font-family: monospace; }
.cd-target span { font-size: 10.5px; color: var(--ink-600); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 420px) { .cd-targets { grid-template-columns: 1fr; } }

.cd-recipe { display: flex; flex-direction: column; gap: 2px; width: 100%; text-align: left;
  border: none; background: none; cursor: pointer; padding: 10px 4px; border-bottom: 1px solid var(--green-100); font-family: inherit; }
.cd-recipe:last-child { border-bottom: none; }
.cd-recipe:active { background: var(--green-50); }
.cd-recipe-name { font-size: 14px; color: var(--ink-900); font-weight: 500; }
.cd-recipe-sub { font-size: 11.5px; color: var(--ink-400); }

.sk-line { height: 13px; border-radius: 6px; margin-bottom: 10px; }
.sk-line.w50 { width: 50%; } .sk-line.w90 { width: 90%; } .sk-line.w80 { width: 80%; }
.sk-line.w70 { width: 70%; margin-bottom: 0; } .sk-line.w40 { width: 40%; margin-bottom: 0; }
/* sk-anim 用全局定义（style.css） */
</style>
