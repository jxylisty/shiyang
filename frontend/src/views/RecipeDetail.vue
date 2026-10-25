<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { BadgeCheck, Clock, ExternalLink, Star, StarOff } from '@lucide/vue'
import { getRecipe, getExposure, addFavorite, removeFavorite, isLoggedIn } from '../api'
import AIReport from '../components/AIReport.vue'
import NetworkGraph from '../components/NetworkGraph.vue'
import SharePoster from '../components/SharePoster.vue'

const route = useRoute()
const recipe = ref(null)
const error = ref('')
const exposure = ref(null)
const favBusy = ref(false)
const favState = ref({})

onMounted(async () => {
  try {
    recipe.value = (await getRecipe(route.params.id)).data.data
  } catch { error.value = '加载失败' }
  getExposure(route.params.id).then(({ data }) => { exposure.value = data.data }).catch(() => {})
})

const fmtGrams = (m) => m.grams ? `${m.grams}g` : (m.note?.includes('未标克数') ? '适量' : '适量*')
const probColor = (p) => p >= 0.9 ? '#2e7d5b' : p >= 0.7 ? '#c98a2d' : '#8a978f'
const radarNames = { anti_inflammatory: '抗炎', immune_regulation: '免疫调节', airway_repair: '气道修复' }
// 三维均值可能带小数，条形图按 0-100 取整
const radarSummary = computed(() => {
  const r = recipe.value?.analysis?.radar_summary
  return r || null
})

async function toggleFav() {
  if (!isLoggedIn()) { window.location.href = '/login'; return }
  if (favBusy.value) return
  favBusy.value = true
  try {
    const id = Number(route.params.id)
    if (favState.value[id]) { await removeFavorite(id); favState.value[id] = false }
    else { await addFavorite(id); favState.value[id] = true }
  } catch (e) {
    if (e?.response?.status === 401) window.location.href = '/login'
  } finally { favBusy.value = false }
}
</script>

<template>
  <div class="page">
    <van-empty v-if="error" image="error" :description="error" />
    <template v-if="recipe">
      <div class="detail-grid">
        <div class="col-main">
          <!-- 头部 -->
          <div class="card head">
            <div class="h-top">
              <h2>{{ recipe.name }}</h2>
              <span class="tag warm">{{ recipe.type }}</span>
            </div>
            <p class="h-one">{{ recipe.oneliner }}</p>
            <div class="h-tags">
              <span v-for="s in recipe.scenes" :key="s" class="tag">{{ s }}</span>
              <span v-if="recipe.analysis_ready" class="tag lab"><BadgeCheck :size="12" :stroke-width="2.4" /> 附成分分析</span>
            </div>
            <div class="h-ops">
              <button class="btn ghost h-fav" @click="toggleFav">
                <Star v-if="!favState[Number($route.params.id)]" :size="14" :stroke-width="2.2" />
                <StarOff v-else :size="14" :stroke-width="2.2" />
                {{ favState[Number($route.params.id)] ? '取消收藏' : '收藏' }}
              </button>
              <SharePoster :recipe-id="route.params.id" />
            </div>
          </div>

          <!-- 配方 -->
          <div class="section-title">配方</div>
          <div class="card">
            <div v-for="m in recipe.materials" :key="m.name" class="mat">
              <div class="m-main">
                <span class="m-name">{{ m.name }}</span>
                <span class="m-kind" :class="m.material_type">{{ m.material_type === 'herb' ? '药食同源' : '食材' }}</span>
              </div>
              <span class="m-grams">{{ fmtGrams(m) }}<small v-if="m.optional">（可选）</small></span>
            </div>
            <p v-if="recipe.materials.some(m => !m.grams)" class="m-note">* 原始来源未标注克数或写"适量"，请按口味与体质酌情增减</p>
          </div>

          <!-- 做法 -->
          <div class="section-title">做法</div>
          <div class="card">
            <p class="method">{{ recipe.method }}</p>
            <p v-if="recipe.duration" class="duration"><Clock :size="13" :stroke-width="2" /> {{ recipe.duration }}</p>
          </div>

          <!-- 适宜与禁忌 -->
          <div class="section-title">适宜 / 禁忌</div>
          <div class="card">
            <p v-if="recipe.constitutions_suitable.length"><b>适宜体质：</b>{{ recipe.constitutions_suitable.join('、') }}</p>
            <p v-if="recipe.constitutions_unsuitable.length" style="margin-top:6px"><b>不宜体质：</b>{{ recipe.constitutions_unsuitable.join('、') }}</p>
            <p style="margin-top:6px"><b>适合人群：</b>{{ recipe.population }}</p>
            <p class="warn-box">{{ recipe.contraindication }}</p>
          </div>

          <!-- 来源 -->
          <div class="section-title">数据来源</div>
          <div class="card source">
            <p>{{ recipe.source }}</p>
            <a v-if="recipe.reference_url" :href="recipe.reference_url" target="_blank" rel="noopener">查看原始出处 <ExternalLink :size="13" :stroke-width="2" /></a>
          </div>
        </div>

        <div class="col-side">
          <!-- 成分分析（核心卖点） -->
          <template v-if="recipe.analysis">
            <div class="section-title">有效成分说明书</div>
            <div class="card analysis">
              <p class="a-intro">共关联 <b>{{ recipe.analysis.compound_count }}</b> 个活性成分（来自成分库）。以下为预测入血概率 Top10：</p>
              <div v-for="(c, i) in recipe.analysis.top_compounds" :key="c.name" class="comp">
                <div class="c-line1">
                  <span class="c-rank">{{ i + 1 }}</span>
                  <span class="c-name">{{ c.name }}</span>
                  <span class="c-prob" :style="{ color: probColor(c.prob_cctcm) }">{{ c.prob_cctcm }}</span>
                </div>
                <div class="c-line2">
                  预测入血概率
                  <span v-if="c.radar && c.radar[0] !== null" class="c-radar">抗炎{{ Math.round(c.radar[0]) }} 免疫{{ Math.round(c.radar[1]) }} 气道{{ Math.round(c.radar[2]) }}</span>
                </div>
              </div>

              <div v-if="radarSummary" class="radar-box">
                <p class="r-title">三维机制参考（成分均值，满分 100）</p>
                <div v-for="(v, k) in radarSummary" :key="k" class="r-row">
                  <span class="r-name">{{ radarNames[k] || k }}</span>
                  <van-progress class="r-bar" :percentage="Math.round(v)" color="#359068" track-color="#eef7f2" :show-pivot="false" />
                  <span class="r-val">{{ Math.round(v) }}</span>
                </div>
              </div>

              <p class="a-targets" v-if="recipe.analysis.top_targets?.length">
                主要关联人类蛋白靶点：{{ recipe.analysis.top_targets.map(t => t.gene).join('、') }}
              </p>
              <p class="a-disclaimer">入血概率为 PU-Learning 模型预测值，三维评分为文献富集参考分（0-100），均为研究参考而非临床结论。</p>
            </div>

            <!-- 成分-靶点网络图 -->
            <div class="section-title">成分 - 靶点网络图</div>
            <div class="card">
              <NetworkGraph :recipe-id="route.params.id" />
              <p class="a-disclaimer">力导向布局：节点可拖拽，双指/滚轮缩放。仅展示 Top 成分与其高频靶点。</p>
            </div>
          </template>
          <div v-else class="card">
            <van-empty image="search" description="该方配料以普通食材为主，暂无成分分析（营养素视角开发中）" />
          </div>

          <!-- 暴露量估计 -->
          <template v-if="exposure && exposure.items.length">
            <div class="section-title">每杯实际摄入多少（估计）</div>
            <div class="card">
              <div v-for="(e, i) in exposure.items.slice(0, 8)" :key="e.compound + i" class="exp-row">
                <span class="e-comp">{{ e.compound }}</span>
                <span class="e-src">{{ e.herb }} {{ e.grams }}g</span>
                <span class="e-val">≈ {{ e.est_mg_min }}–{{ e.est_mg_max }} mg</span>
              </div>
              <p class="a-disclaimer">{{ exposure.note }}</p>
            </div>
          </template>

          <!-- AI 解读 -->
          <template v-if="recipe.analysis">
            <div class="section-title">AI 通俗解读</div>
            <div class="card">
              <AIReport :recipe-id="route.params.id" />
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.detail-grid { display: block; }
@media (min-width: 900px) {
  .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 20px; align-items: start; }
  .col-side { position: sticky; top: 74px; }
}

.h-top { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.h-top h2 { font-size: 20px; }
.h-one { font-size: 13px; color: var(--ink-600); margin: 6px 0; }
.tag.lab { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.h-ops { display: flex; gap: 10px; margin-top: 12px; }
.h-ops .h-fav { display: inline-flex; align-items: center; gap: 5px; }

.exp-row { display: flex; align-items: center; gap: 8px; padding: 7px 0; border-bottom: 1px dashed var(--green-50); font-size: 13px; }
.exp-row:last-of-type { border-bottom: none; }
.e-comp { flex: 1; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.e-src { font-size: 11px; color: var(--ink-400); flex-shrink: 0; }
.e-val { color: var(--green-700); font-weight: 700; flex-shrink: 0; }

.mat { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed var(--green-50); }
.mat:last-of-type { border-bottom: none; }
.m-name { font-size: 15px; font-weight: 600; }
.m-kind { font-size: 10px; padding: 1px 7px; border-radius: 8px; background: var(--green-100); color: var(--green-700); margin-left: 8px; }
.m-grams { font-size: 13px; color: var(--ink-600); }
.m-note { font-size: 11px; color: var(--ink-400); margin-top: 8px; }

.method { font-size: 14px; }
.duration { font-size: 12px; color: var(--ink-400); margin-top: 6px; }
.warn-box { margin-top: 10px; padding: 8px 12px; background: var(--red-50); border-radius: 8px; color: var(--red-500); font-size: 13px; }

.a-intro { font-size: 13px; color: var(--ink-600); margin-bottom: 10px; }
.comp { padding: 8px 0; border-bottom: 1px dashed var(--green-50); }
.c-line1 { display: flex; align-items: center; gap: 8px; }
.c-rank { width: 18px; height: 18px; border-radius: 50%; background: var(--green-50); color: var(--green-700); font-size: 11px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.c-name { flex: 1; font-size: 14px; font-weight: 600; }
.c-prob { font-size: 15px; font-weight: 700; }
.c-line2 { font-size: 11px; color: var(--ink-400); margin: 3px 0 0 26px; }
.c-radar { margin-left: 8px; color: var(--green-700); }

.radar-box { margin-top: 14px; background: var(--green-50); border-radius: 10px; padding: 12px; }
.r-title { font-size: 12px; font-weight: 700; color: var(--green-700); margin-bottom: 8px; }
.r-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
.r-name { width: 56px; font-size: 12px; color: var(--ink-600); }
.r-bar { flex: 1; }
.r-bar :deep(.van-progress__portion) { border-radius: 4px; }
.r-val { width: 36px; text-align: right; font-size: 12px; }

.a-targets { font-size: 12px; color: var(--ink-600); margin-top: 12px; }
.a-disclaimer { font-size: 11px; color: var(--ink-400); margin-top: 10px; line-height: 1.5; }

.source p { font-size: 13px; color: var(--ink-600); }
.source a { font-size: 13px; color: var(--green-700); text-decoration: none; display: inline-block; margin-top: 4px; }
</style>
