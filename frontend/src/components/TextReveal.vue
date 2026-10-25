<script setup>
import { computed } from 'vue'

// 中文逐字 reveal：拆 span + 错峰 delay，入场时逐字上浮
const props = defineProps({
  text: { type: String, required: true },
  step: { type: Number, default: 35 },   // 每字延迟 ms
  delay: { type: Number, default: 0 },   // 起始延迟 ms
})

const chars = computed(() => Array.from(props.text))
</script>

<template>
  <span class="tr" aria-label="text">
    <span
      v-for="(ch, i) in chars" :key="i" aria-hidden="true"
      class="tr-ch" :style="{ animationDelay: delay + i * step + 'ms' }"
    >{{ ch }}</span>
  </span>
</template>

<style scoped>
.tr { display: inline; }
.tr-ch {
  display: inline-block;
  animation: tr-in 0.5s var(--ease-out-soft) backwards;
  white-space: pre;
}
@keyframes tr-in { from { opacity: 0; transform: translateY(0.5em); } }
</style>
