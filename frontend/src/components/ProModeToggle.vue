<script setup>
// 专业模式快捷开关卡：未登录用户进不了「我的」，在详情页/鉴方页也给一个入口
import { FlaskConical } from '@lucide/vue'
import { proMode } from '../utils/proMode'

defineProps({
  hint: { type: String, default: '入血成分预测、作用靶点、网络图等研究数据' },
})
</script>

<template>
  <div class="card pro-toggle" :class="{ on: proMode }">
    <FlaskConical :size="18" :stroke-width="2" class="pt-icon" />
    <div class="pt-text">
      <b>{{ proMode ? '专业模式已开启' : '想看科学依据？' }}</b>
      <span>{{ proMode ? '正在显示研究分析，关闭后回到简洁版' : `打开专业模式，查看${hint}` }}</span>
    </div>
    <button class="switch-btn" :class="{ on: proMode }" role="switch" :aria-checked="proMode"
            aria-label="专业模式" @click="proMode = !proMode">
      <span class="knob"></span>
    </button>
  </div>
</template>

<style scoped>
.pro-toggle { display: flex; align-items: center; gap: 12px; }
.pt-icon { color: var(--green-text); flex-shrink: 0; }
.pt-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.pt-text b { font-size: 14px; color: var(--ink-900); }
.pt-text span { font-size: 12px; color: var(--ink-400); line-height: 1.5; }
/* 开关样式与「我的·设置」同款（Me.vue 内为 scoped，这里复刻一份） */
.switch-btn { flex-shrink: 0; width: 46px; height: 26px; border-radius: 13px; border: none; background: #d7e0db; position: relative; cursor: pointer; transition: background .2s; }
.switch-btn.on { background: var(--green-600); }
.switch-btn .knob { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: left .2s var(--ease-spring); }
.switch-btn.on .knob { left: 23px; }
</style>
