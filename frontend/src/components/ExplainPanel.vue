<script setup>
/**
 * 入血概率可解释面板（T1-4）：模型判断依据科普化
 * 每个成分展示 分子量/logP 对照 Lipinski 口服有利特征 + 命中/超标人话解读
 */
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { CircleCheck, CircleX, ChevronDown } from '@lucide/vue'
import { getExplainRecipe } from '../api'

const router = useRouter()
const props = defineProps({ recipeId: { type: Number, required: true } })
const data = ref(null)
const openIdx = ref(0)
// 成分行展开态里给「成分词典」入口：整行按钮已用于展开/收起，词典入口放展开区底部
const goDict = (name) => router.push(`/compounds/${encodeURIComponent(name)}`)

async function load() {
  try { data.value = (await getExplainRecipe(props.recipeId)).data.data } catch { /* 静默 */ }
}
watch(() => props.recipeId, load, { immediate: true })
</script>

<template>
  <div class="card xp-card" v-if="data?.compounds?.length">
    <p class="xp-title">入血概率怎么算？</p>
    <p class="xp-sub">预测模型看两个关键吸收特征（Lipinski 口服有利规则）：
      <b>分子量 &lt; 500</b>（小分子易穿肠壁）、<b>logP &lt; 5</b>（脂溶性适中）。
      点开每个成分看模型的人话解读：</p>

    <div v-for="(c, i) in data.compounds" :key="c.name" class="xp-item">
      <button class="xp-row" @click="openIdx = openIdx === i ? -1 : i">
        <span class="xp-name">{{ c.name }}</span>
        <span class="xp-pass" :class="{ fail: c.pass_count < c.feat_count }">
          {{ c.pass_count }}/{{ c.feat_count }} 命中
        </span>
        <span class="xp-prob" :style="{ color: c.band.color }">{{ (c.prob_cctcm * 100).toFixed(0) }}%</span>
        <ChevronDown :size="14" class="xp-arrow" :class="{ flip: openIdx === i }" />
      </button>
      <div v-show="openIdx === i" class="xp-detail">
        <p class="xp-band" :style="{ color: c.band.color }">模型判断：{{ c.band.say }}</p>
        <div v-for="f in c.features" :key="f.key" class="xp-feat" :class="{ fail: !f.pass }">
          <span class="xp-feat-head">
            <CircleCheck v-if="f.pass" :size="14" />
            <CircleX v-else :size="14" />
            <b>{{ f.label }}</b>
            <span class="xp-val">{{ f.value }} <i>/ 上限 {{ f.limit }}</i></span>
          </span>
          <p class="xp-say">{{ f.say }}</p>
        </div>
        <button class="xp-dict" @click.stop="goDict(c.name)">查看 {{ c.name }} 的成分词典 →</button>
      </div>
    </div>
    <p class="xp-note">{{ data.note }}</p>
    <details class="xp-scope">
      <summary>这个概率不是"吸收率"（点开看说明）</summary>
      <p>模型预测的是成分<b>在血中被检出的倾向</b>，不是口服吸收百分比。所以会出现反直觉情况：
        人参皂苷这类大分子虽然吸收率低，但肠道菌群代谢后仍能在血中检出，模型给高分；
        挥发性小分子萜类虽然容易吸收，但代谢快、血中难检出，模型给低分。这由训练标签的定义决定，不是模型错误。</p>
      <p>数据来源：南京中医药大学赵玉男老师团队自建 ccTCM 2.0 数据库；模型 ROC-AUC 0.903，平台以 prob ≥ 0.7 为展示阈值，仅用于成分排序参考。</p>
    </details>
  </div>
</template>

<style scoped>
.xp-card { padding: 14px 16px; }
.xp-title { font-size: 15px; font-weight: 700; }
.xp-sub { font-size: 12px; color: var(--ink-600); margin: 4px 0 10px; line-height: 1.6; }
.xp-item { border-top: 1px solid var(--green-50); }
.xp-row { display: flex; align-items: center; gap: 8px; width: 100%; padding: 9px 0; background: none; border: none; cursor: pointer; }
.xp-name { font-size: 13px; font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: left; }
.xp-pass { font-size: 11px; color: var(--green-text); background: var(--green-50); border-radius: 8px; padding: 1px 7px; flex-shrink: 0; }
.xp-pass.fail { color: var(--amber-text); background: var(--amber-50); }
.xp-prob { font-size: 14px; font-weight: 800; flex-shrink: 0; width: 38px; text-align: right; }
.xp-arrow { color: var(--ink-400); transition: rotate .25s var(--ease-out-soft); flex-shrink: 0; }
.xp-arrow.flip { rotate: 180deg; }
.xp-detail { padding: 0 2px 12px; }
.xp-band { font-size: 12px; font-weight: 600; margin-bottom: 8px; }
.xp-feat { padding: 8px 10px; border-radius: 10px; background: var(--green-50); margin-bottom: 6px; }
.xp-feat.fail { background: var(--amber-50); }
.xp-feat-head { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-900); }
.xp-feat-head svg { color: var(--green-600); flex-shrink: 0; }
.xp-feat.fail .xp-feat-head svg { color: var(--amber-text); }
.xp-val { margin-left: auto; font-size: 12px; color: var(--ink-600); }
.xp-val i { font-style: normal; font-size: 10px; color: var(--ink-400); }
.xp-say { font-size: 12px; color: var(--ink-600); line-height: 1.6; margin-top: 4px; }
.xp-note { font-size: 11px; color: var(--ink-400); margin-top: 8px; line-height: 1.6; }
.xp-scope { margin-top: 10px; border-top: 1px dashed var(--green-100); padding-top: 8px; }
.xp-scope summary { font-size: 11.5px; color: var(--green-text); cursor: pointer; font-weight: 600; list-style: none; }
.xp-scope summary::-webkit-details-marker { display: none; }
.xp-scope summary::before { content: 'ⓘ '; }
.xp-scope p { font-size: 11px; color: var(--ink-600); line-height: 1.65; margin-top: 6px; }
.xp-dict { border: none; background: none; color: var(--green-text); font-size: 12px; cursor: pointer; padding: 2px 0 0; font-family: inherit; }
</style>
