<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { BadgeCheck } from '@lucide/vue'
import { listRecipes } from '../api'

const route = useRoute()
const items = ref([])
const total = ref(0)
const loading = ref(true)
const loadError = ref(false)
const type = ref('')
const scene = ref(route.query.scene || '')
const kw = ref(route.query.q || '')

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
function pickScene(s) { scene.value = scene.value === s ? '' : s; load() }
function pickType(t) { type.value = type.value === t ? '' : t; load() }
</script>

<template>
  <div class="page">
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

    <p class="count" v-if="!loading && !loadError">共 {{ total }} 方</p>
    <div v-if="loading" class="empty">加载中…</div>
    <van-empty v-else-if="loadError" image="error" description="服务暂时不可用，请稍后重试" />
    <van-empty v-else-if="!items.length" image="search" description="这个组合下暂无方子，换个筛选试试" />

    <div v-else class="recipe-list">
      <router-link v-for="r in items" :key="r.id" :to="`/recipes/${r.id}`" class="card recipe-card">
        <div class="rc-top">
          <span class="rc-name">{{ r.name }}</span>
          <span class="tag warm">{{ r.type }}</span>
        </div>
        <p class="rc-one">{{ r.oneliner }}</p>
        <div class="rc-bottom">
          <span v-for="s in r.scenes" :key="s" class="tag">{{ s }}</span>
          <span v-if="r.analysis_ready" class="tag lab"><BadgeCheck :size="12" :stroke-width="2.4" /> 成分分析</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.search-box { margin-bottom: 10px; padding: 0; background: transparent; }
.filters { margin-bottom: 12px; }
.f-row { display: flex; flex-wrap: wrap; gap: 0; margin-bottom: 6px; }
.f-row .tag { cursor: pointer; border: 1px solid var(--green-100); background: #fff; }
/* 与 .f-row .tag 同特异性且需在其后声明，否则选中态的白底白字会让文字消失 */
.f-row .tag.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.count { font-size: 12px; color: var(--ink-400); margin-bottom: 8px; }
.recipe-card { display: block; text-decoration: none; color: inherit; }
@media (min-width: 900px) {
  .recipe-list { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .recipe-list .recipe-card { margin-bottom: 0; }
}
.rc-top { display: flex; align-items: center; justify-content: space-between; }
.rc-name { font-size: 16px; font-weight: 700; }
.rc-one { font-size: 13px; color: var(--ink-600); margin: 4px 0 8px; }
.rc-bottom { display: flex; flex-wrap: wrap; align-items: center; }
.tag.lab { display: inline-flex; align-items: center; gap: 3px; background: var(--green-700); color: #fff; border-color: var(--green-700); }
</style>
