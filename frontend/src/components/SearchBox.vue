<script setup>
// 顶栏全局搜索：一次关键词聚合方子/药材/成分三类结果（对标知源中医的统一检索入口）
// 药材行 → /herbs?h=名（Herbs.vue 读 query 打开详情弹窗）；成分行 → /compounds/:name 词典页
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@lucide/vue'
import { globalSearch } from '../api'

const router = useRouter()
const q = ref('')
const open = ref(false)
const loading = ref(false)
const result = ref(null)
const boxRef = ref(null)
let timer = null
let reqId = 0

function onInput() {
  clearTimeout(timer)
  const kw = q.value.trim()
  if (!kw) { open.value = false; result.value = null; return }
  timer = setTimeout(async () => {
    loading.value = true
    open.value = true
    const id = ++reqId
    try {
      const { data } = await globalSearch(kw)
      if (id === reqId) result.value = data.data
    } catch { /* 静默：下拉保持上次结果或空态 */ }
    finally { if (id === reqId) loading.value = false }
  }, 300)
}

function close() { open.value = false }

function onDocClick(e) {
  if (boxRef.value && !boxRef.value.contains(e.target)) close()
}
function onKey(e) { if (e.key === 'Escape') close() }
onMounted(() => { document.addEventListener('click', onDocClick); document.addEventListener('keydown', onKey) })
onUnmounted(() => { document.removeEventListener('click', onDocClick); document.removeEventListener('keydown', onKey) })

function go(kind, item) {
  close()
  if (kind === 'recipe') router.push(`/recipes/${item.id}`)
  else if (kind === 'herb') router.push({ path: '/herbs', query: { h: item.name } })
  else router.push(`/compounds/${encodeURIComponent(item.name)}`)
}
const hasResult = (r) => r && (r.recipes.length || r.herbs.length || r.compounds.length)
const probColor = (p) => p >= 0.9 ? 'var(--green-700)' : p >= 0.7 ? 'var(--amber-text)' : 'var(--ink-400)'
</script>

<template>
  <div class="gsearch" ref="boxRef">
    <div class="gs-input">
      <Search :size="15" :stroke-width="2.2" />
      <input v-model="q" type="search" placeholder="搜方子 / 药材 / 成分" @input="onInput" @focus="q.trim() && (open = true)" />
    </div>
    <transition name="gs-fade">
      <div class="gs-panel" v-if="open">
        <div class="gs-loading" v-if="loading">搜索中…</div>
        <template v-else-if="result">
          <div class="gs-empty" v-if="!hasResult(result)">没有找到「{{ result.query }}」相关内容</div>
          <template v-else>
            <div class="gs-group" v-if="result.recipes.length">
              <div class="gs-title">方子</div>
              <button class="gs-item" v-for="r in result.recipes" :key="'r' + r.id" @click="go('recipe', r)">
                <span class="gs-name">{{ r.name }}</span>
                <span class="gs-sub">{{ r.type }}<template v-if="r.oneliner"> · {{ r.oneliner }}</template></span>
              </button>
            </div>
            <div class="gs-group" v-if="result.herbs.length">
              <div class="gs-title">药材</div>
              <button class="gs-item" v-for="h in result.herbs" :key="'h' + h.id" @click="go('herb', h)">
                <span class="gs-name">{{ h.name }}</span>
                <span class="gs-sub">{{ h.nature }}{{ h.flavor ? ' · ' + h.flavor : '' }} · {{ h.compound_count }} 个成分</span>
              </button>
            </div>
            <div class="gs-group" v-if="result.compounds.length">
              <div class="gs-title">成分</div>
              <button class="gs-item" v-for="c in result.compounds" :key="'c' + c.id" @click="go('compound', c)">
                <span class="gs-name">{{ c.name }}</span>
                <span class="gs-sub">入血概率 <b :style="{ color: probColor(c.prob_cctcm) }">{{ (c.prob_cctcm * 100).toFixed(0) }}%</b></span>
              </button>
            </div>
          </template>
        </template>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.gsearch { position: relative; flex-shrink: 0; }
.gs-input {
  display: flex; align-items: center; gap: 6px;
  background: var(--green-50); border: 1px solid var(--green-100); border-radius: 18px;
  padding: 5px 12px; color: var(--ink-400);
}
.gs-input input {
  border: none; outline: none; background: transparent;
  font-size: 13px; color: var(--ink-900); width: 150px;
}
.gs-input input::placeholder { color: var(--ink-400); }
.gs-input:focus-within { border-color: var(--green-600); }
.gs-panel {
  position: absolute; top: calc(100% + 8px); right: 0; z-index: 50;
  width: 300px; max-height: 70vh; overflow-y: auto;
  background: var(--card); border: 1px solid var(--green-100); border-radius: var(--radius);
  box-shadow: 0 8px 28px rgba(31, 74, 56, 0.14); padding: 6px;
  text-align: left;
}
.gs-loading, .gs-empty { padding: 18px 12px; text-align: center; color: var(--ink-400); font-size: 13px; }
.gs-group + .gs-group { border-top: 1px solid var(--green-100); margin-top: 4px; padding-top: 4px; }
.gs-title { font-size: 11px; color: var(--ink-400); padding: 6px 10px 2px; letter-spacing: 1px; }
.gs-item {
  display: flex; flex-direction: column; gap: 1px; width: 100%;
  border: none; background: none; text-align: left; cursor: pointer;
  padding: 7px 10px; border-radius: 8px; font-family: inherit;
}
.gs-item:hover { background: var(--green-50); }
.gs-name { font-size: 14px; color: var(--ink-900); font-weight: 500; }
.gs-sub { font-size: 11.5px; color: var(--ink-400); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gs-fade-enter-active, .gs-fade-leave-active { transition: opacity .15s ease, transform .15s ease; }
.gs-fade-enter-from, .gs-fade-leave-to { opacity: 0; transform: translateY(-4px); }
@media (max-width: 420px) {
  .gs-input input { width: 104px; }
  .gs-panel { width: 260px; }
}
</style>
