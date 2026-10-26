<script setup>
// 药材图鉴：34 味药食同源药材，图 + 性味 + 功效摘要，点开看归经/化合物数
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { listHerbs, matImg } from '../api'

const route = useRoute()
const items = ref([])
const loading = ref(true)
const loadError = ref(false)
const kw = ref('')
const active = ref(null)      // popup 详情
const imgFailed = ref({})

let timer = null
let reqId = 0
async function load() {
  const id = ++reqId
  loading.value = true
  loadError.value = false
  try {
    const d = (await listHerbs(kw.value.trim())).data.data
    if (id !== reqId) return   // 已有更新的请求发出，丢弃本次结果
    items.value = d.items
    // 全局搜索跳转：?h=药材名 → 数据到位后直接打开详情弹窗
    const h = route.query.h
    if (h) {
      const hit = items.value.find(x => x.name === h)
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
  timer = setTimeout(load, 300)
}
onMounted(load)

const hideImg = (name) => { imgFailed.value[name] = true }
</script>

<template>
  <div class="page">
    <van-search v-model="kw" placeholder="搜药材名或拼音，如：枸杞 / jujube" @update:model-value="onSearch" class="search-box" />

    <div v-if="loading" class="herb-grid">
      <div v-for="i in 8" :key="i" class="card herb-card">
        <div class="h-img sk-anim"></div>
        <div class="sk-line w70 sk-anim"></div>
        <div class="sk-line w50 sk-anim"></div>
      </div>
    </div>
    <van-empty v-else-if="loadError" image="error" description="服务暂时不可用，请稍后重试" />
    <van-empty v-else-if="!items.length" image="search" description="没有找到相关药材" />

    <template v-else>
      <p class="count">共 {{ items.length }} 味 · 点开看性味归经与成分</p>
      <div class="herb-grid">
        <button v-for="(h, i) in items" :key="h.id" class="card herb-card"
                :style="{ '--d': `${Math.min(i, 16) * 40}ms` }" @click="active = h">
          <div class="h-img">
            <img v-if="!imgFailed[h.name]" :src="matImg(h.name)" :alt="h.name" loading="lazy" @error="hideImg(h.name)" />
            <span v-else class="h-fallback">{{ h.name[0] }}</span>
          </div>
          <b class="h-name">{{ h.name }}</b>
          <span class="h-nature" v-if="h.nature || h.flavor">{{ [h.nature, h.flavor].filter(Boolean).join(' · ') }}</span>
          <span class="h-count">{{ h.compound_count }} 个活性成分</span>
        </button>
      </div>
    </template>

    <!-- 详情弹层 -->
    <van-popup :show="!!active" position="bottom" round
               :style="{ maxWidth: '750px', margin: '0 auto' }" @update:show="() => active = null" @click-overlay="active = null">
      <div class="h-detail" v-if="active">
        <div class="hd-head">
          <div class="h-img hd-img">
            <img v-if="!imgFailed[active.name]" :src="matImg(active.name)" :alt="active.name" @error="hideImg(active.name)" />
            <span v-else class="h-fallback">{{ active.name[0] }}</span>
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
          <p>关联 <b class="hd-num">{{ active.compound_count }}</b> 个活性成分（含预测入血概率与靶点数据），
             可在<a href="/compounds" class="hd-link">成分库</a>按「来源药材」继续查看。</p>
        </div>
        <p class="hd-note hd-in" style="--i: 4" v-if="active.food_catalog_batch">卫健委药食同源目录：第 {{ active.food_catalog_batch }} 批</p>
        <button class="btn block hd-close hd-in" style="--i: 5" @click="active = null">关闭</button>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.search-box { margin-bottom: 10px; padding: 0; background: transparent; }
.count { font-size: 12px; color: var(--ink-400); margin-bottom: 10px; }
.herb-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (min-width: 900px) { .herb-grid { grid-template-columns: repeat(5, 1fr); } }
.herb-card {
  padding: 10px 8px; text-align: center; cursor: pointer; border: none; font: inherit;
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  animation: rise .4s var(--ease-out-soft) backwards; animation-delay: var(--d, 0ms);
  transition: scale var(--dur-fast) var(--ease-snap);
}
.herb-card:active { scale: 0.95; }
.h-img {
  width: 100%; aspect-ratio: 1; border-radius: 10px; overflow: hidden;
  background: var(--green-50); margin-bottom: 6px; position: relative;
}
.h-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.h-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 26px; font-weight: 700; color: var(--green-700); }
.h-name { font-size: 14px; }
.h-nature { font-size: 11px; color: var(--amber-text); }
.h-count { font-size: 10px; color: var(--ink-400); }

/* 骨架屏（shimmer 与 .sk-anim 均用全局定义，style.css） */
.sk-line { height: 12px; border-radius: 6px; width: 80%; }
.sk-line.w70 { width: 70%; }
.sk-line.w50 { width: 50%; }

/* 弹层内容渐入错峰 */
.h-detail .hd-head { animation: rise .35s var(--ease-out-soft) backwards; }
.pop-text { animation: pop .45s var(--ease-spring) .15s backwards; }
.hd-in { animation: rise .4s var(--ease-out-soft) backwards; animation-delay: calc(var(--i) * 60ms); }

/* 详情弹层 */
.h-detail { padding: 20px 16px; }
.hd-head { display: flex; gap: 14px; align-items: center; margin-bottom: 14px; }
.hd-img { width: 72px; flex-shrink: 0; }
.hd-head h3 { font-size: 19px; }
.hd-sub { font-size: 13px; color: var(--amber-text); margin-top: 2px; }
.hd-sec { padding: 10px 0; border-top: 1px dashed var(--green-100); }
.hd-sec b { font-size: 12px; color: var(--green-700); display: block; margin-bottom: 4px; }
.hd-sec p { font-size: 13.5px; color: var(--ink-600); line-height: 1.7; }
.hd-num { color: var(--green-700); }
.hd-link { color: var(--green-700); }
.hd-note { font-size: 11px; color: var(--ink-400); margin-top: 6px; }
.hd-close { margin-top: 14px; }
</style>
