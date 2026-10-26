<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { BadgeCheck, FlaskConical, ShieldAlert } from '@lucide/vue'
import AppIcon from '../components/AppIcon.vue'
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

let safetyId = 0
async function runSafety() {
  const id = ++safetyId
  if (!profile.value || !items.value.length) { safetyMap.value = {}; return }
  try {
    const { data } = await safetyCheckBatch(items.value.map(r => r.id), profile.value)
    if (id !== safetyId) return
    safetyMap.value = data.data.results
  } catch { if (id === safetyId) safetyMap.value = {} }
}

const SCENES = ['护嗓润喉', '熬夜护眼', '换季调理', '助眠', '消化', '控糖轻养', '控油祛痘', '久坐通气', '情绪舒压', '经期温养']

let searchTimer = null
let reqId = 0
async function load() {
  const id = ++reqId
  loading.value = true
  loadError.value = false
  try {
    const params = { size: 100 }
    if (type.value) params.type = type.value
    if (scene.value) params.scene = scene.value
    if (kw.value.trim()) params.q = kw.value.trim()
    const d = (await listRecipes(params)).data.data
    if (id !== reqId) return   // 已有更新的请求发出，丢弃本次结果
    items.value = d.items
    total.value = d.total
    runSafety()
  } catch {
    if (id !== reqId) return
    loadError.value = true
    items.value = []
  } finally { if (id === reqId) loading.value = false }
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
function coverSrc(r) {
  if (r._cover === '') return ''
  return r._cover || coverOf(r)
}
function onCoverErr(r) {
  r._try = (r._try ?? 0) + 1
  r._cover = r._try < (r.materials?.length || 0) ? matImg(r.materials[r._try]) : ''
}
</script>

<template>
  <div class="page">
    <!-- 节气推荐（T2-9） -->
    <TermCard style="margin-bottom: 14px;" />

    <div class="filter-card card">
      <van-search v-model="kw" placeholder="搜方子名、体质需求或药材（如：金银花 / 润肺）" @update:model-value="onSearch" class="search-box" />

      <div class="filters">
        <div class="f-row f-type">
          <button class="seg-btn" :class="{ active: !type }" @click="pickType('')">全部</button>
          <button class="seg-btn" :class="{ active: type === '茶饮' }" @click="pickType('茶饮')"><AppIcon name="tea" :size="14" /> 茶饮</button>
          <button class="seg-btn" :class="{ active: type === '药膳' }" @click="pickType('药膳')"><AppIcon name="dish" :size="14" /> 药膳</button>
        </div>
        <div class="f-row f-scenes">
          <button v-for="s in SCENES" :key="s" class="tag" :class="{ active: scene === s }" @click="pickScene(s)">{{ s }}</button>
        </div>
      </div>

      <!-- 人群安全滤镜 -->
      <div class="safety-row" v-if="profiles.length">
        <span class="safety-label"><ShieldAlert :size="13" :stroke-width="2.2" /> 慢病安全滤镜：</span>
        <div class="safety-tags">
          <button v-for="p in profiles" :key="p.code" class="tag safety-tag"
                  :class="{ active: profile === p.code }" @click="pickProfile(p.code)">{{ p.name }}</button>
        </div>
      </div>
    </div>

    <div class="list-head" v-if="!loading && !loadError">
      <span class="count">共 <b>{{ total }}</b> 款食养方</span>
      <router-link to="/recipes/compare" class="lab-link">
        <FlaskConical :size="13" :stroke-width="2.2" /> 对比实验室
      </router-link>
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
        <div class="rc-cover">
          <img v-if="coverSrc(r)" :src="coverSrc(r)" alt="" loading="lazy" @error="onCoverErr(r)" />
          <span v-else class="rc-cover-fallback"><AppIcon :name="r.type === '药膳' ? 'dish' : 'tea'" :size="32" /></span>
          <span class="rc-type">{{ r.type }}</span>
        </div>
        <div class="rc-main">
          <div class="rc-top">
            <span class="rc-name">{{ r.name }}</span>
            <span v-if="r.duration" class="rc-dur">{{ r.duration }}</span>
          </div>
          <p class="rc-one">{{ r.oneliner }}</p>
          <div v-if="r.materials?.length" class="rc-mats">
            <span>配料：</span>{{ r.materials.slice(0, 4).join(' · ') }}
          </div>
          <div v-if="safetyMap[r.id]?.verdict === 'block'" class="rc-safety block">
            <ShieldAlert :size="12" /> {{ safetyMap[r.id].blocks[0].reason }}<span v-if="safetyMap[r.id].blocks.length > 1"> 等</span>
          </div>
          <div v-else-if="safetyMap[r.id]?.verdict === 'warn'" class="rc-safety warn">
            <ShieldAlert :size="12" /> {{ safetyMap[r.id].warns[0].reason }}<span v-if="safetyMap[r.id].warns.length > 1"> 等</span>
          </div>
          <div class="rc-bottom">
            <span v-for="s in r.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
            <span v-if="r.analysis_ready" class="tag lab"><BadgeCheck :size="12" :stroke-width="2.4" /> 成分有据</span>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.filter-card { padding: 14px; margin-bottom: 12px; }
.search-box { margin-bottom: 12px; padding: 0; background: transparent; }
.filters { margin-bottom: 6px; }

.f-type {
  display: inline-flex; background: var(--green-50); border: 1px solid var(--green-100);
  border-radius: 20px; padding: 2px; margin-bottom: 10px;
}
.seg-btn {
  display: inline-flex; align-items: center; gap: 4px;
  border: none; background: transparent; padding: 5px 14px; font-size: 13px; font-weight: 600;
  border-radius: 16px; color: var(--ink-600); cursor: pointer;
  transition: all var(--dur-fast) ease;
}
.seg-btn.active {
  background: #fff; color: var(--green-text); font-weight: 600;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
:root[data-theme="dark"] .seg-btn.active { background: var(--card); color: var(--green-600); }

.f-scenes { display: flex; flex-wrap: wrap; gap: 2px; margin-bottom: 4px; }
.f-scenes .tag {
  cursor: pointer; border: 1px solid var(--green-100); background: #fff;
  transition: all var(--dur-fast) ease;
}
.f-scenes .tag.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }

.safety-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-top: 10px; padding: 8px 12px; background: var(--amber-50);
  border: 1px solid rgba(194, 131, 40, 0.15); border-radius: 10px;
}
.safety-label { font-size: 11.5px; color: var(--amber-text); display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; font-weight: 600; }
.safety-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.safety-tag { background: #fff; border-color: rgba(194, 131, 40, 0.2); }
.safety-tag.active { background: var(--amber-600); color: #fff; border-color: var(--amber-600); }

.list-head {
  display: flex; align-items: center; justify-content: space-between;
  margin: 14px 2px 10px; font-size: 13px; color: var(--ink-400);
}
.list-head b { color: var(--ink-900); font-variant-numeric: tabular-nums; }
.lab-link {
  font-size: 12.5px; color: var(--green-text); text-decoration: none;
  display: inline-flex; align-items: center; gap: 4px; font-weight: 500;
  background: var(--green-50); padding: 3px 10px; border-radius: 12px;
  border: 1px solid var(--green-100);
}

.recipe-list { display: flex; flex-direction: column; gap: 12px; }
.recipe-card { display: block; text-decoration: none; color: inherit; margin-bottom: 0; }
.recipe-card.safety-block { opacity: .55; }
.recipe-card.with-cover { display: flex; padding: 14px; gap: 14px; align-items: stretch; }

.rc-cover {
  position: relative; width: 96px; min-height: 96px; border-radius: 12px; overflow: hidden;
  background: var(--green-100); flex-shrink: 0; border: 1px solid rgba(0,0,0,0.03);
}
.rc-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.rc-cover-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--tile-ink); }
.rc-type {
  position: absolute; left: 0; bottom: 0; font-size: 10px; color: #fff;
  background: rgba(22, 56, 42, 0.82); padding: 1px 7px; border-radius: 0 8px 0 0;
  backdrop-filter: blur(4px);
}

.rc-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.rc-top { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.rc-name { font-family: var(--font-serif); font-size: 17px; font-weight: 700; color: var(--ink-900); letter-spacing: 0.02em; }
.rc-dur { font-size: 11px; color: var(--ink-400); flex-shrink: 0; }
.rc-one {
  font-size: 13px; color: var(--ink-600); margin: 3px 0 6px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.rc-mats {
  font-size: 11.5px; color: var(--ink-600); margin-bottom: 6px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; opacity: 0.85;
}
.rc-mats span { color: var(--ink-400); }

.rc-safety { font-size: 11px; margin: 0 0 6px; padding: 4px 8px; border-radius: 8px; display: flex; align-items: center; gap: 4px; line-height: 1.4; }
.rc-safety.block { background: var(--red-50); color: var(--red-text); }
.rc-safety.warn { background: var(--amber-50); color: var(--amber-text); }

.rc-bottom { margin-top: auto; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.tag.lab {
  display: inline-flex; align-items: center; gap: 3px; background: var(--green-50);
  color: var(--green-text); border-color: var(--green-100); font-weight: 500;
}

/* 骨架屏 */
.sk-card { display: flex; gap: 14px; padding: 14px; }
.sk-cover { width: 96px; min-height: 96px; border-radius: 12px; flex-shrink: 0; }
.sk-line { height: 14px; border-radius: 6px; margin-bottom: 10px; }
.sk-line.w60 { width: 60%; }
.sk-line.w90 { width: 90%; }
.sk-line.w40 { width: 40%; margin-bottom: 0; }

/* 响应式多列网格：680px 起采用双列，彻底解决宽屏横向拉伸大片空白！ */
@media (min-width: 680px) {
  .recipe-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
}
</style>
