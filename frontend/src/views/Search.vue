<script setup>
// 独立搜索页：大搜索框 + 最近搜索/快搜词 + 三分组全部结果（每类 ≤20）
// 与顶栏 SearchBox 形成「两级搜索」：下拉快查，这里看全量并深链各列表页
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { globalSearch } from '../api'
import { loadHistory as loadSearchHistory, saveHistory as saveSearchHistory, clearHistory as clearSearchHistory, QUICK_WORDS } from '../utils/searchPrefs'

const route = useRoute()
const router = useRouter()
const q = ref(route.query.q || '')
const history = ref(loadSearchHistory())
const loading = ref(false)
const result = ref(null)
let timer = null
let reqId = 0

async function doSearch() {
  const kw = q.value.trim()
  if (!kw) { result.value = null; return }
  const id = ++reqId
  loading.value = true
  try {
    const { data } = await globalSearch(kw, 20)
    if (id === reqId) result.value = data.data
  } catch { /* 静默：保留上次结果 */ }
  finally { if (id === reqId) loading.value = false }
}

function onInput() {
  clearTimeout(timer)
  timer = setTimeout(doSearch, 350)
}

function submitSearch(kw) {
  if (kw !== undefined) q.value = kw
  const trimmed = q.value.trim()
  if (!trimmed) return
  history.value = saveSearchHistory(trimmed)
  doSearch()
}

const hasResult = (r) => r && (r.recipes.length || r.herbs.length || r.compounds.length)
const probColor = (p) => p >= 0.9 ? 'var(--green-700)' : p >= 0.7 ? 'var(--amber-text)' : 'var(--ink-400)'

function goRecipe(r) { router.push(`/recipes/${r.id}`) }
function goHerb(h) { router.push({ path: '/herbs', query: { h: h.name } }) }
function goCompound(c) { router.push(`/compounds/${encodeURIComponent(c.name)}`) }

onMounted(() => { if (q.value.trim()) doSearch() })
</script>

<template>
  <div class="page">
    <div class="card s-card">
      <van-search v-model="q" placeholder="搜方子 / 药材 / 成分 / 配料 / 体质" show-action
                  @update:model-value="onInput" @search="submitSearch()" autofocus>
        <template #action>
          <button class="s-go" @click="submitSearch()">搜索</button>
        </template>
      </van-search>

      <!-- 空输入：最近搜索 + 快搜词（与顶栏下拉共用 searchPrefs） -->
      <div v-if="!q.trim()" class="s-idle">
        <template v-if="history.length">
          <div class="s-label">最近搜索
            <button class="s-clear" @click="history = []; clearSearchHistory()">清空</button>
          </div>
          <div class="s-chips">
            <button v-for="kw in history" :key="kw" class="s-chip" @click="submitSearch(kw)">
              <AppIcon name="search" :size="11" /> {{ kw }}
            </button>
          </div>
        </template>
        <div class="s-label">快搜</div>
        <div class="s-chips">
          <button v-for="kw in QUICK_WORDS" :key="kw" class="s-chip" @click="submitSearch(kw)">{{ kw }}</button>
        </div>
      </div>
    </div>

    <template v-if="q.trim()">
      <div v-if="loading" class="s-skl">
        <div class="sk-line w50 sk-anim"></div>
        <div class="sk-line w90 sk-anim"></div>
        <div class="sk-line w70 sk-anim"></div>
      </div>
      <van-empty v-else-if="!hasResult(result)" image="search"
                 :description="`没有找到「${q.trim()}」相关内容，换个词试试`" />
      <template v-else>
        <!-- 方子组 -->
        <div class="s-group" v-if="result.recipes.length">
          <div class="s-head">方子 <span>{{ result.recipes.length }}</span></div>
          <button class="card s-item pressable" v-for="r in result.recipes" :key="'r' + r.id" @click="goRecipe(r)">
            <span class="s-name">{{ r.name }}</span>
            <span class="s-sub">{{ r.type }}<template v-if="r.oneliner"> · {{ r.oneliner }}</template></span>
            <span v-if="r.matched_by" class="s-hit">{{ r.matched_by }}</span>
          </button>
          <router-link :to="{ path: '/recipes', query: { q } }" class="s-more">去方子库看全部 →</router-link>
        </div>
        <!-- 药材组 -->
        <div class="s-group" v-if="result.herbs.length">
          <div class="s-head">药材 <span>{{ result.herbs.length }}</span></div>
          <button class="card s-item pressable" v-for="h in result.herbs" :key="'h' + h.id" @click="goHerb(h)">
            <span class="s-name">{{ h.name }}</span>
            <span class="s-sub">{{ h.category }} · {{ h.nature }}{{ h.flavor ? ' · ' + h.flavor : '' }} · {{ h.compound_count }} 个成分</span>
            <span v-if="h.matched_by" class="s-hit">{{ h.matched_by }}</span>
          </button>
          <router-link :to="{ path: '/herbs' }" class="s-more">去药材图鉴 →</router-link>
        </div>
        <!-- 成分组 -->
        <div class="s-group" v-if="result.compounds.length">
          <div class="s-head">活性成分 <span>{{ result.compounds.length }}</span></div>
          <button class="card s-item pressable" v-for="c in result.compounds" :key="'c' + c.id" @click="goCompound(c)">
            <span class="s-name">{{ c.name }}</span>
            <span class="s-sub">入血概率 <b :style="{ color: probColor(c.prob_cctcm) }">{{ (c.prob_cctcm * 100).toFixed(0) }}%</b> · 关联 {{ c.target_count }} 个靶点</span>
          </button>
          <router-link :to="{ path: '/compounds' }" class="s-more">去成分库 →</router-link>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.s-card { padding: 10px 14px; margin-bottom: 12px; }
.s-go {
  border: none; background: var(--green-700); color: #fdfaf1; font-family: inherit;
  font-size: 13px; padding: 5px 14px; border-radius: 16px; cursor: pointer; font-weight: 600;
}
.s-idle { padding: 2px 0 8px; }
.s-label { font-size: 11px; color: var(--ink-400); letter-spacing: 1px; display: flex; align-items: center; margin-bottom: 8px; }
.s-clear { border: none; background: none; cursor: pointer; font-family: inherit; font-size: 11px; color: var(--ink-400); margin-left: auto; padding: 0; }
.s-clear:hover { color: var(--cinnabar); }
.s-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.s-chip {
  display: inline-flex; align-items: center; gap: 4px;
  border: 1px solid var(--green-100); background: var(--green-50);
  color: var(--ink-600); font-size: 13px; font-family: inherit;
  padding: 5px 13px; border-radius: 16px; cursor: pointer;
  transition: border-color var(--dur-fast) ease, color var(--dur-fast) ease;
}
.s-chip:hover { border-color: var(--green-600); color: var(--green-text); }

.s-skl { padding: 20px 16px; display: flex; flex-direction: column; gap: 10px; }

.s-group { margin-bottom: 18px; }
.s-head { font-size: 13px; font-weight: 700; color: var(--ink-900); font-family: var(--font-serif); letter-spacing: .04em; margin-bottom: 8px; }
.s-head span { font-size: 11px; color: var(--ink-400); font-weight: 400; margin-left: 4px; }
.s-item {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px; width: 100%;
  border: 1px solid var(--card-border); text-align: left; cursor: pointer;
  padding: 11px 14px; margin-bottom: 8px; font-family: inherit;
}
.s-name { font-size: 14.5px; color: var(--ink-900); font-weight: 600; font-family: var(--font-serif); }
.s-sub { font-size: 12px; color: var(--ink-400); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.s-hit {
  font-size: 10px; color: var(--green-text); background: var(--green-50);
  border: 1px solid var(--green-100); border-radius: 4px; padding: 0 5px; line-height: 1.6;
  margin-top: 2px;
}
.s-more { display: block; text-align: center; font-size: 12.5px; color: var(--green-text); text-decoration: none; font-weight: 600; padding: 6px 0 2px; }
</style>
