<script setup>
/**
 * 证据链溯源卡（T1-3）：A/B/C 三级证据的可展开列表
 * A=权威出处（方子来源/官方目录）B=实验数据库（含 PMID 直达）C=模型预测
 */
import { ref, watch } from 'vue'
import { BadgeCheck, Database, FlaskConical, ExternalLink, ChevronDown } from '@lucide/vue'
import { getEvidence } from '../api'

const props = defineProps({ recipeId: { type: Number, required: true } })
const data = ref(null)
const open = ref(false)

const ICONS = { A: BadgeCheck, B: Database, C: FlaskConical }

async function load() {
  try { data.value = (await getEvidence(props.recipeId)).data.data } catch { /* 静默 */ }
}
watch(() => props.recipeId, load, { immediate: true })
</script>

<template>
  <div class="card ev-card" v-if="data">
    <button class="ev-head" @click="open = !open">
      <span class="ev-title">证据链与溯源</span>
      <span class="ev-badges">
        <span v-for="(meta, lv) in data" :key="lv" class="ev-badge" :style="{ '--lv': meta.color }">{{ lv }}</span>
      </span>
      <ChevronDown :size="16" class="ev-arrow" :class="{ flip: open }" />
    </button>

    <p class="ev-note" v-if="!open">三级证据：A 权威出处 · B 实验数据库 · C 模型预测（点开看每条出处）</p>

    <div v-show="open" class="ev-body">
      <div v-for="(meta, lv) in data" :key="lv" class="ev-group">
        <div class="ev-group-head">
          <span class="ev-badge big" :style="{ '--lv': meta.color }">{{ lv }}</span>
          <b>{{ meta.name }}</b>
          <span class="ev-group-desc">{{ meta.desc }}</span>
        </div>
        <ul class="ev-list">
          <li v-for="(item, i) in meta.items" :key="i">
            <span class="ev-what">{{ item.what }}</span>
            <a v-if="item.url" :href="item.url" target="_blank" rel="noopener" class="ev-text link">
              {{ item.text }} <ExternalLink :size="11" class="ev-ext" />
            </a>
            <span v-else class="ev-text">{{ item.text }}</span>
          </li>
          <li v-if="!meta.items.length" class="ev-empty">暂无</li>
        </ul>
      </div>
      <p class="ev-footnote">等级表示出处类型，不表示疗效强弱；模型预测详见「入血概率怎么算」。</p>
    </div>
  </div>
</template>

<style scoped>
.ev-card { padding: 14px 16px; }
.ev-head { display: flex; align-items: center; gap: 8px; width: 100%; background: none; border: none; cursor: pointer; padding: 0; }
.ev-title { font-size: 15px; font-weight: 700; }
.ev-badges { display: flex; gap: 4px; margin-left: auto; }
.ev-badge {
  width: 20px; height: 20px; border-radius: 6px; background: var(--lv, var(--ink-400));
  color: #fff; font-size: 11px; font-weight: 800; display: inline-flex; align-items: center; justify-content: center;
}
.ev-badge.big { width: 24px; height: 24px; font-size: 13px; flex-shrink: 0; }
.ev-arrow { color: var(--ink-400); transition: rotate .25s var(--ease-out-soft); }
.ev-arrow.flip { rotate: 180deg; }
.ev-note { font-size: 12px; color: var(--ink-400); margin-top: 8px; }
.ev-body { margin-top: 12px; }
.ev-group { margin-bottom: 14px; }
.ev-group:last-of-type { margin-bottom: 0; }
.ev-group-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.ev-group-head b { font-size: 13px; }
.ev-group-desc { font-size: 11px; color: var(--ink-400); }
.ev-list { list-style: none; padding-left: 32px; }
.ev-list li { font-size: 12px; color: var(--ink-600); line-height: 1.7; margin-bottom: 2px; }
.ev-what { color: var(--ink-400); margin-right: 6px; }
.ev-text.link { color: var(--green-700); text-decoration: none; }
.ev-ext { vertical-align: -1px; }
.ev-empty { color: var(--ink-400); }
.ev-footnote { font-size: 11px; color: var(--ink-400); margin-top: 10px; border-top: 1px dashed var(--green-100); padding-top: 8px; }
</style>
