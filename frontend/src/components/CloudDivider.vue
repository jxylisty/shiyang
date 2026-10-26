<script setup>
/**
 * 云纹分隔线（古典装饰）
 * 两段半圆云头 + 两端内卷云尾，是传统云纹最核心的语汇。
 * 纯内联 SVG，无外部依赖、无网络请求；颜色随 currentColor。
 */
defineProps({
  width: { type: [Number, String], default: 54 },
  label: { type: String, default: '' },
})
</script>

<template>
  <div class="orn-divider" role="presentation">
    <svg v-if="!label" :width="width" height="24" viewBox="0 0 140 70"
         fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" aria-hidden="true">
      <path d="M18 52 C10 52 6 46 10 41 C14 36 22 37 23 44"/>
      <path d="M23 44 C23 30 33 20 47 20 C61 20 71 30 71 44"/>
      <path d="M71 44 C71 30 81 20 95 20 C109 20 119 30 119 44"/>
      <path d="M119 44 C120 37 128 36 132 41 C136 46 132 52 124 52"/>
      <path d="M18 52 H124"/>
    </svg>
    <span v-if="label" class="orn-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.orn-label {
  font-family: var(--font-serif);
  font-size: 12px; letter-spacing: 0.28em; text-indent: 0.28em;
  color: var(--ink-400); white-space: nowrap;
}
</style>
