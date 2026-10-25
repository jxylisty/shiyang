<script setup>
import { computed } from 'vue'

// 环形进度：SVG stroke-dashoffset + spring 过渡，数值变化时环平滑生长
const props = defineProps({
  value: { type: Number, default: 0 },   // 0~100
  size: { type: Number, default: 72 },
  stroke: { type: Number, default: 7 },
  color: { type: String, default: 'var(--green-600)' },
  track: { type: String, default: 'var(--green-100)' },
  label: { type: String, default: '' },  // 圆心文字，空则显示整数百分比
})

const r = computed(() => (props.size - props.stroke) / 2)
const c = computed(() => 2 * Math.PI * r.value)
const dash = computed(() => (Math.min(100, Math.max(0, props.value)) / 100) * c.value)
</script>

<template>
  <div class="ring" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" viewBox="0 0 100 100">
      <circle cx="50" cy="50" :r="(50 - stroke / 2)" fill="none" :stroke="track" :stroke-width="stroke" />
      <circle class="fg" cx="50" cy="50" :r="50 - stroke / 2" fill="none" :stroke="color" :stroke-width="stroke"
        stroke-linecap="round" :stroke-dasharray="c" :stroke-dashoffset="c - dash"
        transform="rotate(-90 50 50)" />
    </svg>
    <span class="ring-label">{{ label || Math.round(value) + '%' }}</span>
  </div>
</template>

<style scoped>
.ring { position: relative; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ring svg { display: block; }
.fg { transition: stroke-dashoffset var(--dur-slow) var(--ease-out-soft); }
.ring-label {
  position: absolute; font-size: 14px; font-weight: 700; color: var(--ink-900);
  font-variant-numeric: tabular-nums;
}
</style>
