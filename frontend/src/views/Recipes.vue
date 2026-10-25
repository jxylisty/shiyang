<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { BadgeCheck, FlaskConical, ShieldAlert } from '@lucide/vue'
import { listRecipes, matImg, getSafetyProfiles, safetyCheckBatch } from '../api'
import TermCard from '../components/TermCard.vue'

const route = useRoute()
const items = ref([])
const total = ref(0)
const loading = ref(true)
const loadError = ref(false)
const type = ref('')
const scene = ref(route.query.scene || '')
const kw = ref(route.query.q || '')

// ---- 慢病安全滤镜（T1-5）：人群模式 ----
const profiles = ref([])
const profile = ref(localStorage.getItem('shiyang_safety_profile') || '')
const safetyMap = ref({})   // {rid: {verdict, blocks, warns, profile_name}}

function pickProfile(code) {
  profile.value = profile.value === code ? '' : code
  localStorage.setItem('shiyang_safety_profile', profile.value)
  runSafety()
}

async function runSafety() {
  if (!profile.value || !items.value.length) { safetyMap.value = {}; return }
  try {
    const { data } = await safetyCheckBatch(items.value.map(r => r.id), profile.value)
    safetyMap.value = data.data.results
  } catch { safetyMap.value = {} }
}

const SCENES = ['护嗓润喉', '熬夜护眼', '换季调理', '助眠', '消化', '控糖轻养', '控油祛痘', '久坐通气', '情绪舒压', '经期温养']

let searchTimer = null
async function load() {
  loading.value = true
  loadError.value = false
  try {
    const params = { size: 100 }
    if (type.value) params.type = type.value
    if (scene.value) params.scene = scene.value
    if (kw.value.trim()) params.q = kw.value.trim()
    const d = (await listRecipes(params)).data.data
    items.value = d.items
    total.value = d.total
    runSafety()
  } catch {
    loadError.value = true
    items.value = []
  } finally { loading.value = false }
}

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 300)
}

onMounted(load)
watch(() => route.query.scene, (s) => { scene.value = s || ''; load() })
// 人群档案清单加载一次
getSafetyProfiles().then(({ data }) => { profiles.value = data.data.items }).catch(() => {})
function pickScene(s) { scene.value = scene.value === s ? '' : s; load() }
function pickType(t) { type.value = type.value === t ? '' : t; load() }

// 封面：首味配料图，加载失败换次味，全失败落品牌渐变兜底
function coverOf(r) {
  return r.materials?.length ? matImg(r.materials[0]) : ''
}
function onCoverErr(r) {
  r._try = (r._try ?? 0) + 1
  r._cover = r._try < (r.materials?.length || 0) ? matImg(r.materials[r._try]) : ''
}
</script>

<template>
  <div class="page">
    <!-- 节气推荐（T2-9） -->
    <TermCard style="margin-bottom: 12px;" />

    <van-search v-model="kw" placeholder="搜方子名，如：金银花 / 助眠" @update:model-value="onSearch" class="search-box" />

    <div class="filters">
      <div class="f-row">
        <button class="tag" :class="{ active: !type }" @click="pickType('')">全部</button>
        <button class="tag" :class="{ active: type === '茶饮' }" @click="pickType('茶饮')">茶饮</button>
        <button class="tag" :class="{ active: type === '药膳' }" @click="pickType('药膳')">药膳</button>
      </div>
      <div class="f-row">
        <button v-for="s in SCENES" :key="s" class="tag" :class="{ active: scene === s }" @click="pickScene(s)">{{ s }}</button>
      </div>
    </div>

    <p class="count" v-if="!loading && !loadError">共 {{ total }} 方
      <router-link to="/recipes/compare" class="lab-link"><FlaskConical :size="13" :stroke-width="2.2" /> 对比实验室</router-link>
    </p>

    <!-- 人群安全滤镜 -->
    <div class="f-row safety-row" v-if="profiles.length">
      <span class="safety-label"><ShieldAlert :size="13" :stroke-width="2.2" /> 我属于</span>
      <button v-for="p in profiles" :key="p.code" class="tag safety-tag"
              :class="{ active: profile === p.code }" @click="pickProfile(p.code)">{{ p.name }}</button>
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading" class="recipe-list">
      <div v-for="i in 6" :key="i" class="card recipe-card sk-card">
        <div class="sk-cover sk-anim"></div>
        <div class="rc-main">
          <div class="sk-line w60 sk-anim"></div>
          <div class="sk-line w90 sk-anim"></div>
          <div class="sk-line w40 sk-anim"></div>
        </div>
      </div>
    </div>
    <van-empty v-else-if="loadError" image="error" description="服务暂时不可用，请稍后重试" />
    <van-empty v-else-if="!items.length" image="search" description="这个组合下暂无方子，换个筛选试试" />

    <div v-else class="recipe-list">
      <router-link v-for="(r, i) in items" :key="r.id" :to="`/recipes/${r.id}`"
                   class="card recipe-card with-cover pressable" :style="{ '--i': i, '--d': `${Math.min(i, 12) * 40}ms` }"
                   :class="{ 'safety-block': safetyMap[r.id]?.verdict === 'block' }">
        <div class="rc-cover" :class="{ 'rc-cover-fb': r.type === '药膳' }">
          <img v-if="r._cover !== ''" :src="r._cover || coverOf(r)" alt="" loading="lazy" @error="onCoverErr(r)" />
          <span v-else class="rc-cover-fallback">{{ (r.materials?.[0] || r.name)[0] }}</span>
          <span class="rc-type">{{ r.type }}</span>
        </div>
        <div class="rc-main">
          <div class="rc-top">
            <span class="rc-name">{{ r.name }}</span>
          </div>
          <p class="rc-one">{{ r.oneliner }}</p>
          <div v-if="safetyMap[r.id]?.verdict === 'block'" class="rc-safety block">
            <ShieldAlert :size="12" /> {{ safetyMap[r.id].blocks[0].reason }}<span v-if="safetyMap[r.id].blocks.length > 1"> 等</span>
          </div>
          <div v-else-if="safetyMap[r.id]?.verdict === 'warn'" class="rc-safety warn">
            <ShieldAlert :size="12" /> {{ safetyMap[r.id].warns[0].reason }}<span v-if="safetyMap[r.id].warns.length > 1"> 等</span>
          </div>
          <div class="rc-bottom">
            <span v-for="s in r.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
            <span v-if="r.duration" class="rc-dur">{{ r.duration }}</span>
            <span v-if="r.analysis_ready" class="tag lab"><BadgeCheck :size="12" :stroke-width="2.4" /> 成分分析</span>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.search-box { margin-bottom: 10px; padding: 0; background: transparent; }
.filters { margin-bottom: 12px; }
.f-row { display: flex; flex-wrap: wrap; gap: 0; margin-bottom: 6px; }
.f-row .tag { cursor: pointer; border: 1px solid var(--green-100); background: #fff; transition: background var(--dur-fast) ease, color var(--dur-fast) ease, border-color var(--dur-fast) ease, scale var(--dur-fast) var(--ease-snap); }
.f-row .tag:active { scale: 0.94; }
/* 与 .f-row .tag 同特异性且需在其后声明，否则选中态的白底白字会让文字消失 */
.f-row .tag.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.count { font-size: 12px; color: var(--ink-400); margin-bottom: 8px; }
.lab-link { float: right; font-size: 12px; color: var(--green-700); text-decoration: none; display: inline-flex; align-items: center; gap: 3px; }
.safety-row { align-items: center; margin-bottom: 10px; padding: 8px 10px; background: var(--amber-50); border-radius: 10px; }
.safety-label { font-size: 12px; color: var(--amber-600); display: inline-flex; align-items: center; gap: 3px; flex-shrink: 0; }
.safety-tag { background: #fff; }
.safety-tag.active { background: var(--amber-600); color: #fff; border-color: var(--amber-600); }
.recipe-card.safety-block { opacity: .55; }
.rc-safety { font-size: 11px; margin: 0 0 6px; padding: 4px 8px; border-radius: 8px; display: flex; align-items: center; gap: 4px; line-height: 1.4; }
.rc-safety.block { background: var(--red-50); color: var(--red-500); }
.rc-safety.warn { background: var(--amber-50); color: var(--amber-600); }
.recipe-card { display: block; text-decoration: none; color: inherit; }

/* 左图右文卡片 */
.recipe-card.with-cover { display: flex; padding: 12px; gap: 12px; align-items: stretch; }
.rc-cover {
  position: relative; width: 86px; min-height: 86px; border-radius: 10px; overflow: hidden;
  background: linear-gradient(135deg, var(--green-600), var(--green-900)); flex-shrink: 0;
}
.rc-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.rc-cover-fb { background: linear-gradient(135deg, var(--amber-600), #8a5a1d); }
.rc-cover-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 30px; font-weight: 700; color: rgba(255,255,255,.9); }
.rc-type {
  position: absolute; left: 0; bottom: 0; font-size: 10px; color: #fff;
  background: rgba(29, 74, 56, 0.75); padding: 1px 7px; border-radius: 0 8px 0 0;
}
.rc-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.rc-top { display: flex; align-items: center; justify-content: space-between; }
.rc-name { font-size: 16px; font-weight: 700; }
.rc-one { font-size: 13px; color: var(--ink-600); margin: 4px 0 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.rc-bottom { margin-top: auto; display: flex; flex-wrap: wrap; align-items: center; gap: 2px; }
.rc-dur { font-size: 11px; color: var(--ink-400); margin-left: auto; flex-shrink: 0; }
.tag.lab { display: inline-flex; align-items: center; gap: 3px; background: var(--green-700); color: #fff; border-color: var(--green-700); }

/* 入场动画：淡入上移，按 --d 错峰（keyframes rise 用全局定义） */
.recipe-list .recipe-card { animation: rise .4s var(--ease-out-soft) backwards; animation-delay: var(--d, 0ms); }

/* 骨架屏（shimmer 用全局 .skl 同款曲线） */
.sk-card { display: flex; gap: 12px; padding: 12px; }
.sk-cover { width: 86px; min-height: 86px; border-radius: 10px; flex-shrink: 0; }
.sk-line { height: 14px; border-radius: 6px; margin-bottom: 10px; }
.sk-line.w60 { width: 60%; }
.sk-line.w90 { width: 90%; }
.sk-line.w40 { width: 40%; margin-bottom: 0; }
.sk-anim { background: linear-gradient(90deg, var(--green-50) 25%, #e6f1ea 50%, var(--green-50) 75%); background-size: 200% 100%; animation: shimmer 1.3s infinite; }

@media (min-width: 900px) {
  .recipe-list { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .recipe-list .recipe-card { margin-bottom: 0; }
}
</style>
