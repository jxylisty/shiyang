<script setup>
/**
 * 开放数据 API 页（T1-6）：给科研/教学用户看的接口说明
 * 端点列表 + 示例 + 许可与引用方式，全部从 /open 索引实时取
 */
import { ref, onMounted } from 'vue'
import { BookOpen, Copy, Check } from '@lucide/vue'
import { showSuccessToast } from 'vant'
import { getOpenIndex } from '../api'

const index = ref(null)
const copied = ref('')

onMounted(async () => {
  try { index.value = (await getOpenIndex()).data.data } catch { /* 静默 */ }
})

const ENDPOINTS = [
  { path: '/api/v1/open/catalog', desc: '卫健委药食同源目录（含批次与异名）' },
  { path: '/api/v1/open/herbs?limit=300', desc: '药材库：性味归经 / 功效 / 化合物数 / 目录归属' },
  { path: '/api/v1/open/compounds?min_prob=0.9&limit=50', desc: '化合物库：MW / logP / 入血概率 / 三维评分（可按概率过滤）' },
  { path: '/api/v1/open/compounds/{名称}/targets', desc: '单化合物作用靶点：活性类型 / 数据库来源 / PMID 直达' },
  { path: '/api/v1/open/constitutions', desc: '九种体质：宜忌食物 / 茶饮思路 / 调养原则' },
  { path: '/api/v1/open/stats', desc: '库存统计' },
  { path: '/api/v1/open/snapshot', desc: '全量数据集打包下载（JSON 附件，约 1.3 MB）' },
]

async function copy(path) {
  const url = location.origin + path
  try {
    await navigator.clipboard.writeText(url)
    copied.value = path
    showSuccessToast('已复制完整地址')
    setTimeout(() => { copied.value = '' }, 1500)
  } catch { /* 剪贴板不可用静默 */ }
}
</script>

<template>
  <div class="page">
    <div class="card head">
      <h2><BookOpen :size="18" /> 开放数据 API</h2>
      <p>药食同源目录 × 药材 × 化合物 × 靶点数据，免费只读接口，供科研与教学复用。无需注册、无需 Key。</p>
    </div>

    <div class="section-title">可用端点（{{ ENDPOINTS.length }}）</div>
    <div class="card ep-card" v-for="e in ENDPOINTS" :key="e.path">
      <div class="ep-row">
        <code class="ep-path">{{ e.path }}</code>
        <button class="copy-btn" @click="copy(e.path)">
          <Check v-if="copied === e.path" :size="14" />
          <Copy v-else :size="14" />
        </button>
      </div>
      <p class="ep-desc">{{ e.desc }}</p>
    </div>

    <div class="section-title">统一返回格式</div>
    <div class="card">
      <pre class="code">{
  "code": 0,
  "message": "success",
  "data": { ... },
  "meta": { "generated_at", "items", "data_license", "cite", "disclaimer" }
}</pre>
      <p class="hint">所有端点均带 meta（生成时间 / 条数 / 许可 / 引用方式 / 免责声明）。</p>
    </div>

    <template v-if="index">
      <div class="section-title">使用许可</div>
      <div class="card">
        <p class="hint"><b>{{ index.data_license }}</b></p>
        <p class="hint">引用建议：{{ index.cite }}</p>
        <p class="hint warn">{{ index.disclaimer }}</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.head { padding: 18px 16px; }
.head h2 { font-size: 18px; display: flex; align-items: center; gap: 6px; color: var(--green-700); }
.head p { font-size: 13px; color: var(--ink-600); margin-top: 6px; line-height: 1.6; }
.ep-card { padding: 12px 14px; margin-bottom: 10px; }
.ep-row { display: flex; align-items: center; gap: 8px; }
.ep-path { font-size: 12px; font-family: ui-monospace, Consolas, monospace; color: var(--green-700);
           background: var(--green-50); padding: 4px 8px; border-radius: 8px; word-break: break-all; flex: 1; }
.copy-btn { border: 1px solid var(--green-100); background: #fff; border-radius: 8px; padding: 5px;
            color: var(--green-700); cursor: pointer; flex-shrink: 0; display: inline-flex; }
.ep-desc { font-size: 12px; color: var(--ink-600); margin-top: 6px; }
.code { font-size: 12px; font-family: ui-monospace, Consolas, monospace; background: var(--green-50);
        border-radius: 8px; padding: 12px; overflow-x: auto; line-height: 1.6; }
.hint { font-size: 12px; color: var(--ink-600); margin-top: 6px; line-height: 1.7; }
.hint.warn { color: var(--amber-text); }
</style>
