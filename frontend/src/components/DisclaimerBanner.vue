<script setup>
import { Info } from '@lucide/vue'
const props = defineProps({
  // 不同场景的差异化文案：'general' 通用健康参考 / 'herb' 药材功效 / 'ai' AI解读
  // / 'compound' 成分活性 / 'recipe' 方子推荐 / 'safety' 安全警示
  variant: { type: String, default: 'general' },
  size: { type: String, default: 'sm' }, // sm = 小字页脚式，lg = 卡片式
})
const texts = {
  general: '本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。',
  herb: '药材功效描述基于药典与公开文献整理，仅作科普参考，不替代专业医疗建议。',
  ai: 'AI 解读由大模型生成，仅供通俗化理解参考，不构成医疗建议；成分数据与靶点关系以页面证据链为准。',
  compound: '成分活性数据来自公开数据库，为体外/文献层面结果，不等同于人体内功效，更不代表食疗效果。',
  recipe: '方子推荐基于体质与场景匹配，仅作食养参考，不针对个体医疗需求；有疾病或用药情况请遵医嘱。',
  safety: '人群禁忌库基于药典与公开资料整理，仅供筛选参考，不构成医疗建议；服用药物或特殊健康状况请遵医嘱。',
  report: '周期报告基于打卡记录与成分数据库统计，仅反映个人食养习惯，不构成健康诊断或治疗建议。',
  pantry: '我的茶罐匹配结果基于配料重叠度，仅供采购参考，不构成食疗方案建议。',
}
</script>

<template>
  <div class="disclaimer-banner" :class="[variant, size]">
    <Info :size="14" :stroke-width="2" />
    <span>{{ texts[variant] || texts.general }}</span>
  </div>
</template>

<style scoped>
.disclaimer-banner {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 12px; border-radius: 10px;
  background: var(--green-50); color: var(--ink-500);
  font-size: 11.5px; line-height: 1.6; border: 1px dashed var(--green-200);
}
.disclaimer-banner svg { flex-shrink: 0; margin-top: 1px; color: var(--green-600); }
.disclaimer-banner.lg { padding: 14px 16px; font-size: 12.5px; }
.disclaimer-banner.safety { background: var(--amber-50); border-color: var(--amber-200); color: var(--amber-text); }
.disclaimer-banner.safety svg { color: var(--amber-600); }
</style>
