<script setup>
// 首页证据链/日常轻养列表行：缩略图 + 名称/一句话 + 时长 + 箭头，图挂了走图标兜底
import { ref, computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { matImg } from '../api'

const props = defineProps({ recipe: { type: Object, required: true } })
const imgFailed = ref(false)
const cover = computed(() => matImg(props.recipe.materials?.[0] || ''))
// 时长优先取「N分钟」；否则取完整 duration（如「煲1.5小时」）；都没有才回退类型
const dur = computed(() => {
  const d = props.recipe.duration || ''
  return d.match(/\d+\s*分钟/)?.[0] || d || props.recipe.type
})
</script>

<template>
  <router-link :to="`/recipes/${recipe.id}`" class="recipe-row">
    <span class="rr-img">
      <img v-if="cover && !imgFailed" :src="cover" alt="" loading="lazy" @error="imgFailed = true" />
      <AppIcon v-else :name="recipe.type === '药膳' ? 'dish' : 'tea'" :size="20" />
    </span>
    <span class="rr-main">
      <span class="r-name">{{ recipe.name }}</span>
      <span class="r-one">{{ recipe.oneliner }}</span>
    </span>
    <span class="rr-meta">{{ dur }}</span>
    <AppIcon name="chevron" :size="14" class="rr-go" />
  </router-link>
</template>

<style scoped>
.recipe-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 0;
  border-bottom: 1px solid var(--green-100); text-decoration: none; color: inherit;
}
.recipe-row:last-of-type { border-bottom: none; }
.rr-img {
  width: 44px; height: 44px; border-radius: 10px; overflow: hidden; flex-shrink: 0;
  background: var(--green-100); color: var(--tile-ink);
  display: flex; align-items: center; justify-content: center;
}
.rr-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.rr-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.r-name { font-size: 14.5px; font-weight: 600; color: var(--ink-900); transition: color var(--dur-fast) ease; }
.r-one { font-size: 12px; color: var(--ink-600); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rr-meta { font-size: 11px; color: var(--ink-400); flex-shrink: 0; font-variant-numeric: tabular-nums; }
.rr-go { color: var(--ink-400); flex-shrink: 0; transition: translate var(--dur-fast) var(--ease-snap), color var(--dur-fast) ease; }
@media (hover: hover) {
  .recipe-row:hover .r-name { color: var(--green-text); }
  .recipe-row:hover .rr-go { translate: 2px 0; color: var(--green-text); }
}
</style>
