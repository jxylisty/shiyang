<script setup>
/**
 * HScroll —— 横向滚动容器 + 常显自绘滚动条
 *
 * 为什么不直接用原生滚动条：Chrome 默认是浮层滚动条，既不占布局空间、
 * 静止几秒还会自动淡出。内容被裁切时用户看不出「右边还有」，横滑列表
 * 因此变成隐性交互。本组件把滚动条改为常显轨道 + 随滚动移动的滑块。
 *
 * 用法：
 *   <HScroll class="my-rail">
 *     <div class="card" v-for="..." />
 *   </HScroll>
 *
 * 样式：滚动容器固定为内部 .h-scroll，调用方用 :deep(.h-scroll) 写布局
 *   .my-rail :deep(.h-scroll) { display: flex; gap: 12px; }
 * 可调令牌：--hscroll-bar-h（轨道高）/ --hscroll-bar-mt（上边距）
 *          --hscroll-track / --hscroll-thumb（配色，暗色主题已内置）
 *
 * 内容异步渲染时可调用暴露的 refresh() 重新判定是否溢出。
 */
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'

const props = defineProps({
  // 滑块最小宽度（百分比）：内容超长时避免滑块小到看不见
  minThumb: { type: Number, default: 12 },
})

const el = ref(null)
const scrollable = ref(false)
const ratio = ref(1)      // 可视宽度 / 内容宽度
const progress = ref(0)   // 0~1 已滚动比例

function refresh() {
  const node = el.value
  if (!node) return
  const max = node.scrollWidth - node.clientWidth
  scrollable.value = max > 1
  ratio.value = node.scrollWidth ? node.clientWidth / node.scrollWidth : 1
  progress.value = max > 0 ? node.scrollLeft / max : 0
}

const thumbStyle = computed(() => {
  const w = Math.max(ratio.value * 100, props.minThumb)
  return { width: `${w}%`, left: `${progress.value * (100 - w)}%` }
})

let ro = null
onMounted(() => {
  refresh()
  // 视口变化会改变可容纳的卡片数（溢出与否随之变化）
  if (typeof ResizeObserver !== 'undefined' && el.value) {
    ro = new ResizeObserver(refresh)
    ro.observe(el.value)
  }
  window.addEventListener('resize', refresh)
})
onBeforeUnmount(() => {
  ro?.disconnect()
  window.removeEventListener('resize', refresh)
})

defineExpose({ refresh, el })
</script>

<template>
  <div class="h-scroll-wrap">
    <div ref="el" class="h-scroll" @scroll="refresh">
      <slot />
    </div>
    <div v-show="scrollable" class="h-bar" aria-hidden="true">
      <span class="h-thumb" :style="thumbStyle"></span>
    </div>
  </div>
</template>

<style scoped>
.h-scroll-wrap { position: relative; }
.h-scroll {
  overflow-x: auto;
  /* 原生条隐藏，改用下方自绘条（浮层条静止淡出，无法承担提示作用） */
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}
.h-scroll::-webkit-scrollbar { display: none; }

.h-bar {
  position: relative;
  height: var(--hscroll-bar-h, 5px);
  margin: var(--hscroll-bar-mt, 10px) 0 2px;
  background: var(--hscroll-track, rgba(120, 95, 60, 0.13));
  border-radius: 3px;
  overflow: hidden;
}
.h-thumb {
  position: absolute; top: 0; height: 100%;
  background: var(--hscroll-thumb, rgba(120, 95, 60, 0.55));
  border-radius: 3px;
  transition: left .12s linear;
}
:root[data-theme="dark"] .h-bar { background: rgba(230, 221, 204, 0.12); }
:root[data-theme="dark"] .h-thumb { background: rgba(230, 221, 204, 0.45); }

@media (prefers-reduced-motion: reduce) {
  .h-thumb { transition: none; }
}
</style>
