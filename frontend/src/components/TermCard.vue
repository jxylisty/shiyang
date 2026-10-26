<script setup>
/**
 * 节气推荐卡（T2-9）：当前节气 + 食养主题 + 主题方子 + 下个节气倒计时
 */
import { ref, onMounted } from 'vue'
import { Sprout, CalendarClock } from '@lucide/vue'
import AppIcon from './AppIcon.vue'
import { getTermCurrent, matImg } from '../api'

const info = ref(null)
onMounted(async () => {
  try { info.value = (await getTermCurrent()).data.data } catch { /* 静默 */ }
})

const fmtDate = (d) => {
  const [y, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}
</script>

<template>
  <div class="card term-card" v-if="info">
    <div class="t-head">
      <div class="t-cur">
        <Sprout :size="16" />
        <b>{{ info.current.name }}</b>
        <span class="t-date">{{ fmtDate(info.current.date) }} 起 · 第 {{ info.current.days_in }} 天</span>
      </div>
      <div class="t-next" v-if="info.upcoming.length">
        <CalendarClock :size="13" />
        {{ info.upcoming[0].name }}还有 {{ info.next_in_days }} 天
      </div>
    </div>
    <p class="t-tip">{{ info.current.theme.tip }}</p>
    <div class="t-recipes" v-if="info.recipes.length">
      <router-link v-for="r in info.recipes.slice(0, 3)" :key="r.id" :to="`/recipes/${r.id}`" class="t-r pressable">
        <span class="t-r-img">
          <img v-if="r.materials?.length" :src="matImg(r.materials[0])" alt="" loading="lazy" @error="e => e.target.style.display = 'none'" />
          <AppIcon v-else :name="r.type === '药膳' ? 'dish' : 'tea'" :size="18" />
        </span>
        <div>
          <b>{{ r.name }}</b>
          <span>{{ r.oneliner }}</span>
        </div>
      </router-link>
    </div>
    <router-link v-if="info.scene" :to="{ path: '/recipes', query: { scene: info.scene } }"
                 class="t-more">{{ info.current.name }}食养清单 →</router-link>
  </div>
</template>

<style scoped>
.term-card { padding: 14px 16px; }
.t-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.t-cur { display: flex; align-items: center; gap: 6px; color: var(--green-700); }
.t-cur b { font-size: 16px; color: var(--ink-900); }
.t-date { font-size: 11px; color: var(--ink-400); }
.t-next { font-size: 11px; color: var(--ink-600); display: inline-flex; align-items: center; gap: 3px; }
.t-tip { font-size: 12px; color: var(--ink-600); margin: 8px 0 10px; }
.t-recipes { display: flex; flex-direction: column; gap: 8px; }
.t-r { display: flex; gap: 10px; align-items: center; text-decoration: none; color: inherit;
       padding: 8px; border-radius: 10px; background: var(--green-50); }
.t-r-img { width: 38px; height: 38px; border-radius: 8px; flex-shrink: 0; overflow: hidden;
           display: flex; align-items: center; justify-content: center;
           background: var(--green-100); color: var(--green-700); }
.t-r-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.t-r b { font-size: 13px; display: block; }
.t-r span { font-size: 11px; color: var(--ink-600); display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
.t-more { display: inline-block; margin-top: 10px; font-size: 12px; color: var(--green-700); text-decoration: none; }
</style>
