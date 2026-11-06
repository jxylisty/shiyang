<script setup>
// 药材图鉴：网格卡片 + 本草笺卡详情弹层（性味归经胶囊、典籍中文功效 + HERB 原文备查、成分数据舱、联动查方）
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { X, Sparkles, FlaskConical, ChevronDown, ArrowRight } from '@lucide/vue'
import AppIcon from '../components/AppIcon.vue'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'
import { listHerbs, matImg } from '../api'
import { normalizeHerbView } from '../utils/pharmacopoeiaFunctions'

const route = useRoute()
const allItems = ref([])
const loading = ref(true)
const loadError = ref(false)
const kw = ref('')
const filterKey = ref('all')   // all | warm | neutral | cool | prob
const active = ref(null)       // 当前打开详情的药材（已归一化）
const showEnRaw = ref(false)   // 是否展开 HERB 英文原文
const imgFailed = ref({})

// 桌面端详情用居中弹窗，手机保持底部抽屉（van-popup--bottom 只有 left:0，宽屏下 margin auto 不生效）
const mqWide = window.matchMedia('(min-width: 720px)')
const isWide = ref(mqWide.matches)
const onMqChange = (e) => { isWide.value = e.matches }

const FILTERS = [
  { key: 'all', label: '全部药材' },
  { key: 'warm', label: '温热性' },
  { key: 'neutral', label: '平性' },
  { key: 'cool', label: '寒凉性' },
  { key: 'prob', label: '含入血预测' },
]

function natureTone(n) {
  if (!n) return 'neutral'
  if (n.includes('温') || n.includes('热')) return 'warm'
  if (n.includes('寒') || n.includes('凉')) return 'cool'
  return 'neutral'
}

function fmtNatureLabel(n) {
  if (!n) return ''
  return n.endsWith('性') ? n : `${n}性`
}

function fmtFlavorLabel(f) {
  if (!f) return ''
  return f.length === 1 ? `${f}味` : f
}

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const d = (await listHerbs('')).data.data
    allItems.value = (d.items || []).map(normalizeHerbView)
    syncQueryHerb()
  } catch {
    loadError.value = true
    allItems.value = []
  } finally {
    loading.value = false
  }
}

function syncQueryHerb() {
  const target = route.query.h
  if (target && allItems.value.length) {
    const hit = allItems.value.find(x => x.name === target)
    if (hit) openHerb(hit)
  }
}

watch(() => route.query.h, syncQueryHerb)

const shownItems = computed(() => {
  const q = kw.value.trim().toLowerCase()
  return allItems.value.filter((h) => {
    if (filterKey.value === 'warm' && natureTone(h.nature) !== 'warm') return false
    if (filterKey.value === 'cool' && natureTone(h.nature) !== 'cool') return false
    if (filterKey.value === 'neutral' && natureTone(h.nature) !== 'neutral') return false
    if (filterKey.value === 'prob' && !h.has_prob_data) return false
    if (!q) return true
    const hay = [
      h.name,
      h.category,
      h.nature,
      h.flavors.join(' '),
      h.meridians.join(' '),
      h.cnFn,
      h.functions,
    ].filter(Boolean).join(' ').toLowerCase()
    return hay.includes(q)
  })
})

function openHerb(h) {
  active.value = h
  // 若该药暂无中文功效词条则默认展开英文原文，否则默认收起保持界面清爽
  showEnRaw.value = !h.cnChips.length && h.hasEnRaw
}

function closeHerb() {
  active.value = null
}

onMounted(() => {
  mqWide.addEventListener('change', onMqChange)
  load()
})
onUnmounted(() => {
  mqWide.removeEventListener('change', onMqChange)
})

const hideImg = (name) => { imgFailed.value[name] = true }
</script>

<template>
  <div class="page">
    <div class="card search-card">
      <van-search v-model="kw" placeholder="搜药材名 / 性味 / 归经 / 功效（如：红枣 / 甘 / 脾经 / 养血）" class="search-box" />
      <div class="filter-bar">
        <button v-for="f in FILTERS" :key="f.key" type="button"
                class="f-pill" :class="{ active: filterKey === f.key }"
                @click="filterKey = f.key">
          {{ f.label }}
        </button>
      </div>
    </div>

    <!-- 骨架屏：15 个占位卡片 -->
    <div v-if="loading" class="herb-grid">
      <div v-for="i in 15" :key="i" class="card herb-card">
        <div class="h-img sk-anim"></div>
        <div class="sk-line w70 sk-anim"></div>
        <div class="sk-line w50 sk-anim"></div>
      </div>
    </div>
    <van-empty v-else-if="loadError" image="error" description="服务暂时不可用，请稍后重试" />
    <van-empty v-else-if="!shownItems.length" image="search" description="未找到匹配药材，换个词或筛选条件试试" />

    <template v-else>
      <p class="count">
        共 <b>{{ shownItems.length }}</b><template v-if="shownItems.length !== allItems.length"> / {{ allItems.length }}</template> 味药食同源药材
      </p>
      <div class="herb-grid">
        <button v-for="(h, i) in shownItems" :key="h.id" type="button"
                class="card herb-card pressable"
                :style="{ '--d': `${Math.min(i, 20) * 25}ms` }"
                @click="openHerb(h)">
          <div class="h-img">
            <img v-if="!imgFailed[h.name]" :src="matImg(h.name)" :alt="h.name" loading="lazy" @error="hideImg(h.name)" />
            <span v-else class="h-fallback"><AppIcon name="herb" :size="30" /></span>
            <span v-if="h.category" class="h-cat-badge">{{ h.category }}</span>
          </div>
          <b class="h-name">{{ h.name }}</b>
          <div class="h-meta" v-if="h.nature || h.flavors.length">
            <span v-if="h.nature" class="h-nat-dot" :class="natureTone(h.nature)">{{ h.nature }}</span>
            <span v-if="h.flavors.length" class="h-flv-txt">{{ h.flavors.slice(0, 2).join('·') }}</span>
          </div>
          <p v-if="h.cnChips.length" class="h-fn-brief">{{ h.cnChips.slice(0, 2).join(' · ') }}</p>
          <span class="h-count">
            <i v-if="h.has_prob_data" class="prob-dot" title="含入血概率预测"></i>
            {{ h.compound_count }} 活性成分
          </span>
        </button>
      </div>
    </template>

    <!-- 本草笺卡详情弹层 -->
    <van-popup :show="!!active" :position="isWide ? 'center' : 'bottom'" round
               class="herb-popup" :class="{ 'h-popup-wide': isWide }"
               @update:show="(v) => { if (!v) closeHerb() }" @click-overlay="closeHerb">
      <div class="h-detail" v-if="active">
        <!-- 右上角轻巧关闭钮 -->
        <button type="button" class="hd-x" @click="closeHerb" aria-label="关闭弹窗">
          <X :size="17" :stroke-width="2.2" />
        </button>

        <!-- 顶部名物头卡 -->
        <div class="hd-head">
          <div class="hd-cover">
            <img v-if="!imgFailed[active.name]" :src="matImg(active.name)" :alt="active.name" @error="hideImg(active.name)" />
            <span v-else class="h-fallback"><AppIcon name="herb" :size="34" /></span>
          </div>
          <div class="hd-title-zone">
            <div class="hd-title-row">
              <h3 class="pop-text">{{ active.name }}</h3>
              <span v-if="active.category" class="hd-cat">{{ active.category }}</span>
            </div>
            <div class="hd-catalog" v-if="active.food_catalog_batch">
              <AppIcon name="herb" :size="12" />
              <span>卫健委药食同源目录 · {{ active.food_catalog_batch }} 年纳入</span>
            </div>
            <div class="hd-props" v-if="active.nature || active.flavors.length">
              <span v-if="active.nature" class="prop-pill" :class="'tone-' + natureTone(active.nature)">
                {{ fmtNatureLabel(active.nature) }}
              </span>
              <span v-for="fl in active.flavors" :key="fl" class="prop-pill tone-flavor">
                {{ fmtFlavorLabel(fl) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 归经横栏 -->
        <div class="hd-meridians hd-in" style="--i: 1" v-if="active.meridians.length">
          <span class="hd-sec-label">归经</span>
          <div class="m-chips">
            <span v-for="m in active.meridians" :key="m" class="m-chip">{{ m }}</span>
          </div>
        </div>

        <!-- 传统功效与记载 -->
        <div class="hd-sec hd-in" style="--i: 2" v-if="active.cnChips.length || active.hasEnRaw">
          <div class="hd-sec-head">
            <span class="hd-sec-label">传统功效</span>
            <span v-if="active.cnSrc" class="hd-src-note">据{{ active.cnSrc }}</span>
          </div>

          <div v-if="active.cnChips.length" class="fn-chips">
            <span v-for="fn in active.cnChips" :key="fn" class="fn-chip">{{ fn }}</span>
          </div>

          <!-- HERB 数据库英文记载折叠备查（去除原始竖线拼接，清晰拆段） -->
          <div v-if="active.hasEnRaw" class="en-raw-wrap">
            <button type="button" class="en-toggle" @click="showEnRaw = !showEnRaw">
              <span>{{ showEnRaw ? '收起 HERB 数据库英文记载' : '查看 HERB 数据库英文记载' }}</span>
              <ChevronDown :size="14" class="en-chev" :class="{ open: showEnRaw }" />
            </button>
            <div v-if="showEnRaw" class="en-box">
              <div v-if="active.enFunc" class="en-item">
                <span class="en-tag">Function · 功效记载</span>
                <p>{{ active.enFunc }}</p>
              </div>
              <div v-if="active.enIndic" class="en-item">
                <span class="en-tag">Indication · 应用记载</span>
                <p>{{ active.enIndic }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 活性成分数据舱（左数右文，彻底消除断字挤压） -->
        <div class="hd-data-pod hd-in" style="--i: 3">
          <div class="pod-num-box">
            <b class="pod-num">{{ active.compound_count || 0 }}</b>
            <span class="pod-unit">活性成分</span>
          </div>
          <div class="pod-divider"></div>
          <div class="pod-info">
            <template v-if="active.has_prob_data">
              <span class="pod-badge ok"><Sparkles :size="11" /> 入血预测模型已覆盖</span>
              <p>已关联预测入血概率与人类蛋白作用靶点数据，可进入成分库深查。</p>
            </template>
            <template v-else-if="active.compound_count > 0">
              <span class="pod-badge herb"><FlaskConical :size="11" /> HERB 数据库收录</span>
              <p>已建立药材-成分-靶点实验文献关联（本平台入血概率模型暂未覆盖该药材）。</p>
            </template>
            <template v-else>
              <span class="pod-badge muted">待补充</span>
              <p>该品种主要按传统药食两用记载收录，分子成分数据整理中。</p>
            </template>
          </div>
        </div>

        <div class="hd-in" style="--i: 4">
          <DisclaimerBanner variant="herb" />
        </div>

        <!-- 底部实用联动行动栏 -->
        <div class="hd-actions hd-in" style="--i: 5">
          <router-link v-if="active.has_prob_data" to="/compounds" class="btn ghost hd-act-sub" @click="closeHerb">
            浏览成分库
          </router-link>
          <router-link :to="{ path: '/recipes', query: { q: active.name } }" class="btn hd-act-main" @click="closeHerb">
            查看含「{{ active.name }}」的方子 <ArrowRight :size="15" :stroke-width="2.2" />
          </router-link>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.search-card { padding: 12px 14px; margin-bottom: 12px; }
.search-box { padding: 0; background: transparent; }
.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.f-pill {
  border: 1px solid var(--card-border); background: rgba(120, 95, 60, 0.04);
  color: var(--ink-600); font-size: 12px; font-family: inherit;
  padding: 4px 11px; border-radius: 999px; cursor: pointer;
  transition: all var(--dur-fast) ease;
}
.f-pill:hover { border-color: rgba(58, 122, 94, 0.35); color: var(--green-text); }
.f-pill.active {
  background: var(--green-700); color: #fdfaf1;
  border-color: var(--green-700); font-weight: 600;
}

.count { font-size: 12.5px; color: var(--ink-400); margin-bottom: 10px; }
.count b { color: var(--ink-900); font-variant-numeric: tabular-nums; }

.herb-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (min-width: 600px) { .herb-grid { grid-template-columns: repeat(4, 1fr); gap: 12px; } }
@media (min-width: 900px) { .herb-grid { grid-template-columns: repeat(5, 1fr); gap: 14px; } }

/* 列表网格小卡片 */
.herb-card {
  padding: 10px 9px 11px; text-align: center; cursor: pointer;
  border: 1px solid var(--card-border); font: inherit;
  display: flex; flex-direction: column; align-items: center; gap: 4px; margin-bottom: 0;
  animation: rise .4s var(--ease-out-soft) backwards; animation-delay: var(--d, 0ms);
}
@media (hover: hover) {
  .herb-card:hover {
    border-color: rgba(58, 122, 94, 0.34);
    box-shadow: var(--shadow-hover);
    transform: translateY(-2px);
  }
  .herb-card:hover .h-img img { transform: scale(1.05); }
}
.herb-card:active { scale: 0.96; }
.h-img {
  width: 100%; aspect-ratio: 1; border-radius: 10px; overflow: hidden;
  background: var(--green-50); margin-bottom: 4px; position: relative;
  border: 1px solid rgba(120, 95, 60, 0.10);
}
.h-img img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .35s var(--ease-out-soft); }
.h-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--tile-ink); }
.h-cat-badge {
  position: absolute; right: 5px; bottom: 5px;
  font-size: 9.5px; line-height: 1.3; padding: 2px 6px; border-radius: 6px;
  background: rgba(253, 250, 241, 0.88); color: var(--ink-600);
  backdrop-filter: blur(4px); border: 1px solid rgba(120, 95, 60, 0.14);
  max-width: calc(100% - 10px); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
:root:is(.van-theme-dark, [data-theme="dark"]) .h-cat-badge {
  background: rgba(42, 38, 31, 0.86); color: var(--ink-900);
}

.h-name { font-family: var(--font-serif); font-size: 15.5px; color: var(--ink-900); font-weight: 700; line-height: 1.3; }
.h-meta { display: inline-flex; align-items: center; gap: 5px; flex-wrap: wrap; justify-content: center; }
.h-nat-dot {
  font-size: 10.5px; font-weight: 600; padding: 0 6px; border-radius: 999px; line-height: 1.55;
}
.h-nat-dot.warm { background: var(--amber-50); color: var(--amber-text); }
.h-nat-dot.cool { background: #e5f2ef; color: #24665c; }
.h-nat-dot.neutral { background: var(--green-50); color: var(--green-text); }
:root:is(.van-theme-dark, [data-theme="dark"]) .h-nat-dot.cool { background: #1e3330; color: #84c7bc; }
.h-flv-txt { font-size: 11px; color: var(--ink-600); }
.h-fn-brief {
  font-size: 11px; color: var(--ink-400); line-height: 1.35;
  width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.h-count {
  margin-top: auto; padding-top: 4px;
  font-size: 10.5px; color: var(--ink-400); font-variant-numeric: tabular-nums;
  display: inline-flex; align-items: center; gap: 4px;
}
.prob-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--green-600); flex-shrink: 0;
}

/* 骨架屏 */
.sk-line { height: 12px; border-radius: 6px; width: 80%; }
.sk-line.w70 { width: 70%; }
.sk-line.w50 { width: 50%; }

/* ==================== 本草笺卡详情弹层 ==================== */
.herb-popup {
  background-color: var(--card) !important;
  background-image:
    var(--paper-fiber),
    radial-gradient(ellipse 110% 80% at 15% 0%, rgba(255, 255, 255, 0.72), transparent 62%);
  background-blend-mode: multiply, normal;
}
:root:is(.van-theme-dark, [data-theme="dark"]) .herb-popup {
  background-image: var(--paper-fiber);
  background-blend-mode: soft-light;
}
.h-popup-wide {
  width: 500px; max-width: 92vw;
  border-radius: 18px !important;
  border: 1px solid var(--card-border);
  box-shadow: 0 18px 48px -12px rgba(40, 30, 18, 0.28);
}

.h-detail {
  position: relative;
  padding: 22px 22px 20px;
  max-height: 82vh; overflow-y: auto;
}
/* 内层古典细笺框（不挡滚动与点击） */
.h-detail::before {
  content: ""; position: absolute; inset: 6px;
  border-radius: 13px; border: 1px solid rgba(120, 95, 60, 0.08);
  pointer-events: none;
}

.hd-x {
  position: absolute; top: 14px; right: 14px; z-index: 2;
  width: 30px; height: 30px; border-radius: 50%;
  border: 1px solid var(--card-border);
  background: rgba(120, 95, 60, 0.06); color: var(--ink-600);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all var(--dur-fast) ease;
}
.hd-x:hover { background: var(--green-50); color: var(--green-text); border-color: rgba(58, 122, 94, 0.3); }

/* 渐入错峰 */
.h-detail .hd-head { animation: rise .32s var(--ease-out-soft) backwards; }
.pop-text { animation: pop .42s var(--ease-spring) .1s backwards; }
.hd-in { animation: rise .36s var(--ease-out-soft) backwards; animation-delay: calc(var(--i) * 45ms); }

/* 头部名物区 */
.hd-head {
  display: flex; gap: 16px; align-items: center;
  padding-right: 28px; margin-bottom: 16px;
}
.hd-cover {
  position: relative; width: 84px; height: 84px; flex-shrink: 0;
  border-radius: 14px; overflow: hidden;
  background: var(--green-50);
  border: 1px solid rgba(120, 95, 60, 0.18);
  box-shadow: 0 4px 12px -3px rgba(74, 56, 32, 0.16);
}
.hd-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.hd-title-zone { flex: 1; min-width: 0; }
.hd-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.hd-title-row h3 {
  font-family: var(--font-serif); font-size: 23px; font-weight: 700;
  color: var(--ink-900); line-height: 1.2; letter-spacing: 0.03em;
}
.hd-cat {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px;
  background: var(--green-50); color: var(--green-text);
  border: 1px solid rgba(58, 122, 94, 0.22);
}
.hd-catalog {
  display: inline-flex; align-items: center; gap: 4px;
  margin-top: 5px; font-size: 11.5px; color: var(--ink-400);
}
.hd-props { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.prop-pill {
  font-size: 11.5px; font-weight: 600; padding: 2px 9px; border-radius: 999px;
  line-height: 1.5; border: 1px solid transparent;
}
.prop-pill.tone-warm { background: var(--amber-50); color: var(--amber-text); border-color: rgba(176, 124, 46, 0.24); }
.prop-pill.tone-cool { background: #e5f2ef; color: #24665c; border-color: rgba(36, 102, 92, 0.2); }
:root:is(.van-theme-dark, [data-theme="dark"]) .prop-pill.tone-cool { background: #1e3330; color: #84c7bc; border-color: rgba(132, 199, 188, 0.24); }
.prop-pill.tone-neutral { background: var(--green-50); color: var(--green-text); border-color: rgba(58, 122, 94, 0.22); }
.prop-pill.tone-flavor {
  background: rgba(120, 95, 60, 0.06); color: var(--ink-600);
  border-color: var(--card-border); font-weight: 500;
}

/* 归经横栏 */
.hd-meridians {
  display: flex; align-items: center; gap: 12px;
  padding: 11px 0; border-top: 1px dashed var(--card-border);
}
.hd-sec-label {
  font-size: 12px; font-weight: 700; color: var(--green-text);
  letter-spacing: 0.04em; flex-shrink: 0;
}
.m-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.m-chip {
  font-size: 12.5px; font-weight: 500; color: var(--ink-900);
  background: rgba(120, 95, 60, 0.06); border: 1px solid var(--card-border);
  padding: 2px 10px; border-radius: 7px;
}

/* 传统功效区 */
.hd-sec { padding: 12px 0; border-top: 1px dashed var(--card-border); }
.hd-sec-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 9px; }
.hd-src-note { font-size: 11px; color: var(--ink-400); }
.fn-chips { display: flex; flex-wrap: wrap; gap: 7px; }
.fn-chip {
  font-size: 13px; font-weight: 600; color: var(--green-900);
  background: var(--green-50); border: 1px solid rgba(58, 122, 94, 0.22);
  padding: 4px 12px; border-radius: 8px; letter-spacing: 0.02em;
}
:root:is(.van-theme-dark, [data-theme="dark"]) .fn-chip { color: var(--green-text); }

/* HERB 英文原文折叠区 */
.en-raw-wrap { margin-top: 10px; }
.en-toggle {
  display: inline-flex; align-items: center; gap: 4px;
  border: none; background: none; padding: 2px 0;
  font-size: 11.5px; color: var(--ink-400); cursor: pointer; font-family: inherit;
  transition: color var(--dur-fast) ease;
}
.en-toggle:hover { color: var(--green-text); }
.en-chev { transition: transform var(--dur-fast) ease; }
.en-chev.open { transform: rotate(180deg); }
.en-box {
  margin-top: 7px; padding: 9px 12px; border-radius: 9px;
  background: rgba(120, 95, 60, 0.045);
  border-left: 2.5px solid rgba(58, 122, 94, 0.38);
  display: flex; flex-direction: column; gap: 7px;
}
.en-tag {
  display: block; font-size: 10.5px; font-weight: 600;
  color: var(--ink-400); letter-spacing: 0.03em; margin-bottom: 2px;
}
.en-item p { font-size: 12px; color: var(--ink-600); line-height: 1.55; margin: 0; }

/* 活性成分数据舱（左数右文，永不断字） */
.hd-data-pod {
  display: flex; align-items: center; gap: 14px;
  margin: 4px 0 12px; padding: 12px 14px;
  background: var(--green-50);
  border: 1px solid rgba(58, 122, 94, 0.18);
  border-radius: 12px;
}
.pod-num-box {
  min-width: 68px; text-align: center; flex-shrink: 0;
  display: flex; flex-direction: column; align-items: center;
}
.pod-num {
  font-family: var(--font-serif); font-size: 26px; font-weight: 700;
  color: var(--green-text); line-height: 1.1; font-variant-numeric: tabular-nums;
}
.pod-unit { font-size: 11px; color: var(--ink-600); margin-top: 3px; white-space: nowrap; }
.pod-divider { width: 1px; align-self: stretch; background: rgba(58, 122, 94, 0.16); flex-shrink: 0; }
.pod-info { flex: 1; min-width: 0; }
.pod-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 999px;
  margin-bottom: 4px;
}
.pod-badge.ok { background: rgba(58, 122, 94, 0.14); color: var(--green-text); }
.pod-badge.herb { background: var(--amber-50); color: var(--amber-text); border: 1px solid rgba(176, 124, 46, 0.24); }
.pod-badge.muted { background: rgba(120, 95, 60, 0.08); color: var(--ink-400); }
.pod-info p { font-size: 12px; color: var(--ink-600); line-height: 1.5; margin: 0; }

/* 底部联动按钮栏 */
.hd-actions { display: flex; gap: 10px; margin-top: 14px; }
.hd-act-sub { flex: 0 0 auto; }
.hd-act-main { flex: 1; }
</style>
