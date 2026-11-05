<script setup>
// 「说人话」白话解读卡（大众层主视觉）
// 内容为 AI 生成：必须显示来源标注与未审校提示（AGENTS.md §2.6），不得移除
import { Sparkles } from '@lucide/vue'

defineProps({
  plain: { type: Object, default: null },   // { headline, suits, caution, ingredients[], reviewed }
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  title: { type: String, default: '这个方子是干嘛的' },
})
</script>

<template>
  <div class="section-title">{{ title }}</div>
  <div class="card plain-card">
    <template v-if="loading">
      <div class="skl" style="height: 18px; width: 80%;"></div>
      <div class="skl" style="height: 13px; width: 95%; margin-top: 12px;"></div>
      <div class="skl" style="height: 13px; width: 70%; margin-top: 8px;"></div>
      <p class="pc-wait">正在用大白话整理…</p>
    </template>
    <p v-else-if="error" class="pc-wait">{{ error }}</p>
    <template v-else-if="plain">
      <p class="pc-head">{{ plain.headline }}</p>
      <div class="pc-row">
        <span class="pc-label ok">适合</span>
        <p>{{ plain.suits }}</p>
      </div>
      <div class="pc-row">
        <span class="pc-label warn">注意</span>
        <p>{{ plain.caution }}</p>
      </div>
      <template v-if="plain.ingredients?.length">
        <p class="pc-sub">每样料起什么作用</p>
        <div v-for="it in plain.ingredients" :key="it.name" class="pc-ing">
          <b>{{ it.name }}</b><span>{{ it.role }}</span>
        </div>
      </template>
      <p class="pc-src">
        <Sparkles :size="12" :stroke-width="2.2" />
        AI 根据传统资料改写{{ plain.reviewed ? '，已经人工审校' : '，尚未经医药专业人员审校' }}，仅供参考
      </p>
    </template>
    <p v-else class="pc-wait">这个方子的白话解读还在整理中，可以先看下方的配方与禁忌。</p>
  </div>
</template>

<style scoped>
.plain-card { line-height: 1.65; }
.pc-head { font-size: 16px; font-weight: 700; color: var(--ink-900); font-family: var(--font-serif); margin-bottom: 10px; }
.pc-row { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; font-size: 13.5px; color: var(--ink-600); }
.pc-row p { flex: 1; }
.pc-label { flex-shrink: 0; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 8px; margin-top: 2px; }
.pc-label.ok { background: var(--green-100); color: var(--green-text); }
.pc-label.warn { background: var(--red-50); color: var(--red-text); }
.pc-sub { font-size: 12px; font-weight: 700; color: var(--green-text); margin: 12px 0 4px; }
.pc-ing { display: flex; gap: 8px; padding: 5px 0; border-bottom: 1px dashed var(--green-50); font-size: 13px; }
.pc-ing:last-of-type { border-bottom: none; }
.pc-ing b { flex-shrink: 0; min-width: 4em; color: var(--ink-900); }
.pc-ing span { color: var(--ink-600); }
.pc-src { display: flex; align-items: center; gap: 4px; margin-top: 12px; font-size: 11px; color: var(--ink-400); }
.pc-wait { font-size: 12.5px; color: var(--ink-400); margin-top: 8px; }
</style>
