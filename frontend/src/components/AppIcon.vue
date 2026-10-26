<script setup>
// 自绘图标集的统一渲染组件：线性、currentColor、与 lucide 相同的 size/stroke-width 接口
import { icons } from './icons'

defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 24 },
  strokeWidth: { type: [Number, String], default: 1.8 },
})
</script>

<template>
  <svg
    aria-hidden="true"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    v-html="icons[name] || ''"
  />
</template>
