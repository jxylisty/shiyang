<script setup>
// 顶栏全局搜索：一次关键词聚合方子/药材/成分三类结果（对标知源中医的统一检索入口）
// 药材行 → /herbs?h=名（Herbs.vue 读 query 打开详情弹窗）；成分行 → /compounds/:name 词典页
// 便利性增强：命中来源标签（matched_by）+ 本地搜索历史 + 快搜词（体质/场景）
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from './AppIcon.vue'
import { globalSearch } from '../api'

const router = useRouter()
const q = ref('')
const open = ref(false)
const expanded = ref(false)   // 窄屏：搜索框折叠成图标，点开才展开输入
const inputRef = ref(null)
const loading = ref(false)
const result = ref(null)
const boxRef = ref(null)
let timer = null
let reqId = 0

// ---- 搜索历史（纯本地，最多 8 条，去重） ----
const HISTORY_KEY = 'shiyang_search_history_v1'
const HISTORY_MAX = 8
const history = ref([])
function loadHistory() {
  try { history.value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { history.value = [] }
}
function saveHistory(kw) {
  const list = history.value.filter(x => x !== kw)
  list.unshift(kw)
  history.value = list.slice(0, HISTORY_MAX)
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value)) } catch { /* 存储不可用静默 */ }
}
function clearHistory() {
  history.value = []
  try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
}
function applyKw(kw) {
  q.value = kw
  onInput()
  inputRef.value?.focus()
}

// ---- 快搜词：九种体质 + 高频场景（静态，空输入聚焦时展示） ----
const QUICK_WORDS = ['气虚', '润肺', '助眠', '枸杞', '菊花', '换季调理', '阴虚', '祛湿']

const showIdle = computed(() => !q.value.trim() && !loading.value)

// 窄屏点图标 → 展开并把焦点给输入框
function onBoxClick() {
  if (expanded.value) return
  expanded.value = true
  nextTick(() => inputRef.value?.focus())
}

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

// 点外部：关下拉；窄屏且输入为空时收回成图标
function onDocClick(e) {
  if (!boxRef.value?.contains(e.target)) {
    close()
    if (!q.value.trim()) expanded.value = false
  }
}
function onKey(e) {
  if (e.key !== 'Escape') return
  if (open.value) close()
  else if (expanded.value) { q.value = ''; expanded.value = false }
}
onMounted(() => {
  loadHistory()
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
onUnmounted(() => { document.removeEventListener('click', onDocClick); document.removeEventListener('keydown', onKey) })

function go(kind, item) {
  saveHistory(q.value.trim())
  close()
  if (kind === 'recipe') router.push(`/recipes/${item.id}`)
  else if (kind === 'herb') router.push({ path: '/herbs', query: { h: item.name } })
  else router.push(`/compounds/${encodeURIComponent(item.name)}`)
}
const hasResult = (r) => r && (r.recipes.length || r.herbs.length || r.compounds.length)
const probColor = (p) => p >= 0.9 ? 'var(--green-700)' : p >= 0.7 ? 'var(--amber-text)' : 'var(--ink-400)'
</script>

<template>
  <div class="gsearch" :class="{ expanded }" ref="boxRef">
    <div class="gs-input" @click="onBoxClick">
      <AppIcon name="search" :size="15" :stroke-width="2.2" />
      <input ref="inputRef" v-model="q" type="search" placeholder="搜方子 / 药材 / 成分" @input="onInput" @focus="open = true" />
    </div>
    <transition name="gs-fade">
      <div class="gs-panel" v-if="open">
        <!-- 空输入聚焦：搜索历史 + 快搜词 -->
        <div v-if="showIdle" class="gs-idle">
          <template v-if="history.length">
            <div class="gs-title gs-idle-head">
              最近搜索
              <button class="gs-clear" @click.stop="clearHistory">清空</button>
            </div>
            <div class="gs-chips">
              <button class="gs-chip" v-for="kw in history" :key="kw" @click="applyKw(kw)">
                <AppIcon name="search" :size="11" /> {{ kw }}
              </button>
            </div>
          </template>
          <div class="gs-title">快搜</div>
          <div class="gs-chips">
            <button class="gs-chip" v-for="kw in QUICK_WORDS" :key="kw" @click="applyKw(kw)">{{ kw }}</button>
          </div>
        </div>
        <template v-else>
          <div class="gs-loading" v-if="loading">搜索中…</div>
          <template v-else-if="result">
            <div class="gs-empty" v-if="!hasResult(result)">没有找到「{{ result.query }}」相关内容</div>
            <template v-else>
              <div class="gs-group" v-if="result.recipes.length">
                <div class="gs-title">方子</div>
                <button class="gs-item" v-for="r in result.recipes" :key="'r' + r.id" @click="go('recipe', r)">
                  <span class="gs-name">{{ r.name }}</span>
                  <span class="gs-sub">
                    {{ r.type }}<template v-if="r.oneliner"> · {{ r.oneliner }}</template>
                  </span>
                  <span v-if="r.matched_by" class="gs-hit">{{ r.matched_by }}</span>
                </button>
              </div>
              <div class="gs-group" v-if="result.herbs.length">
                <div class="gs-title">药材</div>
                <button class="gs-item" v-for="h in result.herbs" :key="'h' + h.id" @click="go('herb', h)">
                  <span class="gs-name">{{ h.name }}</span>
                  <span class="gs-sub">{{ h.nature }}{{ h.flavor ? ' · ' + h.flavor : '' }} · {{ h.compound_count }} 个成分</span>
                  <span v-if="h.matched_by" class="gs-hit">{{ h.matched_by }}</span>
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

/* 空输入态：最近搜索 + 快搜词 */
.gs-idle { padding: 2px 0 6px; }
.gs-idle-head { display: flex; align-items: center; justify-content: space-between; }
.gs-clear {
  border: none; background: none; cursor: pointer; font-family: inherit;
  font-size: 11px; color: var(--ink-400); padding: 0 10px;
}
.gs-clear:hover { color: var(--cinnabar); }
.gs-chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 10px 2px; }
.gs-chip {
  display: inline-flex; align-items: center; gap: 4px;
  border: 1px solid var(--green-100); background: var(--green-50);
  color: var(--ink-600); font-size: 12px; font-family: inherit;
  padding: 3px 10px; border-radius: 14px; cursor: pointer;
  transition: border-color var(--dur-fast) ease, color var(--dur-fast) ease;
}
.gs-chip:hover { border-color: var(--green-600); color: var(--green-text); }

/* 命中来源标签（配料含枸杞 / 场景·助眠 / 功效·润肺…） */
.gs-hit {
  align-self: flex-start; margin-top: 2px;
  font-size: 10px; color: var(--green-text); background: var(--green-50);
  border: 1px solid var(--green-100); border-radius: 4px; padding: 0 5px;
  line-height: 1.5;
}
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
@media (max-width: 560px) {
  /* 窄屏：顶栏放不下 logo + 5 项导航 + 输入框，搜索收成一个图标；点开时浮层覆盖导航
     不这么做会撑出横向滚动条（375px 下溢出约 72px）。topbar 是 sticky 定位的
     包含块，absolute 相对它定位 */
  .gs-input { padding: 6px; border-radius: 50%; }
  .gs-input input { display: none; }
  .gsearch.expanded {
    position: absolute; right: 12px; top: 50%; translate: 0 -50%; z-index: 30;
  }
  .gsearch.expanded .gs-input {
    border-radius: 18px; padding: 5px 12px;
    background: var(--card); box-shadow: 0 2px 12px rgba(31, 74, 56, .12);
  }
  .gsearch.expanded .gs-input input { display: block; width: 150px; min-width: 0; }
  .gs-panel { width: min(280px, calc(100vw - 32px)); right: 0; }
}
</style>
