<script setup>
// 家人适配提示：登录用户有体质档案（含家庭成员）时，
// 按每位成员最近一次测评的主体质，对照本方适宜/不宜体质给出提示。
// 数据全部来自既有接口（GET /api/v1/constitution/records），未登录不渲染。
import { ref, onMounted } from 'vue'
import { listRecords, isLoggedIn } from '../api'

const props = defineProps({
  suitable: { type: Array, default: () => [] },
  unsuitable: { type: Array, default: () => [] },
})

const items = ref([])

onMounted(async () => {
  if (!isLoggedIn()) return
  try {
    const records = (await listRecords()).data.data
    // 每个成员（含本人 member_id=null）只取最新一条
    const latest = new Map()
    for (const r of records) {
      const key = r.member_id ?? 0
      if (!latest.has(key)) latest.set(key, r)
    }
    items.value = [...latest.values()].map((r) => {
      const name = r.member_name || '我'
      const c = r.main_name
      let verdict = '一般'
      if (c && props.unsuitable.includes(c)) verdict = '不宜'
      else if (c && props.suitable.includes(c)) verdict = '适宜'
      return { name, constitution: c || '未知', verdict }
    })
  } catch { /* 401 由全局拦截处理，其余静默 */ }
})
</script>

<template>
  <div v-if="items.length" class="ff-wrap">
    <span v-for="it in items" :key="it.name" class="ff-chip" :class="it.verdict">
      {{ it.name }}·{{ it.constitution }}：{{ it.verdict }}
    </span>
  </div>
</template>

<style scoped>
.ff-wrap { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.ff-chip { font-size: 12px; padding: 4px 10px; border-radius: 999px; background: var(--green-50); color: var(--ink-600); }
.ff-chip.适宜 { background: var(--green-100); color: var(--green-text); font-weight: 600; }
.ff-chip.不宜 { background: var(--amber-50); color: var(--amber-text); font-weight: 600; }
</style>
