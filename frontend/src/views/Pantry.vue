<script setup>
import { ref, computed, onMounted } from 'vue'
import { ShoppingBasket, Check, Plus } from '@lucide/vue'
import { showSuccessToast } from 'vant'
import { getPantryMaterials, pantryMatch, matImg } from '../api'

const materials = ref([])       // 全部可选食材
const selected = ref(new Set()) // 勾选的食材名
const search = ref('')
const result = ref(null)
const loading = ref(false)
const error = ref('')

const STORE_KEY = 'shiyang_pantry_v1'

onMounted(async () => {
  // 本地记忆：上次勾选的茶罐
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || '[]')
    saved.forEach(n => selected.value.add(n))
  } catch { /* ignore */ }
  try {
    materials.value = (await getPantryMaterials()).data.data.items
  } catch { error.value = '食材清单加载失败' }
  if (selected.value.size) runMatch()
})

const shown = computed(() => {
  const kw = search.value.trim()
  const sel = [...selected.value]
  const rest = materials.value.filter(m => !selected.value.has(m.name))
  const pool = kw ? rest.filter(m => m.name.includes(kw)) : rest
  return { sel, pool: pool.slice(0, kw ? 50 : 40) }
})

function toggle(name) {
  const s = new Set(selected.value)
  s.has(name) ? s.delete(name) : s.add(name)
  selected.value = s
}

function persist() {
  localStorage.setItem(STORE_KEY, JSON.stringify([...selected.value]))
}

async function runMatch() {
  if (!selected.value.size) { result.value = null; return }
  loading.value = true
  error.value = ''
  persist()
  try {
    result.value = (await pantryMatch([...selected.value])).data.data
  } catch { error.value = '匹配失败，请重试' } finally { loading.value = false }
}

function coverBar(c) { return Math.round(c * 100) }
</script>

<template>
  <div class="page">
    <div class="card head-card">
      <h2 class="p-title"><ShoppingBasket :size="18" /> 我的茶罐</h2>
      <p class="p-sub">勾选手边有的食材，看看今晚就能煮什么——反向配伍，附成分证据</p>
    </div>

    <van-empty v-if="error && !materials.length" image="error" :description="error" />

    <!-- 已选 -->
    <div class="section-title">已选 {{ selected.size }} 味</div>
    <div class="card">
      <div v-if="selected.size" class="chip-wrap">
        <button v-for="n in shown.sel" :key="n" class="tag sel-tag" @click="toggle(n)">
          {{ n }} <span class="x">✕</span>
        </button>
      </div>
      <p v-else class="hint">从下面勾选你手边有的食材（会记住你的茶罐）</p>
      <button class="btn" style="margin-top: 10px; width: 100%" :disabled="!selected.size || loading"
              @click="runMatch">{{ loading ? '配伍中…' : '找能煮的方子' }}</button>
    </div>

    <!-- 食材选择 -->
    <div class="section-title">勾选食材</div>
    <div class="card">
      <van-search v-model="search" placeholder="搜食材，如：陈皮" class="search-box" />
      <div class="chip-wrap">
        <button v-for="m in shown.pool" :key="m.name" class="tag opt-tag" @click="toggle(m.name)">
          <img :src="matImg(m.name)" alt="" loading="lazy" @error="e => e.target.style.display = 'none'" />
          {{ m.name }}
        </button>
      </div>
      <p v-if="!shown.pool.length" class="hint">没有更多可选食材了</p>
    </div>

    <template v-if="result">
      <!-- 直接能煮 -->
      <div class="section-title">直接能煮（{{ result.suggestions.length }}）</div>
      <div v-if="result.suggestions.length" class="pantry-list">
        <router-link v-for="r in result.suggestions" :key="r.id" :to="`/recipes/${r.id}`"
                     class="card p-item pressable">
          <div class="pi-left">
            <img :src="matImg(r.hit[0] || '')" alt="" loading="lazy" @error="e => e.target.style.visibility = 'hidden'" />
            <Check :size="16" class="pi-check" />
          </div>
          <div class="pi-main">
            <b>{{ r.name }}</b>
            <p class="pi-one">{{ r.oneliner }}</p>
            <div class="pi-tags">
              <span v-for="s in r.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
              <span v-if="r.hi_blood_count" class="tag lab">高入血成分 ×{{ r.hi_blood_count }}</span>
            </div>
          </div>
        </router-link>
      </div>
      <van-empty v-else image="search" description="现有食材还不能完整煮任何方子，看看下面「差一点」的" />

      <!-- 差一点 -->
      <div v-if="result.partial.length" class="section-title">差一味就齐（{{ result.partial.length }}）</div>
      <div v-if="result.partial.length" class="pantry-list">
        <router-link v-for="r in result.partial" :key="r.id" :to="`/recipes/${r.id}`"
                     class="card p-item partial pressable">
          <div class="pi-left">
            <img :src="matImg(r.hit[0] || '')" alt="" loading="lazy" @error="e => e.target.style.visibility = 'hidden'" />
          </div>
          <div class="pi-main">
            <div class="pi-top">
              <b>{{ r.name }}</b>
              <span class="cov">{{ coverBar(r.coverage) }}%</span>
            </div>
            <p class="pi-miss">还差：<b>{{ r.missing.join('、') }}</b></p>
            <div class="pi-tags">
              <span v-for="s in r.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
            </div>
          </div>
        </router-link>
      </div>
    </template>
  </div>
</template>

<style scoped>
.head-card { text-align: center; padding: 20px 16px; }
.p-title { font-size: 18px; display: flex; align-items: center; justify-content: center; gap: 6px; color: var(--green-text); }
.p-sub { font-size: 12px; color: var(--ink-400); margin-top: 6px; }
.search-box { padding: 0 0 10px; background: transparent; }
.chip-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
.sel-tag { background: var(--green-700); color: #fff; border-color: var(--green-700); cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.sel-tag .x { opacity: .85; font-size: 10px; }
.opt-tag { cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.opt-tag img { width: 16px; height: 16px; border-radius: 50%; object-fit: cover; }
.hint { font-size: 12px; color: var(--ink-400); }

.pantry-list { display: flex; flex-direction: column; gap: 10px; }
.p-item { display: flex; gap: 12px; padding: 12px; text-decoration: none; color: inherit; position: relative; }
.pi-left { position: relative; width: 56px; height: 56px; border-radius: 12px; overflow: hidden; flex-shrink: 0;
           background: linear-gradient(135deg, var(--green-600), var(--green-900)); }
.pi-left img { width: 100%; height: 100%; object-fit: cover; }
.pi-check { position: absolute; right: 2px; bottom: 2px; color: #fff; background: var(--green-600);
            border-radius: 50%; padding: 2px; }
.p-item.partial { opacity: .92; }
.pi-main { flex: 1; min-width: 0; }
.pi-main b { font-size: 15px; }
.pi-top { display: flex; justify-content: space-between; align-items: center; }
.cov { font-size: 12px; font-weight: 700; color: var(--amber-text); }
.pi-one { font-size: 12px; color: var(--ink-600); margin: 3px 0 6px; }
.pi-miss { font-size: 12px; color: var(--ink-600); margin: 3px 0 6px; }
.pi-miss b { color: var(--amber-text); font-weight: 600; }
.pi-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag.lab { background: var(--green-700); color: #fff; border-color: var(--green-700); }
</style>
