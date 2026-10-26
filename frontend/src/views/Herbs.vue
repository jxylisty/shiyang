<script setup>
// 药材图鉴：网格卡片，点开弹窗显示性味归经、功效与成分数（对标中华本草/药典）
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { listHerbs, matImg } from '../api'

const route = useRoute()
const items = ref([])
const loading = ref(true)
const loadError = ref(false)
const kw = ref('')
const active = ref(null)      // popup 详情
const imgFailed = ref({})
// 桌面端详情用居中弹窗，手机保持底部抽屉（van-popup--bottom 只有 left:0，宽屏下 margin auto 不生效）
const mqWide = window.matchMedia('(min-width: 900px)')
const isWide = ref(mqWide.matches)
mqWide.addEventListener('change', (e) => { isWide.value = e.matches })

let timer = null
let reqId = 0
async function load() {
  const id = ++reqId
  loading.value = true
  loadError.value = false
  try {
    const q = kw.value.trim()
    const d = (await listHerbs(q)).data.data
    if (id !== reqId) return
    items.value = d.items
    // 路由带 ?h=药材名 时（如顶栏全局搜索跳过来）自动弹详情
    const target = route.query.h
    if (target && !active.value) {
      const hit = items.value.find(x => x.name === target)
      if (hit) active.value = hit
    }
  } catch {
    if (id !== reqId) return
    loadError.value = true
    items.value = []
  } finally { if (id === reqId) loading.value = false }
}

function onSearch() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(load, 250)
}

onMounted(load)

const hideImg = (name) => { imgFailed.value[name] = true }
</script>

<template>
  <div class="page">
    <div class="card search-card">
      <van-search v-model="kw" placeholder="搜药材名 / 性味 / 功效（如：枸杞 / 甘 / 润肺）" @update:model-value="onSearch" class="search-box" />
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
    <van-empty v-else-if="!items.length" image="search" description="未找到匹配药材，换个词试试" />

    <template v-else>
      <p class="count">共 <b>{{ items.length }}</b> 味药食同源药材</p>
      <div class="herb-grid">
        <button v-for="(h, i) in items" :key="h.id" class="card herb-card pressable"
                :style="{ '--d': `${Math.min(i, 20) * 25}ms` }"
                @click="active = h">
          <div class="h-img">
            <img v-if="!imgFailed[h.name]" :src="matImg(h.name)" :alt="h.name" loading="lazy" @error="hideImg(h.name)" />
            <span v-else class="h-fallback"><AppIcon name="herb" :size="30" /></span>
          </div>
          <b class="h-name">{{ h.name }}</b>
          <span class="h-nature" v-if="h.nature || h.flavor">{{ [h.nature, h.flavor].filter(Boolean).join(' · ') }}</span>
          <span class="h-count">{{ h.compound_count }} 个活性成分</span>
        </button>
      </div>
    </template>

    <!-- 详情弹层 -->
    <van-popup :show="!!active" :position="isWide ? 'center' : 'bottom'" round
               :class="{ 'h-popup-wide': isWide }"
               @update:show="() => active = null" @click-overlay="active = null">
      <div class="h-detail" v-if="active">
        <div class="hd-head">
          <div class="h-img hd-img">
            <img v-if="!imgFailed[active.name]" :src="matImg(active.name)" :alt="active.name" @error="hideImg(active.name)" />
            <span v-else class="h-fallback"><AppIcon name="herb" :size="30" /></span>
          </div>
          <div>
            <h3 class="pop-text">{{ active.name }}</h3>
            <p class="hd-sub">{{ [active.nature, active.flavor].filter(Boolean).join(' · ') || '性味待补' }}</p>
          </div>
        </div>
        <div class="hd-sec hd-in" style="--i: 1" v-if="active.meridians"><b>归经</b><p>{{ active.meridians }}</p></div>
        <div class="hd-sec hd-in" style="--i: 2" v-if="active.functions"><b>功效</b><p>{{ active.functions }}</p></div>
        <div class="hd-sec hd-in" style="--i: 3">
          <b>成分数据</b>
          <p class="hd-comp">关联 <span class="hd-num">{{ active.compound_count }}</span> 个活性成分，含预测入血概率与靶点数据</p>
          <router-link to="/compounds" class="hd-goto">到成分库按「来源药材」继续查看<AppIcon name="chevron" :size="12" :stroke-width="2.4" /></router-link>
        </div>
        <p class="hd-note hd-in" style="--i: 4" v-if="active.food_catalog_batch">卫健委药食同源目录：第 {{ active.food_catalog_batch }} 批</p>
        <button class="btn ghost block hd-close hd-in" style="--i: 5" @click="active = null">关闭</button>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.search-card { padding: 12px 14px; margin-bottom: 12px; }
.search-box { padding: 0; background: transparent; }
.count { font-size: 12.5px; color: var(--ink-400); margin-bottom: 10px; }
.count b { color: var(--ink-900); font-variant-numeric: tabular-nums; }

.herb-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (min-width: 600px) { .herb-grid { grid-template-columns: repeat(4, 1fr); gap: 12px; } }
@media (min-width: 900px) { .herb-grid { grid-template-columns: repeat(5, 1fr); gap: 14px; } }

.herb-card {
  padding: 12px 8px; text-align: center; cursor: pointer; border: 1px solid var(--card-border); font: inherit;
  display: flex; flex-direction: column; align-items: center; gap: 3px; margin-bottom: 0;
  animation: rise .4s var(--ease-out-soft) backwards; animation-delay: var(--d, 0ms);
  transition: transform var(--dur-fast) var(--ease-snap), box-shadow var(--dur-med) ease;
}
.herb-card:active { scale: 0.95; }
.h-img {
  width: 100%; aspect-ratio: 1; border-radius: 10px; overflow: hidden;
  background: var(--green-50); margin-bottom: 6px; position: relative;
  border: 1px solid rgba(0,0,0,0.03);
}
.h-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.h-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--tile-ink); }
.h-name { font-family: var(--font-serif); font-size: 15px; color: var(--ink-900); font-weight: 700; }
.h-nature { font-size: 11px; color: var(--amber-text); }
.h-count { font-size: 10.5px; color: var(--ink-400); font-variant-numeric: tabular-nums; }

/* 骨架屏 */
.sk-line { height: 12px; border-radius: 6px; width: 80%; }
.sk-line.w70 { width: 70%; }
.sk-line.w50 { width: 50%; }

/* 弹层内容渐入错峰 */
.h-detail .hd-head { animation: rise .35s var(--ease-out-soft) backwards; }
.pop-text { animation: pop .45s var(--ease-spring) .15s backwards; }
.hd-in { animation: rise .4s var(--ease-out-soft) backwards; animation-delay: calc(var(--i) * 60ms); }

/* 详情弹层 */
.h-popup-wide { width: 520px; max-width: 92vw; border-radius: 16px; border: 1px solid var(--card-border); }
.h-detail { padding: 22px 18px; max-height: 80vh; overflow-y: auto; }
.hd-head { display: flex; gap: 14px; align-items: center; margin-bottom: 14px; }
.hd-img { width: 72px; flex-shrink: 0; border-radius: 12px; }
.hd-head h3 { font-family: var(--font-serif); font-size: 20px; font-weight: 700; color: var(--ink-900); }
.hd-sub { font-size: 13px; color: var(--amber-text); margin-top: 3px; }
.hd-sec { padding: 10px 0; border-top: 1px dashed var(--green-100); }
.hd-sec b { font-size: 12px; color: var(--green-700); display: block; margin-bottom: 4px; }
.hd-sec p { font-size: 13.5px; color: var(--ink-600); line-height: 1.7; }
.hd-comp { display: flex; align-items: baseline; gap: 7px; }
.hd-num { font-size: 22px; font-weight: 700; color: var(--green-700); font-variant-numeric: tabular-nums; }
.hd-goto { display: inline-flex; align-items: center; gap: 3px; margin-top: 6px; font-size: 12.5px; color: var(--green-700); text-decoration: none; font-weight: 500; }
.hd-goto:hover { text-decoration: underline; }
.hd-note { font-size: 11px; color: var(--ink-400); margin-top: 6px; }
.hd-close { margin-top: 16px; }
</style>
