<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BadgeCheck, Clock, ExternalLink, Star, StarOff, CheckCircle2, ArrowUp } from '@lucide/vue'
import { showSuccessToast } from 'vant'
import { getRecipe, getExposure, addFavorite, removeFavorite, listFavorites, isLoggedIn, pushHistory, doCheckin, undoCheckin } from '../api'
import AIReport from '../components/AIReport.vue'
import NetworkGraph from '../components/NetworkGraph.vue'
import SharePoster from '../components/SharePoster.vue'

const route = useRoute()
const router = useRouter()
const recipe = ref(null)
const error = ref('')
const exposure = ref(null)
const favBusy = ref(false)
const favState = ref({})
const matFailed = ref({})
const checkedToday = ref(false)   // 今日打卡状态
const checkinBusy = ref(false)
const favJustPop = ref(false)     // 收藏成功 pop 弹跳
const barsGrown = ref(false)      // 三维机制条从 0 生长
const showTop = ref(false)        // 返回顶部浮钮

async function syncFavState() {
  if (!isLoggedIn()) return
  try {
    const favs = (await listFavorites()).data.data
    const map = {}
    for (const f of favs) map[f.id] = true
    favState.value = map
  } catch { /* 静默：仅影响回显 */ }
  // 今日打卡回显（近 30 天记录里 today 字段即今日已打卡的方子）
  try {
    const { listCheckins } = await import('../api')
    const data = (await listCheckins()).data.data
    checkedToday.value = data.today.includes(Number(route.params.id))
  } catch { /* 静默 */ }
}

onMounted(async () => {
  try {
    recipe.value = (await getRecipe(route.params.id)).data.data
    pushHistory({ id: recipe.value.id, name: recipe.value.name, type: recipe.value.type, oneliner: recipe.value.oneliner })
    // 下一帧再给进度条终值：让 van-progress 的 width transition 从 0 播到目标
    requestAnimationFrame(() => requestAnimationFrame(() => { barsGrown.value = true }))
  } catch { error.value = '加载失败' }
  getExposure(route.params.id).then(({ data }) => { exposure.value = data.data }).catch(() => {})
  syncFavState()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

function onScroll() {
  showTop.value = window.scrollY > 600
}
function backTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const fmtGrams = (m) => m.grams ? `${m.grams}g` : (m.note?.includes('未标克数') ? '适量' : '适量*')

// 配料图片：构建期预拉取到 /img/materials/{name}.jpg（Wikimedia Commons，许可见页脚）
// 没有图的物料 img 加载失败时隐藏占位、显示首字方块
const matImg = (name) => `/img/materials/${encodeURIComponent(name)}.jpg`
const hideImg = (e) => { e.target.style.display = 'none' }
const matLoaded = ref({})
const onMatLoad = (name) => { matLoaded.value[name] = true }
const probColor = (p) => p >= 0.9 ? '#2e7d5b' : p >= 0.7 ? '#c98a2d' : '#8a978f'
const radarNames = { anti_inflammatory: '抗炎', immune_regulation: '免疫调节', airway_repair: '气道修复' }
// 三维均值可能带小数，条形图按 0-100 取整
const radarSummary = computed(() => {
  const r = recipe.value?.analysis?.radar_summary
  return r || null
})

function gotoLogin() {
  router.push({ path: '/login', query: { redirect: route.fullPath } })
}

function buzz(ms) {
  try { navigator.vibrate?.(ms) } catch { /* 不支持则静默 */ }
}

async function toggleFav() {
  if (!isLoggedIn()) { gotoLogin(); return }
  if (favBusy.value) return
  favBusy.value = true
  try {
    const id = Number(route.params.id)
    if (favState.value[id]) { await removeFavorite(id); favState.value[id] = false }
    else {
      await addFavorite(id); favState.value[id] = true
      // 收藏成功：star pop + 轻触觉 + toast（与打卡反馈对称）
      favJustPop.value = true
      buzz(10)
      showSuccessToast('已加入收藏 ★')
      setTimeout(() => { favJustPop.value = false }, 500)
    }
  } catch (e) {
    if (e?.response?.status === 401) gotoLogin()
  } finally { favBusy.value = false }
}

async function toggleCheckin() {
  if (!isLoggedIn()) { gotoLogin(); return }
  if (checkinBusy.value) return
  checkinBusy.value = true
  try {
    const id = Number(route.params.id)
    if (checkedToday.value) { await undoCheckin(id); checkedToday.value = false }
    else { await doCheckin(id); checkedToday.value = true; buzz(10); showSuccessToast('今日已打卡 ✓') }
  } catch (e) {
    if (e?.response?.status === 401) gotoLogin()
  } finally { checkinBusy.value = false }
}
</script>

<template>
  <div class="page">
    <van-empty v-if="error" image="error" :description="error" />

    <!-- 加载骨架：recipe 为 null 且未出错时的占位（此前整页空白） -->
    <template v-else-if="!recipe">
      <div class="card">
        <div class="skl" style="height: 22px; width: 60%;"></div>
        <div class="skl" style="height: 14px; width: 90%; margin-top: 12px;"></div>
        <div class="skl" style="height: 30px; width: 70%; margin-top: 14px; border-radius: 15px;"></div>
      </div>
      <div class="card" v-for="n in 2" :key="n">
        <div class="skl mat-skl" v-for="m in 4" :key="m">
          <span class="skl mat-skl-img"></span>
          <span class="skl" style="flex: 1; height: 15px;"></span>
          <span class="skl" style="width: 34px; height: 13px;"></span>
        </div>
      </div>
    </template>

    <template v-else>
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
                <span class="fav-star" :class="{ pop: favJustPop }">
                  <Star v-if="!favState[Number($route.params.id)]" :size="14" :stroke-width="2.2" />
                  <StarOff v-else :size="14" :stroke-width="2.2" style="fill: var(--amber-600); color: var(--amber-600);" />
                </span>
                {{ favState[Number($route.params.id)] ? '取消收藏' : '收藏' }}
              </button>
              <button class="btn h-checkin" :class="{ done: checkedToday }" @click="toggleCheckin">
                <CheckCircle2 :size="14" :stroke-width="2.2" />
                {{ checkedToday ? '今日已打卡' : '今日打卡' }}
              </button>
              <SharePoster :recipe-id="route.params.id" />
            </div>
          </div>

          <!-- 配方 -->
          <div class="section-title">配方</div>
          <div class="card">
            <div v-for="(m, mi) in recipe.materials" :key="m.name" class="mat" :style="{ '--i': mi }">
              <img v-if="!matFailed[m.name]" :src="matImg(m.name)" :alt="m.name" class="m-img" :class="{ loaded: matLoaded[m.name] }" loading="lazy"
                   @load="onMatLoad(m.name)" @error="matFailed[m.name] = true" />
              <div v-else class="m-img m-img-fallback">{{ m.name[0] }}</div>
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
              <div v-for="(c, i) in recipe.analysis.top_compounds" :key="c.name" class="comp" :style="{ '--i': i }">
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
                  <van-progress class="r-bar" :percentage="barsGrown ? Math.round(v) : 0" color="#359068" track-color="#eef7f2" :show-pivot="false" />
                  <span class="r-val">{{ barsGrown ? Math.round(v) : 0 }}</span>
                </div>
                <p class="r-scope">三维维度沿用大创课题「中医治疗儿童哮喘」机制研究的靶点富集框架，此处作为成分生物活性的一般性参考，不代表该方对任一具体场景的功效评价。</p>
              </div>

              <p class="a-targets" v-if="recipe.analysis.top_targets?.length">
                主要关联人类蛋白靶点：{{ recipe.analysis.top_targets.map(t => t.gene).join('、') }}
              </p>
              <p class="a-disclaimer">入血概率为 PU-Learning 模型预测值；三维评分沿用大创课题靶点富集框架（抗炎/免疫/气道修复），为文献富集参考分而非临床结论。</p>
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

      <!-- 返回顶部浮钮（长页移动端） -->
      <Transition name="fade-up">
        <button v-if="showTop" class="back-top" @click="backTop" aria-label="返回顶部">
          <ArrowUp :size="18" :stroke-width="2.2" />
        </button>
      </Transition>
    </template>
  </div>
</template>

<style scoped>
.detail-grid { display: block; }
@media (min-width: 900px) {
  .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 20px; align-items: start; }
  .col-side { position: sticky; top: 74px; }
}

/* 加载骨架 */
.mat-skl { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
.mat-skl-img { width: 44px; height: 44px; border-radius: 10px; flex-shrink: 0; }

.h-top { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.h-top h2 { font-size: 20px; }
.h-one { font-size: 13px; color: var(--ink-600); margin: 6px 0; }
.tag.lab { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.h-ops { display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.h-ops .h-fav { display: inline-flex; align-items: center; gap: 5px; }
.fav-star { display: inline-flex; }
.fav-star.pop { animation: pop 0.45s var(--ease-spring); }
.h-ops .h-checkin { display: inline-flex; align-items: center; gap: 5px; background: var(--green-700); color: #fff; transition: background var(--dur-fast) ease, color var(--dur-fast) ease; }
.h-ops .h-checkin.done { background: var(--green-100); color: var(--green-700); }

/* 配料行入场错峰 + 图片懒加载淡入 */
.mat { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed var(--green-50); gap: 10px; animation: rise .4s var(--ease-out-soft) backwards; animation-delay: calc(var(--i) * 40ms); }
.mat:last-of-type { border-bottom: none; }
.m-img { width: 44px; height: 44px; border-radius: 10px; object-fit: cover; flex-shrink: 0; background: var(--green-50); opacity: 0; scale: 0.92; transition: opacity .35s ease, scale .35s var(--ease-snap); }
.m-img.loaded { opacity: 1; scale: 1; }
.m-img-fallback { display: flex; align-items: center; justify-content: center; font-size: 17px; font-weight: 700; color: var(--green-700); opacity: 1; scale: 1; }
.m-main { flex: 1; }
.m-name { font-size: 15px; font-weight: 600; }
.m-kind { font-size: 10px; padding: 1px 7px; border-radius: 8px; background: var(--green-100); color: var(--green-700); margin-left: 8px; }
.m-grams { font-size: 13px; color: var(--ink-600); }
.m-note { font-size: 11px; color: var(--ink-400); margin-top: 8px; }

.method { font-size: 14px; }
.duration { font-size: 12px; color: var(--ink-400); margin-top: 6px; }
.warn-box { margin-top: 10px; padding: 8px 12px; background: var(--red-50); border-radius: 8px; color: var(--red-500); font-size: 13px; }

.a-intro { font-size: 13px; color: var(--ink-600); margin-bottom: 10px; }
.comp { padding: 8px 0; border-bottom: 1px dashed var(--green-50); animation: rise .4s var(--ease-out-soft) backwards; animation-delay: calc(var(--i) * 35ms); }
.c-line1 { display: flex; align-items: center; gap: 8px; }
.c-rank { width: 18px; height: 18px; border-radius: 50%; background: var(--green-50); color: var(--green-700); font-size: 11px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.c-name { flex: 1; font-size: 14px; font-weight: 600; }
.c-prob { font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
.c-line2 { font-size: 11px; color: var(--ink-400); margin: 3px 0 0 26px; }
.c-radar { margin-left: 8px; color: var(--green-700); }

.radar-box { margin-top: 14px; background: var(--green-50); border-radius: 10px; padding: 12px; }
.r-title { font-size: 12px; font-weight: 700; color: var(--green-700); margin-bottom: 8px; }
.r-scope { font-size: 10.5px; color: var(--ink-400); margin-top: 8px; line-height: 1.5; }
.r-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
.r-name { width: 56px; font-size: 12px; color: var(--ink-600); }
.r-bar { flex: 1; }
.r-bar :deep(.van-progress__portion) { border-radius: 4px; transition: width var(--dur-slow) var(--ease-out-soft); }
.r-val { width: 36px; text-align: right; font-size: 12px; font-variant-numeric: tabular-nums; }

.a-targets { font-size: 12px; color: var(--ink-600); margin-top: 12px; }
.a-disclaimer { font-size: 11px; color: var(--ink-400); margin-top: 10px; line-height: 1.5; }

.source p { font-size: 13px; color: var(--ink-600); }
.source a { font-size: 13px; color: var(--green-700); text-decoration: none; display: inline-block; margin-top: 4px; }

/* 返回顶部 */
.back-top {
  position: fixed; right: max(16px, calc(50% - 375px + 16px)); bottom: 28px; z-index: 30;
  width: 42px; height: 42px; border: none; border-radius: 50%;
  background: var(--card); color: var(--green-700); box-shadow: 0 4px 14px rgba(31, 74, 56, 0.18);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  transition: scale var(--dur-fast) var(--ease-snap);
}
.back-top:active { scale: 0.9; }
.fade-up-enter-active, .fade-up-leave-active { transition: opacity .25s ease, transform .25s var(--ease-out-soft); }
.fade-up-enter-from, .fade-up-leave-to { opacity: 0; transform: translateY(10px); }
</style>
